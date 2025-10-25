from typing import Dict, List
import uuid
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query
from ..core.security import decode_token
from ..db.session import SessionLocal
from ..models import Participant, CallLog

router = APIRouter()


class Connection:
    def __init__(self, ws: WebSocket, user_id: str, display_name: str | None):
        self.ws = ws
        self.user_id = user_id
        self.display_name = display_name
        self.conn_id = str(uuid.uuid4())


class RoomHub:
    def __init__(self):
        self.rooms: Dict[str, List[Connection]] = {}
        # track active call log ids per (room_id, user_id)
        self.active_logs: Dict[tuple[str, str], str] = {}

    async def connect(self, room_key: str, conn: Connection):
        await conn.ws.accept()
        self.rooms.setdefault(room_key, []).append(conn)

    async def disconnect(self, room_key: str, conn: Connection):
        conns = self.rooms.get(room_key, [])
        if conn in conns:
            conns.remove(conn)
        if not conns:
            self.rooms.pop(room_key, None)

    async def broadcast(self, room_key: str, message: dict, skip_conn: Connection | None = None):
        for c in list(self.rooms.get(room_key, [])):
            if skip_conn is not None and c is skip_conn:
                continue
            try:
                await c.ws.send_json(message)
            except Exception:
                # drop dead connections silently
                conns = self.rooms.get(room_key, [])
                if c in conns:
                    conns.remove(c)
                if not conns:
                    self.rooms.pop(room_key, None)

    def find_by_conn_id(self, room_key: str, conn_id: str) -> Connection | None:
        for c in self.rooms.get(room_key, []):
            if c.conn_id == conn_id:
                return c
        return None


hub = RoomHub()


@router.websocket("/{room_id}")
async def websocket_endpoint(websocket: WebSocket, room_id: str, token: str = Query(...)):
    try:
        payload = decode_token(token)
        user_id = payload.get("sub")
        display_name = payload.get("display_name")
        is_recorder = bool(payload.get("recorder")) or (isinstance(user_id, str) and user_id.startswith("recorder:"))
    except Exception:
        await websocket.close(code=4401)
        return

    room_key = str(room_id)
    conn = Connection(websocket, user_id, display_name)
    await hub.connect(room_key, conn)

    # Mark participant as connected in DB (skip for recorder)
    if not is_recorder:
        db = SessionLocal()
        try:
            # ensure participant row exists
            p = db.query(Participant).filter(Participant.room_id == room_id, Participant.user_id == user_id).first()
            if not p:
                p = Participant(room_id=room_id, user_id=user_id)
                db.add(p)
            p.connected = True
            db.commit()
            # start call log
            cl = CallLog(room_id=room_id, user_id=user_id)
            db.add(cl)
            db.commit()
            db.refresh(cl)
            hub.active_logs[(room_id, user_id)] = str(cl.id)
        finally:
            db.close()

    # send welcome with own conn_id
    await conn.ws.send_json({"type": "welcome", "conn_id": conn.conn_id})
    # send current peers to newcomer
    current = [
        {"user_id": c.user_id, "conn_id": c.conn_id, "display_name": c.display_name}
        for c in hub.rooms.get(room_key, []) if c is not conn and not (isinstance(c.user_id, str) and c.user_id.startswith("recorder:"))
    ]
    if current:
        await conn.ws.send_json({"type": "peers", "items": current})
    # notify others (skip for recorder)
    if not is_recorder:
        await hub.broadcast(room_key, {"type": "join", "user_id": user_id, "display_name": display_name, "conn_id": conn.conn_id}, skip_conn=conn)
        await hub.broadcast(room_key, {"type": "participant_state", "user_id": user_id, "connected": True})

    try:
        while True:
            data = await websocket.receive_json()
            t = data.get("type")
            if t == "signal":
                # expected: {type:"signal", to_conn:"...", sdp|ice:...}
                msg = {"type": "signal", "from": user_id, "from_conn": conn.conn_id}
                msg.update(data)
                # optionally direct delivery if to_conn provided
                to_conn_id = data.get("to_conn")
                if to_conn_id:
                    target = hub.find_by_conn_id(room_key, to_conn_id)
                    if target:
                        try:
                            await target.ws.send_json(msg)
                        except Exception:
                            # if target is dead, drop it
                            await hub.disconnect(room_key, target)
                    continue
                # else broadcast to room (clients filter)
                await hub.broadcast(room_key, msg, skip_conn=conn)
            elif t == "state":
                # update participant state and broadcast
                if not is_recorder:
                    db2 = SessionLocal()
                    try:
                        p = db2.query(Participant).filter(Participant.room_id == room_id, Participant.user_id == user_id).first()
                        if p:
                            for f in ("mic_on", "cam_on", "screen_sharing", "is_speaking", "raised_hand"):
                                if f in data:
                                    setattr(p, f, bool(data[f]))
                            db2.commit()
                        await hub.broadcast(room_key, {"type": "participant_state", "user_id": user_id, **{k: data[k] for k in data if k != 'type'}})
                    finally:
                        db2.close()
    except WebSocketDisconnect:
        await hub.disconnect(room_key, conn)
        # mark disconnected in DB (skip for recorder)
        if not is_recorder:
            db = SessionLocal()
            try:
                p = db.query(Participant).filter(Participant.room_id == room_id, Participant.user_id == user_id).first()
                if p:
                    p.connected = False
                    db.commit()
                # finish call log
                key = (room_id, user_id)
                log_id = hub.active_logs.pop(key, None)
                if log_id:
                    cl = db.get(CallLog, log_id)
                    if cl and not cl.left_at:
                        from datetime import datetime, timezone
                        cl.left_at = datetime.now(timezone.utc)
                        joined = cl.joined_at
                        if joined is not None and joined.tzinfo is None:
                            joined = joined.replace(tzinfo=timezone.utc)
                        if joined is not None:
                            cl.duration_seconds = int((cl.left_at - joined).total_seconds())
                        db.commit()
            finally:
                db.close()
            await hub.broadcast(room_key, {"type": "leave", "user_id": user_id, "conn_id": conn.conn_id})
            await hub.broadcast(room_key, {"type": "participant_state", "user_id": user_id, "connected": False})
