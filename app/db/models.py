from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class CallSession(Base):
    __tablename__ = "call_sessions"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    caller_number: Mapped[str] = mapped_column(String(32))
    livekit_room: Mapped[str] = mapped_column(String(128))
    stage: Mapped[str] = mapped_column(String(32), default="greeting")
    hubspot_contact_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    hubspot_deal_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    calcom_booking_uid: Mapped[str | None] = mapped_column(String(128), nullable=True)
    lead_score: Mapped[str | None] = mapped_column(String(16), nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    ended_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    duration_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)

    messages: Mapped[list["CallMessage"]] = relationship(
        "CallMessage", back_populates="session", cascade="all, delete-orphan"
    )


class CallMessage(Base):
    __tablename__ = "call_messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("call_sessions.id", ondelete="CASCADE")
    )
    role: Mapped[str] = mapped_column(String(16))  # user | assistant
    content: Mapped[str] = mapped_column(Text)
    timestamp: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)

    session: Mapped["CallSession"] = relationship("CallSession", back_populates="messages")
