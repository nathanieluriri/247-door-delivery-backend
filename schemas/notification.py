from pydantic import BaseModel, Field


class PushTokenRegister(BaseModel):
    player_id: str = Field(..., alias="playerId")

    model_config = {
        "populate_by_name": True,
        "json_schema_extra": {
            "examples": [
                {
                    "playerId": "onesignal_player_id_123",
                }
            ]
        },
    }
