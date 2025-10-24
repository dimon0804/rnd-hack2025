from fastapi import APIRouter, Depends, HTTPException, Header
from pydantic import BaseModel, EmailStr, HttpUrl
from sqlalchemy.orm import Session
from ..db.session import get_db
from ..models import User, Participant
from ..core.security import create_access_token, hash_password, verify_password
from .auth import get_current_user

router = APIRouter()


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str
    display_name: str
    avatar_url: HttpUrl | None = None


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class UserOut(BaseModel):
    id: str
    email: str | None = None
    display_name: str
    avatar_url: str | None = None


class ProfileUpdate(BaseModel):
    display_name: str | None = None
    avatar_url: HttpUrl | None = None


def parse_token(authorization: str | None) -> str:
    if not authorization:
        raise HTTPException(status_code=401, detail="Missing Authorization header")
    if not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Invalid Authorization header")
    return authorization.split(" ", 1)[1]


@router.post("/register")
def register(payload: RegisterRequest, db: Session = Depends(get_db)):
    exists = db.query(User).filter(User.email == payload.email).first()
    if exists:
        raise HTTPException(status_code=409, detail="Email already registered")
    u = User(
        email=payload.email,
        password_hash=hash_password(payload.password),
        display_name=payload.display_name,
        avatar_url=str(payload.avatar_url) if payload.avatar_url else None,
    )
    db.add(u)
    db.commit()
    db.refresh(u)
    token = create_access_token(str(u.id), extra={"display_name": u.display_name})
    return {"access_token": token, "token_type": "bearer"}


@router.post("/login")
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    u = db.query(User).filter(User.email == payload.email).first()
    if not u or not u.password_hash or not verify_password(payload.password, u.password_hash):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    token = create_access_token(str(u.id), extra={"display_name": u.display_name})
    return {"access_token": token, "token_type": "bearer"}


@router.get("/me", response_model=UserOut)
def me(authorization: str | None = Header(default=None), db: Session = Depends(get_db)):
    token = parse_token(authorization)
    u = get_current_user(token, db)
    return UserOut(id=str(u.id), email=u.email, display_name=u.display_name, avatar_url=u.avatar_url)


@router.put("/me", response_model=UserOut)
def update_me(payload: ProfileUpdate, authorization: str | None = Header(default=None), db: Session = Depends(get_db)):
    token = parse_token(authorization)
    u = get_current_user(token, db)
    if payload.display_name is not None:
        u.display_name = payload.display_name
    if payload.avatar_url is not None:
        u.avatar_url = str(payload.avatar_url)
    db.commit()
    db.refresh(u)
    return UserOut(id=str(u.id), email=u.email, display_name=u.display_name, avatar_url=u.avatar_url)


@router.get("/me/rooms")
def my_rooms(authorization: str | None = Header(default=None), db: Session = Depends(get_db)):
    token = parse_token(authorization)
    u = get_current_user(token, db)
    # rooms I own
    from ..models import Room
    own = db.query(Room).filter(Room.owner_id == u.id).order_by(Room.created_at.desc()).all()
    return [{"id": str(r.id), "name": r.name, "invite_code": r.invite_code} for r in own]


@router.get("/me/rooms/joined")
def my_joined_rooms(authorization: str | None = Header(default=None), db: Session = Depends(get_db)):
    token = parse_token(authorization)
    u = get_current_user(token, db)
    from ..models import Room
    q = db.query(Room).join(Participant, Participant.room_id == Room.id).filter(Participant.user_id == u.id)
    rooms = q.order_by(Room.created_at.desc()).all()
    return [{"id": str(r.id), "name": r.name, "invite_code": r.invite_code} for r in rooms]
