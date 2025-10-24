import time
from typing import Optional
import bcrypt
import jwt
from ..core.config import settings


def hash_password(password: str) -> str:
    salt = bcrypt.gensalt(rounds=12)
    return bcrypt.hashpw(password.encode('utf-8'), salt).decode('utf-8')


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode('utf-8'), password_hash.encode('utf-8'))
    except Exception:
        return False


def create_access_token(sub: str, extra: Optional[dict] = None, expires_minutes: Optional[int] = None) -> str:
    now = int(time.time())
    exp = now + 60 * (expires_minutes or settings.access_token_expire_minutes)
    payload = {"sub": sub, "iat": now, "exp": exp}
    if extra:
        payload.update(extra)
    token = jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)
    return token


def decode_token(token: str) -> dict:
    return jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
