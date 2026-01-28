from typing import Optional
import jwt
 
from datetime import timedelta, timezone,datetime
from core.database import db
from dotenv import load_dotenv
import os
from pydantic import BaseModel
from bson import ObjectId

load_dotenv()
SECRETID = os.getenv("SECRETID")
# Token lifetime (in minutes)
ACCESS_TOKEN_EXPIRE_MINUTES = 60
# Secret key for signing (use env var in production)


# ---------------------------
# JWT Schema
# ---------------------------
class JWTPayload(BaseModel):
    access_token: str
    user_id: str
    user_type: str
    is_activated: bool
    exp: datetime
    iat: datetime

SECRET_KEY = os.getenv("SECRET_KEY", "super-secure-secret-key")
ALGORITHM = "HS256"

async def get_secret_dict()->dict:
    if not SECRETID:
        raise ValueError("SECRETID is not configured")
    result = await db.secret_keys.find_one({"_id":ObjectId(SECRETID)})
    if not result:
        raise ValueError("Secret key set not found")
    result.pop('_id', None)
    return result



async def get_secret_and_header():
    
    import random
    
    secrets = await get_secret_dict()
    if not secrets:
        raise ValueError("No secrets available for JWT signing")
    
    random_key = random.choice(list(secrets.keys()))
    random_secret = secrets[random_key]
    SECRET_KEYS={random_key:random_secret}
    HEADERS = {"kid":random_key}
    result = {
        "SECRET_KEY":SECRET_KEYS,
        "HEADERS":HEADERS
    }
    
    return result


async def _resolve_secret_for_token(token: str) -> str:
    try:
        header = jwt.get_unverified_header(token)
    except Exception:
        return SECRET_KEY
    kid = header.get("kid") if isinstance(header, dict) else None
    if not kid:
        return SECRET_KEY
    try:
        secrets = await get_secret_dict()
    except Exception:
        return SECRET_KEY
    return secrets.get(kid, SECRET_KEY)


# ---------------------------
# Create Token
# ---------------------------
def create_jwt_token(
    access_token: str,
    user_id: str,
    user_type: str,
    is_activated: bool,
    role: str = "member",
) -> str:
    payload = JWTPayload(
        access_token=access_token,
        user_id=user_id,
        user_type=user_type,
        is_activated=is_activated,
        exp=datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES),
        iat=datetime.now(timezone.utc),
    ).model_dump()

    payload["role"] = role

    token = jwt.encode(
        payload=payload,
        key=SECRET_KEY,
        algorithm=ALGORITHM,   # "HS256"
        headers={"typ": "JWT"},
    )

    return token





async def create_jwt_member_token(token):
    try:
        secrets = await get_secret_and_header()
        secret_key = secrets["SECRET_KEY"][secrets["HEADERS"]["kid"]]
        headers = secrets["HEADERS"]
    except Exception:
        secret_key = SECRET_KEY
        headers = {"typ": "JWT"}

    payload = {
        "accessToken": token,
        "role": "member",
        "exp": datetime.now(timezone.utc) + timedelta(minutes=15),
    }

    return jwt.encode(
        payload,
        secret_key,
        algorithm="HS256",
        headers=headers,
    )

async def create_jwt_admin_token(token: str,userId:str):
    payload = {
        "accessToken": token,
        "role": "admin",
        "userId":userId,
        "exp": datetime.now(timezone.utc) + timedelta(minutes=15)
    }

    encoded_jwt = jwt.encode(payload, SECRET_KEY, algorithm="HS256")
    return encoded_jwt



async def decode_jwt_token(token: str)->Optional[dict]:
    """
    Decodes and verifies a JWT token.

    Args:
        token (str): Encoded JWT token.

    Returns:
        dict | None: Decoded payload if valid, or None if invalid/expired.

    Example:
        {'accessToken': '682c99f395ff4782fbea010f', 'role': 'admin', 'exp': 1747825460}
    """

    try:
        secret = await _resolve_secret_for_token(token)
        decoded = jwt.decode(token, secret, algorithms=["HS256"])
        return decoded

    except jwt.ExpiredSignatureError:
        return None

    except jwt.InvalidSignatureError:
        return None

    except jwt.DecodeError:
        return None

    except Exception as e:
        return None

async def decode_jwt_token_without_expiration(token: str):
    secret = await _resolve_secret_for_token(token)
    try:
        decoded = jwt.decode(token, secret, algorithms=["HS256"])

        return decoded
    
    except jwt.ExpiredSignatureError:
    
        try:
            decoded = jwt.decode(
                token,
                secret,
                algorithms=["HS256"],
                options={"verify_exp": False},
            )
            return decoded
        except Exception as inner_e:
            return None

    except jwt.DecodeError:
        return None

    except Exception as e:
        return None




