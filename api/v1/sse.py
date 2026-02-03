from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import StreamingResponse

from schemas.response_schema import APIResponse
from schemas.sse import SSEAck, SSEEventType
from schemas.tokens_schema import accessTokenOut
from security.auth import verify_token_driver_role, verify_token_rider_role
from services.sse_service import ack_event, stream_events


router = APIRouter(prefix="/sse", tags=["SSE"])


@router.get("/driver/stream", summary="Stream SSE updates for drivers")
async def stream_driver_events(
    request: Request,
    ride_id: Optional[str] = Query(default=None),
    event_types: Optional[List[SSEEventType]] = Query(default=None),
    token: accessTokenOut = Depends(verify_token_driver_role),
):
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


@router.get("/rider/stream", summary="Stream SSE updates for riders")
async def stream_rider_events(
    request: Request,
    ride_id: Optional[str] = Query(default=None),
    event_types: Optional[List[SSEEventType]] = Query(default=None),
    token: accessTokenOut = Depends(verify_token_rider_role),
):
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


@router.post("/driver/ack", response_model=APIResponse[bool])
async def ack_driver_event(
    payload: SSEAck,
    token: accessTokenOut = Depends(verify_token_driver_role),
):
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


@router.post("/rider/ack", response_model=APIResponse[bool])
async def ack_rider_event(
    payload: SSEAck,
    token: accessTokenOut = Depends(verify_token_rider_role),
):
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
