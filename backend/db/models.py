import uuid

from sqlalchemy import Column, String, Float, Boolean, DateTime, JSON, ForeignKey, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from backend.db.session import Base


def gen_uuid() -> str:
    return str(uuid.uuid4())


class Signal(Base):
    """One row per incoming TradingView alert (after dedupe)."""
    __tablename__ = "signals"

    id = Column(String, primary_key=True, default=gen_uuid)
    event_id = Column(String, unique=True, index=True, nullable=False)  # dedupe key from Pine payload
    symbol = Column(String, index=True, nullable=False)
    direction = Column(String, nullable=False)  # bullish / bearish / crt_bullish / crt_bearish
    setup_timeframe = Column(String, nullable=False)
    price = Column(Float, nullable=False)
    raw_payload = Column(JSON, nullable=False)  # full structured payload, exactly as received
    received_at = Column(DateTime(timezone=True), server_default=func.now())

    verdict = relationship("Verdict", back_populates="signal", uselist=False)


class Verdict(Base):
    """LLM confirmation result for a signal, plus any manual override."""
    __tablename__ = "verdicts"

    id = Column(String, primary_key=True, default=gen_uuid)
    signal_id = Column(String, ForeignKey("signals.id"), unique=True, nullable=False)

    llm_decision = Column(String, nullable=False)  # CONFIRM / REJECT
    checklist = Column(JSON, nullable=False)  # {"htf_bias_aligned": true, ...}
    rationale = Column(Text, nullable=False)
    model_used = Column(String, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Manual override, if the user acts from the dashboard
    manual_decision = Column(String, nullable=True)  # APPROVE / REJECT / null
    manual_decided_at = Column(DateTime(timezone=True), nullable=True)
    manual_actor = Column(String, nullable=True)

    # Outcome, filled in later for R-multiple tracking / backtesting
    outcome_r_multiple = Column(Float, nullable=True)
    outcome_notes = Column(Text, nullable=True)

    signal = relationship("Signal", back_populates="verdict")


class AuditLog(Base):
    """Every login, decision, and manual override -- timestamp + actor."""
    __tablename__ = "audit_log"

    id = Column(String, primary_key=True, default=gen_uuid)
    actor = Column(String, nullable=False)  # email or "system"
    action = Column(String, nullable=False)  # "login", "manual_approve", "manual_reject", ...
    details = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class UserSession(Base):
    """Server-side session record backing the session cookie."""
    __tablename__ = "user_sessions"

    id = Column(String, primary_key=True, default=gen_uuid)
    email = Column(String, nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class MagicLinkToken(Base):
    """Short-lived, single-use tokens issued for email login."""
    __tablename__ = "magic_link_tokens"

    id = Column(String, primary_key=True, default=gen_uuid)
    email = Column(String, nullable=False)
    token_hash = Column(String, nullable=False, unique=True)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    used = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
