# HackRTC API Mini Doc (for Frontend)

Base URL: http://<host>:8000
All endpoints return JSON.

Auth: Anonymous JWT
- POST /auth/anonymous
  - Body:
    {
      "display_name": "Alice",
      "avatar_url": "https://..." // optional
    }
  - 200 → {
    "access_token": "<JWT>"
  }
- Use the token as Authorization: Bearer <JWT> for protected endpoints and WS.

Rooms
- POST /rooms/ (auth required)
  - Body: { "name": "Team call" }
  - 200 → { "id": "<room_id>", "name": "Team call", "invite_code": "abcd1234" }
- GET /rooms/by-invite/{invite_code}
  - 200 → { "id": "<room_id>", "name": "...", "invite_code": "..." }
- POST /rooms/join/{invite_code} (auth required)
  - 200 → { "room_id": "<room_id>", "invite_code": "..." }
- GET /rooms/{room_id}/participants
  - 200 → { "items": [ { "user_id": "...", "display_name": "...", "role": "host|moderator|guest", "connected": true|false } ] }

Chat
- GET /chat/{room_id}
  - 200 → [ { "id": "...", "user_id": "...", "ciphertext": "...", "created_at": "ISO" } ]
- POST /chat/{room_id} (auth required)
  - Body: { "ciphertext": "..." }
  - 200 → { "id": "..." }
  - Validations: ciphertext required, max length 4000.

WebSocket Signaling
- URL: ws://<host>:8000/ws/{room_id}?token=<JWT>
- Messages are JSON.

Inbound from server (examples)
- welcome: { "type": "welcome", "conn_id": "<your_conn_id>" }
- peers:   { "type": "peers", "items": [ { "user_id": "...", "conn_id": "...", "display_name": "..." }, ... ] }
- join:    { "type": "join", "user_id": "...", "display_name": "...", "conn_id": "..." }
- leave:   { "type": "leave", "user_id": "...", "conn_id": "..." }
- signal:  { "type": "signal", "from": "<user_id>", "from_conn": "<conn_id>", "to_conn": "<optional>", "sdp"|"ice": { ... } }
- participant_state: { "type": "participant_state", "user_id": "...", "connected": true|false }
- chat (realtime): { "type": "chat", "room_id": "...", "msg": { "id": "...", "user_id": "...", "ciphertext": "...", "created_at": "ISO" } }

Outbound to server (from client)
- signal (direct to peer): { "type": "signal", "to_conn": "<target_conn_id>", "sdp": { ... } }
- signal (broadcast):      { "type": "signal", "sdp": { ... } }
- signal (ICE):            { "type": "signal", "to_conn": "<target_conn_id>", "ice": { ... } }

Notes
- Signaling is transport only; run full WebRTC setup on the client (add tracks, create offers/answers, ICE).
- Use REST chat for persistence; WS "chat" events arrive to all connected clients in the room.
