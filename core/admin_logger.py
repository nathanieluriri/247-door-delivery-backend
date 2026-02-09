
import time
from fastapi import Depends, Request
from security.auth import verify_admin_token
from repositories.admin_activity_repo import add_admin_activity


async def log_what_admin_does(request: Request, token: dict = Depends(verify_admin_token)):
    endpoint = request.scope.get("endpoint")
    payload = {
        "timestamp": int(time.time()),
        "adminId": token.get("userId") or token.get("user_id"),
        "method": request.method,
        "path": request.url.path,
        "query": dict(request.query_params),
        "endpoint": endpoint.__name__ if endpoint else None,
        "clientIp": request.client.host if request.client else None,
    }
    await add_admin_activity(payload)
    
    
    
    
