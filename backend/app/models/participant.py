import uuid
from datetime import datetime
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy import String, DateTime, ForeignKey, Boolean, Enum
import enum
from ..db.session import Base


class Role(str, enum.Enum):
    host = "host"
    moderator = "moderator"
    guest = "guest"


class Participant(Base):
    __tablename__ = "participants"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    room_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("rooms.id", ondelete="CASCADE"), nullable=False)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)

    role: Mapped[Role] = mapped_column(Enum(Role), default=Role.guest, nullable=False)

    connected: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    mic_on: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    cam_on: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    screen_sharing: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_speaking: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    raised_hand: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    muted_by_moderator: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    joined_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
