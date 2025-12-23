from fastapi import APIRouter, HTTPException, Query, Path, status, Request, Depends
from fastapi.responses import StreamingResponse
from typing import List, Optional
import json

# Assuming these schemas exist based on your template
from schemas.response_schema import APIResponse
from schemas.chat import (
    ChatCreate,
    ChatOut,
    ChatBase,
    ChatUpdate,
)
from security.encrypting_jwt import JWTPayload
from services.chat_service import (
    add_chat,
    remove_chat,
    retrieve_chats,
    retrieve_chat_by_chat_id,
    update_chat_by_id,
)
# Assuming you have your redis instance and auth dependencies
from core.redis_cache import async_redis
from security.auth import verify_token

router = APIRouter(prefix="/chats", tags=["Chats"])

# ------------------------------
# 1. Send Chat (Create & Broadcast)
# ------------------------------
@router.post("/", response_model=APIResponse[ChatOut], status_code=status.HTTP_201_CREATED)
async def send_chat_message(
    payload: ChatBase, 
    user:JWTPayload=Depends(verify_token) # Ensure user is authenticated
):
    """
    Sends a chat message. 
    1. Persists message to MongoDB (via service layer).
    2. Broadcasts message via Redis Pub/Sub to the specific ride channel.
    """
    # Create the chat object (includes timestamps, etc.)
    
    
    new_data = ChatCreate(**payload.model_dump(),userType=user.user_type,userId=user.user_id)
    
    # 1. Save to Database
    if user.user_type=="DRIVER":
        new_item = await add_chat(new_data,driverId=user.user_id)
    elif user.user_type=="RIDER":
        new_item = await add_chat(new_data,riderId=user.user_id)
    if not new_item:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Failed to send message")
    
    # 2. Publish to Redis (The SSE route listens to this)
    # Channel format: "ride:{ride_id}:chat"
    # We serialize the output model to JSON for the stream
    channel = f"ride:{new_item.ride_id}:chat"
    message_data = new_item.model_dump_json()
    
    await async_redis.publish(channel, message_data)
    
    return APIResponse(status_code=201, data=new_item, detail="Message sent and broadcasted")


# ------------------------------
# 2. Receive Chat Updates (SSE Stream)
# ------------------------------
@router.get("/stream/{ride_id}", summary="Stream chat messages for a ride")
async def stream_chat_updates(
    ride_id: str,
    request: Request,
    user=Depends(verify_token)
):
    """
    SSE Endpoint for Riders and Drivers to receive real-time chat messages.
    - Connects to Redis channel: 'ride:{ride_id}:chat'
    - Yields new messages as they are published by the POST route.
    """
    pubsub = async_redis.pubsub()
    channel = f"ride:{ride_id}:chat"
    await pubsub.subscribe(channel)

    async def event_generator():
        try:
            async for message in pubsub.listen():
                if await request.is_disconnected():
                    break

                if message["type"] == "message":
                    # message['data'] is the JSON string we published in send_chat_message
                    yield f"data: {message['data']}\n\n"
        finally:
            await pubsub.unsubscribe(channel)
            await pubsub.close()

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream"
    )



# ---------------------------------
# Retrieve All Messages For Ride   
# ---------------------------------
@router.get("/{rideId}", response_model=APIResponse[List[ChatOut]])
async def get_message_by_id(rideId: str = Path(..., description="ride ID")):
    item = await retrieve_chat_by_chat_id(id=id)
    if not item:
        raise HTTPException(status_code=404, detail="Message not found")
    return APIResponse(status_code=200, data=item, detail="Message fetched")



# ------------------------------
# Delete Message
# ------------------------------
@router.delete("/{id}", response_model=APIResponse[None])
async def delete_message(id: str = Path(...)):
    deleted = await remove_chat(id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Message not found or deletion failed")
    return APIResponse(status_code=200, data=None, detail="Message deleted")