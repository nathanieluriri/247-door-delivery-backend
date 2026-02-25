"""
Antivirus helper using clamd if available. Falls back to a stub when not configured.
"""
import importlib
import os
from typing import Any, Tuple


CLAMAV_HOST = os.getenv("CLAMAV_HOST", "localhost")
CLAMAV_PORT = int(os.getenv("CLAMAV_PORT", "3310"))
AV_ENABLED = os.getenv("AV_ENABLED", "0") in {"1", "true", "True"}


def _load_clamd() -> Any | None:
    try:
        return importlib.import_module("clamd")
    except ImportError:  # pragma: no cover - optional dependency
        return None


def scan_bytes(content: bytes) -> Tuple[bool, str]:
    """
    Returns (is_clean, message).
    If AV is disabled, returns clean=True.
    """
    if not AV_ENABLED:
        return True, "av_disabled"
    clamd_module = _load_clamd()
    if clamd_module is None:
        return False, "clamd_not_installed"
    try:
        client = clamd_module.ClamdNetworkSocket(CLAMAV_HOST, CLAMAV_PORT)
        result = client.instream(content)
        status = result.get("stream")
        if not status:
            return True, "no_result"
        verdict, reason = status
        if verdict == "OK":
            return True, reason
        return False, reason
    except Exception as e:  # pragma: no cover - best effort
        return False, f"av_error:{e}"
