from fastapi import APIRouter, Depends, HTTPException, Header
from pydantic import BaseModel
from sqlalchemy.orm import Session
from ..db.session import get_db
from ..models import KeyBundle
from .auth import get_current_user

router = APIRouter()

class PublishKeyBundle(BaseModel):
    identity_key: str
    pre_key: str | None = None


def parse_token(authorization: str | None) -> str:
    if not authorization:
        raise HTTPException(status_code=401, detail="Missing Authorization header")
    if not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Invalid Authorization header")
    return authorization.split(" ", 1)[1]


@router.post("/{room_id}")
def publish(room_id: str, payload: PublishKeyBundle, db: Session = Depends(get_db), authorization: str | None = Header(default=None)):
    token = parse_token(authorization)
    me = get_current_user(token, db)

    kb = db.query(KeyBundle).filter(KeyBundle.room_id == room_id, KeyBundle.user_id == me.id).first()
    if not kb:
        kb = KeyBundle(room_id=room_id, user_id=me.id, identity_key=payload.identity_key, pre_key=payload.pre_key)
        db.add(kb)
    else:
        kb.identity_key = payload.identity_key
        kb.pre_key = payload.pre_key
    db.commit()
    return {"status": "ok"}


@router.get("/{room_id}")
def list_bundles(room_id: str, db: Session = Depends(get_db)):
    bundles = db.query(KeyBundle).filter(KeyBundle.room_id == room_id).all()
    return [
        {
            "user_id": str(b.user_id),
            "identity_key": b.identity_key,
            "pre_key": b.pre_key,
        }
        for b in bundles
    ]
