"""Service helpers for audit logging.

The service layer wraps the repository to keep controllers lean and to allow
future expansion (e.g., fan-out to analytics or emitting domain events).
"""

from typing import Any, Optional

from repositories.audit_log_repo import add_audit_log, list_audit_logs_for_target


async def record_audit_event(
    *,
    actor_id: str,
    actor_type: str,
    action: str,
    target_type: str,
    target_id: str,
    metadata: Optional[dict[str, Any]] = None,
) -> dict:
    return await add_audit_log(
        actor_id=actor_id,
        actor_type=actor_type,
        action=action,
        target_type=target_type,
        target_id=target_id,
        metadata=metadata,
    )


async def fetch_audit_history(target_id: str, target_type: str, limit: int = 50):
    return await list_audit_logs_for_target(target_id=target_id, target_type=target_type, limit=limit)

