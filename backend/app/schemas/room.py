from pydantic import BaseModel
from uuid import UUID

class RoomCreate(BaseModel):
    name: str

class RoomOut(BaseModel):
    id: UUID
    name: str
    invite_code: str

    class Config:
        from_attributes = True
