from fastapi import APIRouter, HTTPException, Path, status, Request, Depends
from fastapi.responses import StreamingResponse
from typing import List

# Assuming these schemas exist based on your template
from schemas.response_schema import APIResponse
from schemas.chat import (
    ChatCreate,
    ChatOut,
    ChatBase,
    ChatUpdate,
)
from schemas.sse import ChatMessageEvent
from security.encrypting_jwt import JWTPayload
from services.chat_service import (
    add_chat,
    remove_chat,
    retrieve_chats,
    retrieve_chat_by_chat_id,
    update_chat_by_id,
)
from services.ride_service import retrieve_ride_by_ride_id
# Assuming you have your redis instance and auth dependencies
from security.auth import verify_token
from services.sse_service import stream_events
from schemas.imports import UserType

router = APIRouter(prefix="/chats", tags=["Chats"])

async def ensure_ride_membership(user: JWTPayload, ride_id: str) -> None:
    ride = await retrieve_ride_by_ride_id(id=ride_id)
    if user.user_type == "RIDER" and ride.userId != user.user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Ride access denied")
    if user.user_type == "DRIVER" and ride.driverId != user.user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Ride access denied")

# ------------------------------
# 1. Send Chat (Create & Broadcast)
# ------------------------------
@router.post(
    "",
    response_model=APIResponse[ChatOut],
    status_code=status.HTTP_201_CREATED,
    summary="Send a chat message",
    description="Creates a chat message for a ride and broadcasts it to the ride channel.",
)
async def send_chat_message(
    payload: ChatBase, 
    user:JWTPayload=Depends(verify_token) # Ensure user is authenticated
):
    """
    Sends a chat message. 
    1. Persists message to MongoDB (via service layer).
    2. Broadcasts message via Redis Pub/Sub to the specific ride channel.

    Access: Rider or Driver involved in the ride (valid access token required).
    """
    # Create the chat object (includes timestamps, etc.)
    
    
    new_data = ChatCreate(
        **payload.model_dump(),
        userType=UserType(user.user_type.lower()),
        userId=user.user_id,
    )
    await ensure_ride_membership(user, payload.rideId)
    
    # 1. Save to Database
    if user.user_type=="DRIVER":
        new_item = await add_chat(new_data,driverId=user.user_id)
    elif user.user_type=="RIDER":
        new_item = await add_chat(new_data,riderId=user.user_id)
    if not new_item: # type: ignore
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Failed to send message")
    
    return APIResponse(status_code=201, data=new_item, detail="Message sent and broadcasted")


# ------------------------------
# 2. Receive Chat Updates (SSE Stream)
# ------------------------------
@router.get(
    "/stream/{ride_id}",
    summary="Stream chat messages for a ride",
    description="Streams chat messages for a ride over Server-Sent Events.",
)
async def stream_chat_updates(
    ride_id: str,
    request: Request,
    user: JWTPayload = Depends(verify_token)
):
    """
    SSE Endpoint for Riders and Drivers to receive real-time chat messages.
    - Connects to Redis channel: 'ride:{ride_id}:chat'
    - Yields new messages as they are published by the POST route.

    Access: Rider or Driver involved in the ride (valid access token required).
    """
    await ensure_ride_membership(user, ride_id)
    return StreamingResponse(
        stream_events(
            request=request,
            user_type=user.user_type.lower(),
            user_id=user.user_id,
            event_types=["chat_message"],
            ride_id=ride_id,
        ),
        media_type="text/event-stream"
    )



# ---------------------------------
# Retrieve All Messages For Ride   
# ---------------------------------
@router.get(
    "/{rideId}",
    response_model=APIResponse[List[ChatMessageEvent]],
    summary="Get chat history for a ride",
    description="Returns stored chat messages associated with a ride.",
)
async def get_message_by_id(rideId: str = Path(..., description="ride ID")):
    """
    Fetch stored chat messages for a ride ID.

    Access: Public (no auth enforced).
    """
    item = await retrieve_chat_by_chat_id(id=rideId)
    if not item:
        raise HTTPException(status_code=404, detail="Message not found")
    events = [
        ChatMessageEvent(
            chatId=chat.id, # type: ignore
            rideId=chat.rideId,
            senderId=chat.userId or "",
            senderType=chat.userType, # type: ignore
            message=chat.text,
            timestamp=chat.date_created or chat.last_updated or 0,
        )
        for chat in item
    ]
    return APIResponse(status_code=200, data=events, detail="Message fetched")



# ------------------------------
# Delete Message
# ------------------------------
@router.delete(
    "/{id}",
    response_model=APIResponse[None],
    summary="Delete a chat message",
    description="Deletes a chat message by its identifier.",
)
async def delete_message(id: str = Path(...)):
    """
    Delete a single chat message by its ID.

    Access: Public (no auth enforced).
    """
    deleted = await remove_chat(id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Message not found or deletion failed")
    return APIResponse(status_code=200, data=None, detail="Message deleted")
