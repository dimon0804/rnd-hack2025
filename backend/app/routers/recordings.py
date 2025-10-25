import asyncio
import logging
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Header
from sqlalchemy.orm import Session
from ..db.session import get_db, SessionLocal
from ..models import Room, Participant, Recording, RecordingStatus
from ..core.security import create_access_token
from ..core.config import settings
from ..services.recorder import RoomRecorder
from .auth import get_current_user
from ..lib.s3 import upload_fileobj

router = APIRouter()
logger = logging.getLogger(__name__)
 
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
    rec_id = str(rec.id)

    # issue a special service token for recorder to avoid affecting UI/participants
    service_sub = f"recorder:{room_id}"
    service_token = create_access_token(service_sub, extra={"display_name": "Recorder", "recorder": True})
    # create initial recorder instance and store reference for stop/status
    rr = RoomRecorder(room_id, service_token)
    _recorders[room_id] = (None, rr, str(rec.id))  # type: ignore

    async def run():
        try:
            db2 = SessionLocal()
            try:
                rec2 = db2.get(Recording, rec_id)
                if rec2:
                    rec2.status = RecordingStatus.recording
                    if not getattr(rec2, "started_at", None):
                        rec2.started_at = datetime.utcnow()
                    db2.commit()
                logger.info("recording.worker_started room_id=%s recording_id=%s", room_id, rec_id)
                await rr.start()
                # after stop/finalize
                rec2 = db2.get(Recording, rec_id)
                if rec2:
                    rec2.status = RecordingStatus.stopping
                    db2.commit()
                # upload to S3 (if configured)
                url = None
                key = None
                try:
                    if settings.s3_bucket and settings.s3_endpoint and settings.s3_access_key and settings.s3_secret_key:
                        with open(rr.output_path, "rb") as f:
                            key = f"recordings/{room_id}/{int(datetime.utcnow().timestamp())}.mkv"
                            url = upload_fileobj(f, key, content_type="video/x-matroska")
                        logger.info("recording.uploaded room_id=%s recording_id=%s key=%s url=%s", room_id, rec_id, key, url)
                    else:
                        logger.warning("recording.s3_not_configured room_id=%s recording_id=%s path=%s", room_id, rec_id, rr.output_path)
                except Exception:
                    logger.exception("recording.upload_failed room_id=%s recording_id=%s path=%s", room_id, rec_id, rr.output_path)
                rec2 = db2.get(Recording, rec_id)
                if rec2:
                    rec2.public_url = url
                    rec2.storage_key = key
                    rec2.status = RecordingStatus.completed if url or not settings.s3_bucket else RecordingStatus.failed
                    rec2.stopped_at = datetime.utcnow()
                    if rr.started_at:
                        rec2.duration_seconds = int((rec2.stopped_at - rr.started_at).total_seconds())
                    db2.commit()
                logger.info("recording.worker_finished room_id=%s recording_id=%s status=%s", room_id, rec_id, rec2.status.value if rec2 else "unknown")
            finally:
                db2.close()
        except Exception:
            db3 = SessionLocal()
            try:
                rec3 = db3.get(Recording, rec_id)
                if rec3:
                    rec3.status = RecordingStatus.failed
                    db3.commit()
            finally:
                db3.close()
        finally:
            # keep registry entry until explicit stop to allow client to fetch status/stop
            pass

    task = asyncio.create_task(run())
    _recorders[room_id] = (task, rr, rec_id)
    return {"status": "started", "recording_id": rec_id}


@router.post("/{room_id}/stop")
async def stop_recording(room_id: str, db: Session = Depends(get_db), authorization: str | None = Header(default=None)):
    token = parse_token(authorization)
    me = get_current_user(token, db)
    require_role(db, room_id, me.id)
    entry = _recorders.get(room_id)
    if not entry:
        raise HTTPException(status_code=404, detail="Recording not running")
    task, rr, rec_id = entry
    logger.info("recording.stop requested room_id=%s by user_id=%s recording_id=%s", room_id, me.id, rec_id)
    try:
        await rr.stop()
    except Exception:
        # stopping is best-effort
        logger.exception("recording.stop_error room_id=%s recording_id=%s", room_id, rec_id)
    if task and not task.done():
        await task
    rec = db.get(Recording, rec_id)
    # cleanup registry entry after stop completes
    _recorders.pop(room_id, None)
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


@router.get("/{room_id}/status")
async def recording_status(room_id: str):
    entry = _recorders.get(room_id)
    if not entry:
        return {"room_id": room_id, "running": False}
    task, rr, rec_id = entry
    return {
        "room_id": room_id,
        "running": not task.done(),
        "recording_id": rec_id,
        "started_at": rr.started_at.isoformat() if getattr(rr, "started_at", None) else None,
        "output_path": rr.output_path,
    }
