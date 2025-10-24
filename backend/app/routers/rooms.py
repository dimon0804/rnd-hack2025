import secrets
from fastapi import APIRouter, Depends, HTTPException, Header
from sqlalchemy.orm import Session
from ..db.session import get_db
from ..models import Room, User, Participant
from ..schemas.room import RoomCreate, RoomOut
from .auth import get_current_user

router = APIRouter()


def parse_token(authorization: str | None) -> str:
    if not authorization:
        raise HTTPException(status_code=401, detail="Missing Authorization header")
    if not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Invalid Authorization header")
    return authorization.split(" ", 1)[1]


@router.post("/", response_model=RoomOut)
def create_room(payload: RoomCreate, db: Session = Depends(get_db), authorization: str | None = Header(default=None)):
    token = parse_token(authorization)
    user = get_current_user(token, db)

    invite_code = secrets.token_urlsafe(8)[:12]
    room = Room(name=payload.name, invite_code=invite_code, owner_id=user.id)
    db.add(room)
    db.commit()
    db.refresh(room)

    participant = Participant(room_id=room.id, user_id=user.id, role="host", connected=False)
    db.add(participant)
    db.commit()

    return room


@router.get("/by-invite/{invite_code}", response_model=RoomOut)
def get_room_by_invite(invite_code: str, db: Session = Depends(get_db)):
    room = db.query(Room).filter(Room.invite_code == invite_code).first()
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")
    return room


@router.post("/join/{invite_code}")
def join_room(invite_code: str, db: Session = Depends(get_db), authorization: str | None = Header(default=None)):
    token = parse_token(authorization)
    user = get_current_user(token, db)

    room = db.query(Room).filter(Room.invite_code == invite_code).first()
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")

    exists = db.query(Participant).filter(Participant.room_id == room.id, Participant.user_id == user.id).first()
    if not exists:
        p = Participant(room_id=room.id, user_id=user.id)
        db.add(p)
        db.commit()

    return {"room_id": str(room.id), "invite_code": room.invite_code}


@router.get("/{room_id}/participants")
def list_participants(room_id: str, db: Session = Depends(get_db)):
    q = (
        db.query(Participant, User)
        .join(User, Participant.user_id == User.id)
        .filter(Participant.room_id == room_id)
    )
    items = []
    for p, u in q.all():
        items.append({
            "user_id": str(u.id),
            "display_name": u.display_name,
            "role": p.role.value if hasattr(p.role, 'value') else str(p.role),
            "connected": bool(p.connected),
            "mic_on": bool(getattr(p, 'mic_on', True)),
            "cam_on": bool(getattr(p, 'cam_on', True)),
            "screen_sharing": bool(getattr(p, 'screen_sharing', False)),
            "is_speaking": bool(getattr(p, 'is_speaking', False)),
            "raised_hand": bool(getattr(p, 'raised_hand', False)),
            "muted_by_moderator": bool(getattr(p, 'muted_by_moderator', False)),
        })
    return {"items": items}


@router.get("/{room_id}", response_model=RoomOut)
def get_room(room_id: str, db: Session = Depends(get_db)):
    room = db.get(Room, room_id)
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")
    return room


@router.get("/mine")
def my_rooms(db: Session = Depends(get_db), authorization: str | None = Header(default=None)):
    token = parse_token(authorization)
    me = get_current_user(token, db)
    rooms = db.query(Room).filter(Room.owner_id == me.id).order_by(Room.created_at.desc()).all()
    return [{"id": str(r.id), "name": r.name, "invite_code": r.invite_code} for r in rooms]


@router.get("/joined")
def joined_rooms(db: Session = Depends(get_db), authorization: str | None = Header(default=None)):
    token = parse_token(authorization)
    me = get_current_user(token, db)
    rooms = db.query(Room).join(Participant, Participant.room_id == Room.id).filter(Participant.user_id == me.id).order_by(Room.created_at.desc()).all()
    return [{"id": str(r.id), "name": r.name, "invite_code": r.invite_code} for r in rooms]


@router.post("/{room_id}/regenerate-invite")
def regenerate_invite(room_id: str, db: Session = Depends(get_db), authorization: str | None = Header(default=None)):
    token = parse_token(authorization)
    me = get_current_user(token, db)
    room = db.get(Room, room_id)
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")
    if room.owner_id != me.id:
        raise HTTPException(status_code=403, detail="Only owner can regenerate invite")
    new_invite = secrets.token_urlsafe(8)[:12]
    room.invite_code = new_invite
    db.commit()
    db.refresh(room)
    return {"invite_code": room.invite_code}


@router.delete("/{room_id}")
def delete_room(room_id: str, db: Session = Depends(get_db), authorization: str | None = Header(default=None)):
    token = parse_token(authorization)
    me = get_current_user(token, db)
    room = db.get(Room, room_id)
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")
    if room.owner_id != me.id:
        raise HTTPException(status_code=403, detail="Only owner can delete room")
    db.delete(room)
    db.commit()
    return {"status": "ok"}
