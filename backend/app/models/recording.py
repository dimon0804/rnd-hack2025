import uuid
from datetime import datetime
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy import DateTime, ForeignKey, String, Integer, Enum, Boolean
import enum
from ..db.session import Base


class RecordingStatus(str, enum.Enum):
    starting = "starting"
    recording = "recording"
    stopping = "stopping"
    completed = "completed"
    failed = "failed"


class Recording(Base):
    __tablename__ = "recordings"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    room_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("rooms.id", ondelete="CASCADE"), nullable=False)
    created_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    status: Mapped[RecordingStatus] = mapped_column(Enum(RecordingStatus), default=RecordingStatus.starting, nullable=False)
    storage_key: Mapped[str | None] = mapped_column(String(512), nullable=True)
    public_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)

    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
    stopped_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    duration_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
