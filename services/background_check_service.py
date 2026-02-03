from __future__ import annotations

from schemas.background_check import (
    BackgroundCheckCreate,
    BackgroundCheckOut,
    BackgroundCheckUpdate,
    BackgroundStatus,
)
from repositories.background_check_repo import (
    create_background_check,
    get_background_check,
    update_background_check,
)
from services.driver_document_service import get_driver_documents
from repositories.audit_log_repo import add_audit_log


async def ensure_background_record(driver_id: str) -> BackgroundCheckOut:
    existing = await get_background_check(driver_id)
    if existing:
        return existing
    return await create_background_check(BackgroundCheckCreate(driverId=driver_id))


async def record_background_result(driver_id: str, status: BackgroundStatus, notes: str | None = None, reference: str | None = None):
    return await update_background_check(
        driver_id, BackgroundCheckUpdate(status=status, notes=notes, referenceId=reference)
    )


async def fetch_background_check(driver_id: str) -> BackgroundCheckOut | None:
    return await get_background_check(driver_id)


async def list_background_checks():
    # simple passthrough for admin listing
    cursor = db.background_checks.find().sort("updatedAt", -1)
    results = []
    async for doc in cursor:
        results.append(BackgroundCheckOut.model_validate_db(doc))
    return results


async def auto_link_documents_to_background(driver_id: str) -> bool:
    """
    If all required documents are approved, and background is pending, auto-set status to PASSED.
    """
    bg = await get_background_check(driver_id)
    if not bg or bg.status != BackgroundStatus.PENDING:
        return False
    docs = await get_driver_documents(driver_id)
    required_types = {
        "driver_license",
        "vehicle_registration",
        "insurance",
    }
    approved = {d.documentType.value for d in docs if d.status == "approved"}
    if not required_types.issubset(approved):
        return False
    await update_background_check(driver_id, BackgroundCheckUpdate(status=BackgroundStatus.PASSED, notes="Auto-passed based on docs"))
    await add_audit_log(
        actor_id="system",
        actor_type="system",
        action="background_auto_pass",
        target_type="driver",
        target_id=driver_id,
        metadata={"reason": "docs_approved"},
    )
    return True
