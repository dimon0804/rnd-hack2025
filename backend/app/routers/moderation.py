from fastapi import APIRouter, Depends, HTTPException, Header
from sqlalchemy.orm import Session
from ..db.session import get_db
from ..models import Participant, Room
from .auth import get_current_user

router = APIRouter()


def parse_token(authorization: str | None) -> str:
    if not authorization:
        raise HTTPException(status_code=401, detail="Missing Authorization header")
    if not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Invalid Authorization header")
    return authorization.split(" ", 1)[1]


def require_role(db: Session, room_id, user_id, allowed=("host", "moderator")) -> Participant:
    me = db.query(Participant).filter(Participant.room_id == room_id, Participant.user_id == user_id).first()
    if not me:
        raise HTTPException(status_code=403, detail="Not in room")
    if me.role not in allowed:
        raise HTTPException(status_code=403, detail="Insufficient role")
    return me


@router.post("/{room_id}/mute/{target_user_id}")
def mute(room_id: str, target_user_id: str, db: Session = Depends(get_db), authorization: str | None = Header(default=None)):
    token = parse_token(authorization)
    me = get_current_user(token, db)
    require_role(db, room_id, me.id)

    target = db.query(Participant).filter(Participant.room_id == room_id, Participant.user_id == target_user_id).first()
    if not target:
        raise HTTPException(status_code=404, detail="Target not found")
    target.muted_by_moderator = True
    db.commit()
    return {"status": "ok"}


@router.post("/{room_id}/unmute/{target_user_id}")
def unmute(room_id: str, target_user_id: str, db: Session = Depends(get_db), authorization: str | None = Header(default=None)):
    token = parse_token(authorization)
    me = get_current_user(token, db)
    require_role(db, room_id, me.id)

    target = db.query(Participant).filter(Participant.room_id == room_id, Participant.user_id == target_user_id).first()
    if not target:
        raise HTTPException(status_code=404, detail="Target not found")
    target.muted_by_moderator = False
    db.commit()
    return {"status": "ok"}


@router.post("/{room_id}/kick/{target_user_id}")
def kick(room_id: str, target_user_id: str, db: Session = Depends(get_db), authorization: str | None = Header(default=None)):
    token = parse_token(authorization)
    me = get_current_user(token, db)
    admin = require_role(db, room_id, me.id)

    target = db.query(Participant).filter(Participant.room_id == room_id, Participant.user_id == target_user_id).first()
    if not target:
        raise HTTPException(status_code=404, detail="Target not found")
    if admin.user_id == target_user_id:
        raise HTTPException(status_code=400, detail="Cannot kick yourself")
    db.delete(target)
    db.commit()
    return {"status": "ok"}


@router.post("/{room_id}/promote/{target_user_id}")
def promote(room_id: str, target_user_id: str, db: Session = Depends(get_db), authorization: str | None = Header(default=None)):
    token = parse_token(authorization)
    me = get_current_user(token, db)
    # Only host can promote to moderator
    my_p = require_role(db, room_id, me.id, allowed=("host",))

    target = db.query(Participant).filter(Participant.room_id == room_id, Participant.user_id == target_user_id).first()
    if not target:
        raise HTTPException(status_code=404, detail="Target not found")
    target.role = "moderator"
    db.commit()
    return {"status": "ok"}


@router.post("/{room_id}/demote/{target_user_id}")
def demote(room_id: str, target_user_id: str, db: Session = Depends(get_db), authorization: str | None = Header(default=None)):
    token = parse_token(authorization)
    me = get_current_user(token, db)
    # Only host can demote
    my_p = require_role(db, room_id, me.id, allowed=("host",))

    target = db.query(Participant).filter(Participant.room_id == room_id, Participant.user_id == target_user_id).first()
    if not target:
        raise HTTPException(status_code=404, detail="Target not found")
    target.role = "guest"
    db.commit()
    return {"status": "ok"}
