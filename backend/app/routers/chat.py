from fastapi import APIRouter, Depends, HTTPException, Header
from sqlalchemy.orm import Session
from ..db.session import get_db
from ..models import Message, Room
from .auth import get_current_user
from .ws import hub

router = APIRouter()


def parse_token(authorization: str | None) -> str:
    if not authorization:
        raise HTTPException(status_code=401, detail="Missing Authorization header")
    if not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Invalid Authorization header")
    return authorization.split(" ", 1)[1]


@router.get("/{room_id}")
def get_messages(room_id: str, db: Session = Depends(get_db)):
    msgs = db.query(Message).filter(Message.room_id == room_id).order_by(Message.created_at.asc()).all()
    return [{"id": str(m.id), "user_id": str(m.user_id), "ciphertext": m.content_ciphertext, "created_at": m.created_at.isoformat()} for m in msgs]


@router.post("/{room_id}")
async def post_message(room_id: str, payload: dict, db: Session = Depends(get_db), authorization: str | None = Header(default=None)):
    token = parse_token(authorization)
    user = get_current_user(token, db)

    room = db.get(Room, room_id)
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")

    ciphertext = (payload.get("ciphertext") or "").strip()
    if not ciphertext:
        raise HTTPException(status_code=422, detail="ciphertext required")
    if len(ciphertext) > 4000:
        raise HTTPException(status_code=422, detail="message too long")

    msg = Message(room_id=room.id, user_id=user.id, content_ciphertext=ciphertext)
    db.add(msg)
    db.commit()
    db.refresh(msg)
    # broadcast to room via ws
    payload = {"type": "chat", "room_id": str(room.id), "msg": {"id": str(msg.id), "user_id": str(user.id), "ciphertext": msg.content_ciphertext, "created_at": msg.created_at.isoformat()}}
    await hub.broadcast(str(room.id), payload)
    return {"id": str(msg.id)}
