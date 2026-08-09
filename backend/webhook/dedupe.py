"""
TradingView can occasionally re-fire or double-deliver an alert. We dedupe
on event_id (built in Pine Script from timestamp+symbol+direction), which is
unique per genuine signal. A duplicate event_id is treated as a no-op, not
an error -- the webhook still returns 200 so TradingView doesn't retry.
"""
from sqlalchemy.orm import Session

from backend.db.models import Signal


def is_duplicate(db: Session, event_id: str) -> bool:
    return db.query(Signal.id).filter(Signal.event_id == event_id).first() is not None
