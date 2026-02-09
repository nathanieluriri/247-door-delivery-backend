from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import StreamingResponse

from schemas.response_schema import APIResponse
from schemas.sse import SSEAck, SSEEventType
from schemas.tokens_schema import accessTokenOut
from security.auth import verify_token_driver_role, verify_token_rider_role
from security.account_status_checks import check_driver_sse_eligibility, get_driver_sse_eligibility_status
from services.sse_service import ack_event, stream_events


router = APIRouter(prefix="/sse", tags=["SSE"])


@router.get(
    "/driver/stream",
    summary="Stream SSE updates for drivers",
    description="Opens a Server-Sent Events stream for driver notifications, optionally filtered by ride or event type.",
)
async def stream_driver_events(
    request: Request,
    ride_id: Optional[str] = Query(default=None),
    event_types: Optional[List[SSEEventType]] = Query(default=None),
    token: accessTokenOut = Depends(verify_token_driver_role),
    _driver: object = Depends(check_driver_sse_eligibility),
):
    """
    Open an SSE stream for driver events with optional ride and event-type filters.

    Access: Driver only (valid driver access token required).
    """
    allowed_types = [event_type.value for event_type in event_types] if event_types else None
    return StreamingResponse(
        stream_events(
            request=request,
            user_type="driver",
            user_id=token.userId,
            event_types=allowed_types,
            ride_id=ride_id,
        ),
        media_type="text/event-stream",
    )


@router.get(
    "/driver/eligibility",
    response_model=APIResponse[dict],
    summary="Check driver SSE eligibility",
    description="Returns whether the authenticated driver can open SSE streams and the reasons if not.",
)
async def check_driver_sse_stream_eligibility(
    token: accessTokenOut = Depends(verify_token_driver_role),
):
    """
    Returns SSE eligibility status for the authenticated driver.

    Access: Driver only (valid driver access token required).
    """
    status = await get_driver_sse_eligibility_status(token)
    return APIResponse(status_code=200, data=status, detail="SSE eligibility checked")


@router.get(
    "/rider/stream",
    summary="Stream SSE updates for riders",
    description="Opens a Server-Sent Events stream for rider notifications, optionally filtered by ride or event type.",
)
async def stream_rider_events(
    request: Request,
    ride_id: Optional[str] = Query(default=None),
    event_types: Optional[List[SSEEventType]] = Query(default=None),
    token: accessTokenOut = Depends(verify_token_rider_role),
):
    """
    Open an SSE stream for rider events with optional ride and event-type filters.

    Access: Rider only (valid rider access token required).
    """
    allowed_types = [event_type.value for event_type in event_types] if event_types else None
    return StreamingResponse(
        stream_events(
            request=request,
            user_type="rider",
            user_id=token.userId,
            event_types=allowed_types,
            ride_id=ride_id,
        ),
        media_type="text/event-stream",
    )


@router.post(
    "/driver/ack",
    response_model=APIResponse[bool],
    summary="Acknowledge a driver SSE event",
    description="Marks a driver event as received to support reliable delivery.",
)
async def ack_driver_event(
    payload: SSEAck,
    token: accessTokenOut = Depends(verify_token_driver_role),
):
    """
    Acknowledge receipt of a driver SSE event by event ID.

    Access: Driver only (valid driver access token required).
    """
    acknowledged = await ack_event(
        user_type="driver",
        user_id=token.userId,
        event_id=payload.event_id,
    )
    if not acknowledged:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Event not found",
        )
    return APIResponse(status_code=200, data=True, detail="Event acknowledged")


@router.post(
    "/rider/ack",
    response_model=APIResponse[bool],
    summary="Acknowledge a rider SSE event",
    description="Marks a rider event as received to support reliable delivery.",
)
async def ack_rider_event(
    payload: SSEAck,
    token: accessTokenOut = Depends(verify_token_rider_role),
):
    """
    Acknowledge receipt of a rider SSE event by event ID.

    Access: Rider only (valid rider access token required).
    """
    acknowledged = await ack_event(
        user_type="rider",
        user_id=token.userId,
        event_id=payload.event_id,
    )
    if not acknowledged:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Event not found",
        )
    return APIResponse(status_code=200, data=True, detail="Event acknowledged")
