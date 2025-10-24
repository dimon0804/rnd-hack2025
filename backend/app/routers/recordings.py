import asyncio
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Header
from sqlalchemy.orm import Session
from ..db.session import get_db
from ..models import Room, Participant, Recording, RecordingStatus
from ..core.security import create_access_token
from ..core.config import settings
from ..services.recorder import RoomRecorder
from .auth import get_current_user
from ..lib.s3 import upload_fileobj

router = APIRouter()

# in-process recorder manager (per room)
_recorders: dict[str, tuple[asyncio.Task, RoomRecorder, str]] = {}


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


@router.post("/{room_id}/start")
async def start_recording(room_id: str, db: Session = Depends(get_db), authorization: str | None = Header(default=None)):
    token = parse_token(authorization)
    me = get_current_user(token, db)
    room = db.get(Room, room_id)
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")
    require_role(db, room_id, me.id)
    if room_id in _recorders:
        raise HTTPException(status_code=400, detail="Recording already running")

    # create DB record
    rec = Recording(room_id=room.id, created_by=me.id, status=RecordingStatus.starting)
    db.add(rec)
    db.commit()
    db.refresh(rec)

    # use owner's token to connect recorder as a participant
    service_token = create_access_token(str(me.id), extra={"display_name": me.display_name})
    rr = RoomRecorder(room_id, service_token)

    async def run():
        try:
            rec.status = RecordingStatus.recording
            db.commit()
            await rr.start()
            # after stop/finalize
            rec.status = RecordingStatus.stopping
            db.commit()
            # upload to S3
            with open(rr.output_path, "rb") as f:
                key = f"recordings/{room_id}/{int(datetime.utcnow().timestamp())}.mkv"
                url = upload_fileobj(f, key, content_type="video/x-matroska")
            rec.public_url = url
            rec.storage_key = key
            rec.status = RecordingStatus.completed
            rec.stopped_at = datetime.utcnow()
            if rr.started_at:
                rec.duration_seconds = int((rec.stopped_at - rr.started_at).total_seconds())
            db.commit()
        except Exception:
            rec.status = RecordingStatus.failed
            db.commit()
        finally:
            _recorders.pop(room_id, None)

    task = asyncio.create_task(run())
    _recorders[room_id] = (task, rr, str(rec.id))
    return {"status": "started", "recording_id": str(rec.id)}


@router.post("/{room_id}/stop")
async def stop_recording(room_id: str, db: Session = Depends(get_db), authorization: str | None = Header(default=None)):
    token = parse_token(authorization)
    me = get_current_user(token, db)
    require_role(db, room_id, me.id)
    entry = _recorders.get(room_id)
    if not entry:
        raise HTTPException(status_code=404, detail="Recording not running")
    task, rr, rec_id = entry
    await rr.stop()
    await task
    rec = db.get(Recording, rec_id)
    return {"status": rec.status.value if rec else "unknown", "recording_id": rec_id, "url": rec.public_url if rec else None}


@router.get("/{room_id}")
async def list_recordings(room_id: str, db: Session = Depends(get_db), authorization: str | None = Header(default=None)):
    # anyone in room can view recordings list
    token = parse_token(authorization)
    me = get_current_user(token, db)
    p = db.query(Participant).filter(Participant.room_id == room_id, Participant.user_id == me.id).first()
    if not p:
        raise HTTPException(status_code=403, detail="Not in room")
    recs = db.query(Recording).filter(Recording.room_id == room_id).order_by(Recording.started_at.desc()).all()
    return [{
        "id": str(r.id),
        "status": r.status.value,
        "url": r.public_url,
        "started_at": r.started_at.isoformat(),
        "stopped_at": r.stopped_at.isoformat() if r.stopped_at else None,
        "duration_seconds": r.duration_seconds,
    } for r in recs]
