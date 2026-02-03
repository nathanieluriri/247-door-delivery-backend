"""
Antivirus helper using clamd if available. Falls back to a stub when not configured.
"""
import os
from typing import Tuple

try:
    import clamd  # type: ignore
except ImportError:  # pragma: no cover
    clamd = None


CLAMAV_HOST = os.getenv("CLAMAV_HOST", "localhost")
CLAMAV_PORT = int(os.getenv("CLAMAV_PORT", "3310"))
AV_ENABLED = os.getenv("AV_ENABLED", "0") in {"1", "true", "True"}


def scan_bytes(content: bytes) -> Tuple[bool, str]:
    """
    Returns (is_clean, message).
    If AV is disabled or clamd missing, returns clean=True.
    """
    if not AV_ENABLED:
        return True, "av_disabled"
    if not clamd:
        return False, "clamd_not_installed"
    try:
        client = clamd.ClamdNetworkSocket(CLAMAV_HOST, CLAMAV_PORT)
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
