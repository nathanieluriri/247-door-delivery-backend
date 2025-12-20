import socketio
import os
import asyncio

 
from web_socket_handler.schemas.messages import AuthenticateRequest, AuthenticateResponse, ServerMessage
from security.encrypting_jwt import decode_jwt_token
from repositories.tokens_repo import get_access_tokens

redis_url = os.getenv("CELERY_BROKER_URL") or os.getenv("REDIS_URL") \
    or f"redis://{os.getenv('REDIS_HOST', 'redis')}:{os.getenv('REDIS_PORT', '6379')}/0"

mgr = socketio.AsyncRedisManager(redis_url)

# 2. Server Instance
sio = socketio.AsyncServer(
    async_mode='asgi',
    cors_allowed_origins='*', # Lock this down in production
    client_manager=mgr,
    logger=True,
    engineio_logger=True
)

# Store authenticated users
authenticated_users = {}  # sid -> {"user_id": str, "user_type": str}

@sio.event
async def connect(sid, environ):
    print("Client connecting:", sid)
    # Send welcome message
    await sio.emit("server_message", ServerMessage(msg="Connected to server! Please authenticate.").model_dump())

@sio.event
async def authenticate(sid, data):
    from web_socket_handler.utils import sync_cleanup_user, sync_save_active_user
    try:
        auth_data = AuthenticateRequest(**data)
        token = auth_data.token

        access_token = await decode_jwt_token(token=token)
        result = await get_access_tokens(accessToken=access_token['access_token'])

        if access_token['user_type'] in ["RIDER", "DRIVER"] and access_token['is_activated']:
            user_type = access_token['user_type']
            user_id = result.userId

            # Save to authenticated users
            authenticated_users[sid] = {"user_id": user_id, "user_type": user_type}

            # Offload DB Save to a Thread
            await asyncio.to_thread(
                sync_save_active_user,
                sid,
                user_id,
                user_type
            )

            response = AuthenticateResponse(
                status="success",
                message="Authenticated successfully",
                user_type=user_type,
                user_id=user_id
            )
        else:
            response = AuthenticateResponse(status="error", message="Invalid or inactive token")

    except Exception as e:
        print(f"Authentication error for {sid}: {e}")
        response = AuthenticateResponse(status="error", message="Authentication failed")

    await sio.emit("authenticate_response", response.model_dump(), to=sid)
    
    
@sio.event
async def disconnect(sid,*args):
    from web_socket_handler.utils import sync_cleanup_user, sync_save_active_user
    print("Client disconnected:", sid)

    # Remove from authenticated users
    if sid in authenticated_users:
        del authenticated_users[sid]

    # NO emit here (client is already gone)

    # Run the cleanup in a thread so the server doesn't freeze
    await asyncio.to_thread(sync_cleanup_user, sid)