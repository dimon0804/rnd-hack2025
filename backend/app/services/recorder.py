import asyncio
import json
import os
import tempfile
from datetime import datetime
from typing import Dict

import aiohttp
from aiortc import RTCPeerConnection, RTCSessionDescription
from aiortc.contrib.media import MediaRecorder

from ..core.config import settings


class RoomRecorder:
    def __init__(self, room_id: str, token: str):
        self.room_id = room_id
        self.token = token
        self.ws = None  # type: aiohttp.ClientWebSocketResponse | None
        self.conn_id = None  # recorder's own conn id from welcome
        self.pcs: Dict[str, RTCPeerConnection] = {}
        self.recorders: Dict[str, MediaRecorder] = {}
        self.started_at: datetime | None = None
        self.output_path = os.path.join(tempfile.gettempdir(), f"recording_{room_id}_{int(datetime.utcnow().timestamp())}.mkv")
        self._stop = asyncio.Event()

    async def start(self):
        self.started_at = datetime.utcnow()
        url = f"{settings.ws_base_url.rstrip('/')}/ws/{self.room_id}?token={self.token}"
        async with aiohttp.ClientSession() as session:
            async with session.ws_connect(url) as ws:
                self.ws = ws
                # event loop
                async for msg in ws:
                    if msg.type == aiohttp.WSMsgType.TEXT:
                        data = json.loads(msg.data)
                        t = data.get("type")
                        if t == "welcome":
                            self.conn_id = data.get("conn_id")
                        elif t == "peers":
                            for p in data.get("items", []):
                                await self.ensure_pc(p.get("conn_id"))
                                await self.make_offer(p.get("conn_id"))
                        elif t == "join":
                            if data.get("conn_id") and data.get("conn_id") != self.conn_id:
                                await self.ensure_pc(data.get("conn_id"))
                                await self.make_offer(data.get("conn_id"))
                        elif t == "signal":
                            to = data.get("to_conn")
                            # ignore messages we sent
                            if to and to != self.conn_id:
                                continue
                            from_conn = data.get("from_conn")
                            if not from_conn:
                                continue
                            pc = await self.ensure_pc(from_conn)
                            if "sdp" in data and data["sdp"]:
                                sdp = data["sdp"]
                                desc = RTCSessionDescription(sdp["sdp"], sdp["type"])  # type: ignore
                                await pc.setRemoteDescription(desc)
                                if sdp["type"] == "offer":
                                    answer = await pc.createAnswer()
                                    await pc.setLocalDescription(answer)
                                    await self.send_signal(from_conn, {"sdp": {
                                        "type": pc.localDescription.type,
                                        "sdp": pc.localDescription.sdp,
                                    }})
                            elif "ice" in data and data["ice"]:
                                try:
                                    await pc.addIceCandidate(data["ice"])  # type: ignore
                                except Exception:
                                    pass
                        elif t == "leave":
                            cid = data.get("conn_id")
                            await self.close_pc(cid)
                    if self._stop.is_set():
                        break
        await self._finalize()

    async def stop(self):
        self._stop.set()
        # closing will be handled after loop exits

    async def _finalize(self):
        # stop all pcs and recorders, and return path
        for pc in list(self.pcs.values()):
            await pc.close()
        self.pcs.clear()
        for rec in list(self.recorders.values()):
            try:
                await rec.stop()
            except Exception:
                pass
        self.recorders.clear()

    async def ensure_pc(self, remote_conn_id: str) -> RTCPeerConnection:
        if remote_conn_id in self.pcs:
            return self.pcs[remote_conn_id]
        pc = RTCPeerConnection()
        # media sink per peer to allow incremental add
        recorder = MediaRecorder(self.output_path)
        self.recorders[remote_conn_id] = recorder

        @pc.on("track")
        async def on_track(track):
            try:
                recorder.addTrack(track)
                await recorder.start()
            except Exception:
                pass

        @pc.on("icecandidate")
        async def on_ice(ev):
            if ev:
                await self.send_signal(remote_conn_id, {"ice": ev})

        self.pcs[remote_conn_id] = pc
        return pc

    async def make_offer(self, remote_conn_id: str):
        pc = await self.ensure_pc(remote_conn_id)
        # Ensure we request media even before any remote SDP arrives
        try:
            # add recvonly transceivers once
            if not getattr(pc, 'getTransceivers', None) or len(pc.getTransceivers()) == 0:
                pc.addTransceiver('audio', direction='recvonly')
                pc.addTransceiver('video', direction='recvonly')
        except Exception:
            # best-effort; continue to create offer
            pass
        offer = await pc.createOffer()
        await pc.setLocalDescription(offer)
        await self.send_signal(remote_conn_id, {"sdp": {
            "type": pc.localDescription.type,
            "sdp": pc.localDescription.sdp,
        }})

    async def send_signal(self, to_conn: str, payload: dict):
        if not self.ws:
            return
        msg = {"type": "signal", "to_conn": to_conn}
        msg.update(payload)
        await self.ws.send_str(json.dumps(msg))
