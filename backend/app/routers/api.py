from fastapi import APIRouter
from . import auth, rooms, chat, ws, moderation, keys, users, recordings

api_router = APIRouter()

api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(users.router, prefix="/users", tags=["users"])
api_router.include_router(rooms.router, prefix="/rooms", tags=["rooms"])
api_router.include_router(chat.router, prefix="/chat", tags=["chat"])
api_router.include_router(ws.router, prefix="/ws", tags=["ws"])
api_router.include_router(moderation.router, prefix="/moderation", tags=["moderation"])
api_router.include_router(keys.router, prefix="/keys", tags=["keys"])
api_router.include_router(recordings.router, prefix="/recordings", tags=["recordings"])
