from schemas.imports import *
import os
from datetime import timedelta


def _refresh_token_expiry_default() -> datetime:
    raw_value = os.getenv("REFRESH_TOKEN_EXPIRE_DAYS")
    try:
        days = int(raw_value) if raw_value is not None else 30
    except ValueError:
        days = 30
    return datetime.now(timezone.utc) + timedelta(days=max(days, 1))


class refreshedTokenRequest(BaseModel):
    refreshToken:str
class refreshedToken(BaseModel):
    userId:str
    dateCreated: int = Field(default_factory=lambda: int(time.time()))
    refreshToken:str
    accessToken:str

class accessTokenBase(BaseModel):
    userId:str

    
class accessTokenCreate(accessTokenBase):
    dateCreated: int = Field(default_factory=lambda: int(time.time()))

    
class accessTokenOut(accessTokenBase):
    dateCreated: int = Field(default_factory=lambda: int(time.time()))
    accesstoken: Optional[str] =None
    role:Optional[str]="annonymous"
    @model_validator(mode='before')
    def set_values(cls,values):
        if values is None:
            values = {}
        values['accesstoken']= str(values.get('_id'))
        admin_token = values.get("accessToken",None)
        if admin_token:
            values['accesstoken']=values.get("accessToken")
        return values
    
    model_config = {
        'populate_by_name': True,
        'arbitrary_types_allowed': True,
    }
    
    
    

    

class refreshTokenBase(BaseModel):
    userId:str
    previousAccessToken:str

    
class refreshTokenCreate(refreshTokenBase):
    dateCreated:int = Field(default_factory=lambda: int(time.time()))
    expiresAt: datetime = Field(default_factory=_refresh_token_expiry_default)

    
class refreshTokenOut(refreshTokenCreate):
    refreshtoken: Optional[str] =None
    @model_validator(mode='before')
    def set_values(cls,values):
        if values is None:
            values = {}
        values['refreshtoken']= str(values.get('_id'))
        return values
    
    model_config = {
        'populate_by_name': True,
        'arbitrary_types_allowed': True,
    }


class TokenOut(BaseModel):
    userId:str
    accesstoken: Optional[str] =None
    refreshtoken: Optional[str] =None
    dateCreated:Optional[str]=datetime.now(timezone.utc).isoformat()
    @model_validator(mode='before')
    def set_dates(cls,values):
        if values is None:
            values = {}
        now_str = datetime.now(timezone.utc).isoformat()
        values['dateCreated']= now_str
        return values    



class refreshTokenRequest(BaseModel):
    refreshToken:str
