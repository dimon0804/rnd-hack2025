# HackRTC Backend — Документация (RU)

Производственный бэкенд видеокомнат для хакатона.

Стек: FastAPI, Pydantic v2, SQLAlchemy 2.0, Alembic, PostgreSQL, JWT, WebSockets. Полностью в Docker.

## Быстрый запуск (Docker)

1) Скопируйте env
```
cp .env.example .env
```
2) Запуск
```
docker compose up --build
```
3) Доступ
- API: http://localhost:8000
- WS:  ws://localhost:8000/ws/{room_id}?token=...

## Локальный запуск (без Docker)

Требуется Python 3.11+ и Postgres 15+.
```
python -m venv .venv
# Windows
. .venv\Scripts\activate
pip install -r requirements.txt
uvicorn backend.app.main:app --reload
```
Настройте `.env` по образцу `.env.example`.

## Переменные окружения

- `DATABASE_URL` (пример: `postgresql+psycopg://app:app@db:5432/app`)
- `JWT_SECRET`, `JWT_ALGORITHM`, `ACCESS_TOKEN_EXPIRE_MINUTES`
- `APP_NAME`, `APP_ENV`, `APP_DEBUG`

## База данных и миграции

Таблицы создаются автоматически на старте (для dev/демо). Для прод/командной работы фиксируйте схему через Alembic:
```
alembic revision --autogenerate -m "init"
alembic upgrade head
```
В Docker-контейнере:
```
docker compose exec api bash
alembic revision --autogenerate -m "init"
alembic upgrade head
```

## Обзор API

- Здоровье: `GET /health`
- Аутентификация: `POST /auth/anonymous` → `{ access_token }`
- Комнаты:
  - `POST /rooms/` → `{ id, name, invite_code }`
  - `GET /rooms/by-invite/{invite_code}`
  - `POST /rooms/join/{invite_code}`
- Чат:
  - `GET /chat/{room_id}` → список сообщений (ciphertext)
  - `POST /chat/{room_id}` → `{ ciphertext }`
- WebSocket сигналинг: `GET /ws/{room_id}?token=...`
- Модерация:
  - `POST /moderation/{room_id}/mute|unmute|kick|promote|demote/{target_user_id}`
- Ключи (E2EE чат):
  - `POST /keys/{room_id}` → публикация `{ identity_key, pre_key? }`
  - `GET /keys/{room_id}` → список бандлов

Заголовок авторизации: `Authorization: Bearer <token>`

## Протокол WebSocket (сигналинг)

Подключение:
```
GET /ws/{room_id}?token=<JWT>
```
Сервер рассылает:
```
{ "type": "join",  "user_id", "display_name" }
{ "type": "signal", "from", ...payload }
{ "type": "leave", "user_id" }
```
Клиент отправляет:
```
{ "type": "signal", "to": "<userId>", "sdp": {...} }
# или
{ "type": "signal", "to": "<userId>", "ice": {...} }
```

## Безопасность и E2EE (чат)

- Хранится только шифртекст `messages.content_ciphertext`.
- Обмен ключами — через `POST/GET /keys/{room_id}` (клиент-side криптология).
- Для хакатона допустим общий симметричный ключ комнаты; для прод — X3DH/Double Ratchet.

## Замечания по разработке

- Модели: `backend/app/models/`
- Сессия/БД: `backend/app/db/session.py`
- Роутеры: `backend/app/routers/`
- Настройки: `backend/app/core/config.py` (`.env`)

## Тестирование (примеры)
```
http :8000/health
http POST :8000/auth/anonymous display_name=Alice
http POST :8000/rooms/ Authorization:"Bearer <TOKEN>" name=Demo
http :8000/rooms/by-invite/<INVITE>
```

## Лицензия

MIT (для хакатона)
