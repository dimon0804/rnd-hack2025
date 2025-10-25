# HackRTC API (Полная шпаргалка для фронта)

Base URL (local): http://<host>:8000
Base URL (prod):  https://api-hack2025.clv-digital.tech
Все ответы — JSON. Авторизация: `Authorization: Bearer <JWT>`.

## Быстрый старт (prod)
- **Проверка здоровья**
  ```bash
  curl -sS https://api-hack2025.clv-digital.tech/health
  ```
  Примечание: `HEAD` запрос (`curl -I`) может вернуть 405, используйте `GET`.
- **Анонимная аутентификация**
  ```bash
  curl -sS -X POST \
    -H 'Content-Type: application/json' \
    -d '{"display_name":"Alice","avatar_url":"https://..."}' \
    https://api-hack2025.clv-digital.tech/auth/anonymous
  ```
  Ответ: `{ "access_token": "<JWT>", "token_type": "bearer" }`
- **Создание комнаты**
  ```bash
  TOKEN=<JWT>
  curl -sS -X POST \
    -H "Authorization: Bearer $TOKEN" \
    -H 'Content-Type: application/json' \
    -d '{"name":"Team call"}' \
    https://api-hack2025.clv-digital.tech/rooms/
  ```

## Аутентификация
- `POST /auth/anonymous`
  - Body:
```json
{ "display_name": "Alice", "avatar_url": "https://..." }
```
  - 200:
```json
{ "access_token": "<JWT>", "token_type": "bearer" }
```

- `POST /users/register`
  - Body:
```json
{ "email": "a@b.c", "password": "secret", "display_name": "Alice", "avatar_url": "https://..." }
```
  - 200:
```json
{ "access_token": "<JWT>", "token_type": "bearer" }
```

- `POST /users/login`
  - Body:
```json
{ "email": "a@b.c", "password": "secret" }
```
  - 200: токен как выше.

- `GET /users/me`
  - 200:
```json
{ "id": "<uuid>", "email": "a@b.c", "display_name": "Alice", "avatar_url": "https://..." }
```

- `PUT /users/me`
  - Body (partial):
```json
{ "display_name": "New", "avatar_url": "https://..." }
```
  - 200: профиль как в GET.

- `GET /users/me/rooms`
  - 200: массив моих комнат (я владелец)
```json
[{ "id": "<uuid>", "name": "Team", "invite_code": "abcd" }]
```

- `GET /users/me/rooms/joined`
  - 200: массив комнат, где я участник (не обязательно владелец).

## Комнаты
- `POST /rooms/` (auth)
  - Body:
```json
{ "name": "Team call" }
```
  - 200:
```json
{ "id": "<uuid>", "name": "Team call", "invite_code": "abcd1234" }
```

- `GET /rooms/{room_id}` → `RoomOut`

- `GET /rooms/by-invite/{invite_code}` → `RoomOut`

- `POST /rooms/join/{invite_code}` (auth)
  - 200:
```json
{ "room_id": "<uuid>", "invite_code": "abcd1234" }
```

- `GET /rooms/{room_id}/participants`
  - 200:
```json
{
  "items": [
    {"user_id":"<uuid>","display_name":"Alice","role":"host|moderator|guest","connected":true,
     "mic_on":true,"cam_on":true,"screen_sharing":false,
     "is_speaking":false,"raised_hand":false,"muted_by_moderator":false}
  ]
}
```

- `GET /rooms/mine` (auth) → мои комнаты (owner)
- `GET /rooms/joined` (auth) → комнаты, где я участник
- `POST /rooms/{room_id}/regenerate-invite` (owner)
  - 200: `{ "invite_code": "..." }`
- `DELETE /rooms/{room_id}` (owner) → `{ "status": "ok" }`

## Чат
- `GET /chat/{room_id}`
  - 200:
```json
[{"id":"<uuid>","user_id":"<uuid>","ciphertext":"base64","created_at":"ISO"}]
```

- `POST /chat/{room_id}` (auth)
  - Body:
```json
{ "ciphertext": "base64" }
```
  - 200: `{ "id": "<uuid>" }`
  - Валид. ошибки: 422 если пусто/слишком длинно (>4000).

## Модерация (auth)
- `POST /moderation/{room_id}/mute/{target_user_id}` → `{ "status": "ok" }`
- `POST /moderation/{room_id}/unmute/{target_user_id}`
- `POST /moderation/{room_id}/kick/{target_user_id}`
- `POST /moderation/{room_id}/promote/{target_user_id}` (только host)
- `POST /moderation/{room_id}/demote/{target_user_id}` (только host)

## Ключи шифрования
- `POST /keys/{room_id}` (auth)
  - Body:
```json
{ "identity_key": "...", "pre_key": "..." }
```
  - 200: `{ "status": "ok" }`
- `GET /keys/{room_id}` → массив бандлов:
```json
[{"user_id":"<uuid>","identity_key":"...","pre_key":"..."}]
```

## Записи (реальные)
- `POST /recordings/{room_id}/start` (auth, host/moderator)
  - 200: `{ "status": "started", "recording_id": "<uuid>" }`
- `POST /recordings/{room_id}/stop` (auth, host/moderator)
  - 200: `{ "status": "completed|...", "recording_id": "<uuid>", "url": "https://.../file.mkv" }`
- `GET /recordings/{room_id}` (auth, участник)
  - 200:
```json
[{"id":"<uuid>","status":"completed","url":"https://...","started_at":"ISO","stopped_at":"ISO|null","duration_seconds":123}]
```

## WebSocket (сигналинг и состояния)
- URL (local): `ws://<host>:8000/ws/{room_id}?token=<JWT>`
- URL (prod):  `wss://api-hack2025.clv-digital.tech/ws/{room_id}?token=<JWT>`
- От сервера:
  - `welcome`: `{ "type":"welcome","conn_id":"<uuid>" }`
  - `peers`: `{ "type":"peers","items":[{"user_id":"...","conn_id":"...","display_name":"..."}] }`
  - `join`: `{ "type":"join","user_id":"...","display_name":"...","conn_id":"..." }`
  - `leave`: `{ "type":"leave","user_id":"...","conn_id":"..." }`
  - `signal`: `{ "type":"signal","from":"<user_id>","from_conn":"<conn_id>","to_conn":"?","sdp|ice":{...} }`
  - `participant_state`: `{ "type":"participant_state","user_id":"...", <partial states> }`
  - `chat`: `{ "type":"chat","room_id":"...","msg":{...} }`
- От клиента:
  - SDP/ICE (адресно): `{ "type":"signal","to_conn":"<target_conn_id>","sdp|ice":{...} }`
  - SDP (эфир): `{ "type":"signal","sdp":{...} }`
  - Состояния: `{ "type":"state", "mic_on":true|false, "cam_on":true|false, "screen_sharing":true|false, "is_speaking":true|false, "raised_hand":true|false }`

### Пример подключения к WS (prod)
```js
const token = '<JWT>';
const roomId = '<uuid>';
const ws = new WebSocket(`wss://api-hack2025.clv-digital.tech/ws/${roomId}?token=${token}`);
ws.onopen = () => console.log('ws open');
ws.onmessage = (e) => console.log('ws message', e.data);
ws.onclose = () => console.log('ws close');
```

## Коды ответов
- 200/201 — успех; 401 — неавторизован; 403 — нет прав; 404 — не найдено; 409 — конфликт (email занят); 422 — валидация.

## Примечания
- Use REST chat for persistence; WS "chat" events arrive to all connected clients in the room.
