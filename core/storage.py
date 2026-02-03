"""
Storage abstraction for driver documents.

Backends:
- local: saves to uploads/documents/{driverId}/{uuid-filename}
- s3: uploads to configured bucket with optional presigned URLs

Environment variables:
- STORAGE_BACKEND: "local" (default) or "s3"
- STORAGE_LOCAL_ROOT: base folder for local storage (default "uploads/documents")
- STORAGE_S3_BUCKET, STORAGE_S3_REGION, STORAGE_S3_ENDPOINT (optional for S3-compatible)
- STORAGE_SIGNED_URL_TTL: seconds for presigned URLs (default 900)
- AV_ENABLED: "1" to enable simple AV stub (placeholder)
"""

from __future__ import annotations

import os
import uuid
import hashlib
from typing import Optional, Tuple

from core.antivirus import scan_bytes
from core.metrics import av_scan_failures, integrity_failures

try:
    import boto3  # type: ignore
except ImportError:  # pragma: no cover - optional
    boto3 = None


STORAGE_BACKEND = os.getenv("STORAGE_BACKEND", "local").lower()
LOCAL_ROOT = os.getenv("STORAGE_LOCAL_ROOT", os.path.join("uploads", "documents"))
SIGNED_URL_TTL = int(os.getenv("STORAGE_SIGNED_URL_TTL", "900"))


class StoredObject:
    def __init__(self, key: str, url: Optional[str] = None, provider: str = "local", sha256: str | None = None, md5: str | None = None):
        self.key = key
        self.url = url
        self.provider = provider
        self.sha256 = sha256
        self.md5 = md5


def _ensure_dir(path: str):
    os.makedirs(path, exist_ok=True)


def _virus_scan_stub(content: bytes) -> None:
    """Placeholder for AV scan. Raises if content is empty when AV is enabled."""
    if os.getenv("AV_ENABLED") not in {"1", "true", "True"}:
        return
    if not content:
        raise ValueError("File failed AV scan (empty content)")


def _hash_content(content: bytes) -> Tuple[str, str]:
    sha256 = hashlib.sha256(content).hexdigest()
    md5 = hashlib.md5(content).hexdigest()  # nosec - for integrity only
    return sha256, md5


def store_file(driver_id: str, filename: str, content: bytes, content_type: Optional[str] = None) -> StoredObject:
    _virus_scan_stub(content)
    clean, reason = scan_bytes(content)
    if not clean:
        av_scan_failures.inc()
        raise ValueError(f"AV scan failed: {reason}")
    sha256, md5 = _hash_content(content)
    if STORAGE_BACKEND == "s3":
        if boto3 is None:
            raise RuntimeError("boto3 not installed; cannot use s3 storage backend")
        bucket = os.environ["STORAGE_S3_BUCKET"]
        region = os.getenv("STORAGE_S3_REGION")
        endpoint = os.getenv("STORAGE_S3_ENDPOINT")
        s3 = boto3.client("s3", region_name=region, endpoint_url=endpoint)
        key = f"drivers/{driver_id}/{uuid.uuid4().hex}-{filename}"
        extra = {"ContentType": content_type} if content_type else {}
        s3.put_object(Bucket=bucket, Key=key, Body=content, Metadata={"sha256": sha256, "md5": md5}, **extra)
        url = s3.generate_presigned_url(
            "get_object",
            Params={"Bucket": bucket, "Key": key},
            ExpiresIn=SIGNED_URL_TTL,
        )
        return StoredObject(key=key, url=url, provider="s3", sha256=sha256, md5=md5)

    # local backend
    driver_dir = os.path.join(LOCAL_ROOT, driver_id)
    _ensure_dir(driver_dir)
    safe_name = f"{uuid.uuid4().hex}-{filename}"
    path = os.path.join(driver_dir, safe_name)
    with open(path, "wb") as f:
        f.write(content)
    return StoredObject(key=path, url=None, provider="local", sha256=sha256, md5=md5)


def get_signed_url(key: str) -> Optional[str]:
    if STORAGE_BACKEND != "s3" or boto3 is None:
        return None
    bucket = os.environ["STORAGE_S3_BUCKET"]
    region = os.getenv("STORAGE_S3_REGION")
    endpoint = os.getenv("STORAGE_S3_ENDPOINT")
    s3 = boto3.client("s3", region_name=region, endpoint_url=endpoint)
    return s3.generate_presigned_url(
        "get_object",
        Params={"Bucket": bucket, "Key": key},
        ExpiresIn=SIGNED_URL_TTL,
    )


def verify_integrity(key: str, expected_sha256: Optional[str]) -> bool:
    if not expected_sha256:
        return False
    if STORAGE_BACKEND == "s3" and boto3 is not None and not key.startswith("/"):
        bucket = os.environ["STORAGE_S3_BUCKET"]
        region = os.getenv("STORAGE_S3_REGION")
        endpoint = os.getenv("STORAGE_S3_ENDPOINT")
        s3 = boto3.client("s3", region_name=region, endpoint_url=endpoint)
        meta = s3.head_object(Bucket=bucket, Key=key)
        stored = meta.get("Metadata", {}).get("sha256")
        return stored == expected_sha256
    # local path
    if os.path.exists(key):
        with open(key, "rb") as f:
            data = f.read()
        sha256, _ = _hash_content(data)
        ok = sha256 == expected_sha256
        if not ok:
            integrity_failures.inc()
        return ok
    integrity_failures.inc()
    return False


def quarantine_file(driver_id: str, filename: str, content: bytes, content_type: Optional[str] = None) -> StoredObject:
    """Save infected files to a quarantine location/prefix."""
    if STORAGE_BACKEND == "s3":
        if boto3 is None:
            raise RuntimeError("boto3 not installed; cannot use s3 storage backend")
        bucket = os.environ["STORAGE_S3_BUCKET"]
        region = os.getenv("STORAGE_S3_REGION")
        endpoint = os.getenv("STORAGE_S3_ENDPOINT")
        s3 = boto3.client("s3", region_name=region, endpoint_url=endpoint)
        key = f"quarantine/{driver_id}/{uuid.uuid4().hex}-{filename}"
        extra = {"ContentType": content_type} if content_type else {}
        s3.put_object(Bucket=bucket, Key=key, Body=content, Metadata={"reason": "virus"}, **extra)
        return StoredObject(key=key, provider="s3")
    # local
    q_dir = os.path.join(LOCAL_ROOT, "quarantine", driver_id)
    _ensure_dir(q_dir)
    safe_name = f"{uuid.uuid4().hex}-{filename}"
    path = os.path.join(q_dir, safe_name)
    with open(path, "wb") as f:
        f.write(content)
    return StoredObject(key=path, provider="local")
