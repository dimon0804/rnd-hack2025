from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from ..db.session import get_db
from ..models import User
from ..schemas.auth import AnonymousAuthRequest, TokenResponse
from ..core.security import create_access_token, decode_token

router = APIRouter()

@router.post("/anonymous", response_model=TokenResponse)
def anonymous_login(payload: AnonymousAuthRequest, db: Session = Depends(get_db)):
    user = User(display_name=payload.display_name, avatar_url=str(payload.avatar_url) if payload.avatar_url else None)
    db.add(user)
    db.commit()
    db.refresh(user)
    token = create_access_token(str(user.id), extra={"display_name": user.display_name})
    return TokenResponse(access_token=token)


def get_current_user(token: str, db: Session) -> User:
    try:
        payload = decode_token(token)
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid token")
    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid token")
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    return user
