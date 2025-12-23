# Handles: chat:send_message, chat:get_ride_chats
from web_socket_handler.base import sio
from web_socket_handler.utils import is_rider, is_driver
from web_socket_handler.schemas.messages import SendChatRequest, SendChatResponse, GetRideChatsRequest, GetRideChatsResponse, ChatMessage, ErrorResponse
from services.chat_service import add_chat, retrieve_chat_by_chat_id
from schemas.chat import ChatCreate
import time

@sio.event
async def send_chat_message(sid, data):
    """
    Client -> Server: Send a chat message in a ride conversation.
    Expected data: {
        "ride_id": "12345",
        "message": "Hello, I'm on my way!"
    }
    """
    # Check if user is authenticated (either rider or driver)
    if not (is_rider(sid=sid) or is_driver(sid=sid)):
        response = ErrorResponse(message="Unauthorized", detail="You must be authenticated to chat")
        await sio.emit("send_chat_message_response", response.model_dump(), to=sid)
        return

    try:
        req = SendChatRequest(**data)

        # Get user info from authenticated users
        from web_socket_handler.base import authenticated_users
        user_info = authenticated_users.get(sid)
        if not user_info:
            response = SendChatResponse(status="error", message="User not authenticated")
            await sio.emit("send_chat_message_response", response.model_dump(), to=sid)
            return

        # Create chat message
        chat_data = ChatCreate(
            rideId=req.ride_id,
            message=req.message,
            userType=user_info["user_type"],
            userId=user_info["user_id"] 
        )

        # Save to database
        saved_chat = await add_chat(chat_data)

        # Create chat message for broadcasting
        chat_message = ChatMessage(
            id=str(saved_chat.id),
            ride_id=req.ride_id,
            sender_id=user_info["user_id"],
            sender_type=user_info["user_type"],
            message=req.message,
            timestamp=int(time.time())
        )

        # Broadcast to all participants in the ride room
        await sio.emit("chat_message", chat_message.model_dump(), room=f"ride_{req.ride_id}")

        # Send success response to sender
        response = SendChatResponse(
            status="success",
            message="Message sent",
            chat_id=str(saved_chat.id)
        )

    except Exception as e:
        print(f"❌ Error sending chat message: {e}")
        response = SendChatResponse(status="error", message="Failed to send message")

    await sio.emit("send_chat_message_response", response.model_dump(), to=sid)

@sio.event
async def get_ride_chats(sid, data):
    """
    Client -> Server: Get all chat messages for a specific ride.
    Expected data: {
        "ride_id": "12345"
    }
    """
    # Check if user is authenticated (either rider or driver)
    if not (is_rider(sid=sid) or is_driver(sid=sid)):
        response = ErrorResponse(message="Unauthorized", detail="You must be authenticated to view chats")
        await sio.emit("get_ride_chats_response", response.model_dump(), to=sid)
        return

    try:
        req = GetRideChatsRequest(**data)

        # Get user info from authenticated users
        from web_socket_handler.base import authenticated_users
        user_info = authenticated_users.get(sid)
        if not user_info:
            response = GetRideChatsResponse(status="error", message="User not authenticated")
            await sio.emit("get_ride_chats_response", response.model_dump(), to=sid)
            return

        # Retrieve all chats for the ride
        chats = await retrieve_chat_by_chat_id(req.ride_id)

        # Convert ChatOut objects to dictionaries for JSON serialization
        chats_data = [chat.model_dump() for chat in chats] if chats else []

        response = GetRideChatsResponse(
            status="success",
            message=f"Retrieved {len(chats_data)} chat messages",
            chats=chats_data
        )

    except Exception as e:
        print(f"❌ Error retrieving ride chats: {e}")
        response = GetRideChatsResponse(status="error", message="Failed to retrieve chats")

    await sio.emit("get_ride_chats_response", response.model_dump(), to=sid)