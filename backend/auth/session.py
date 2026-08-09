"""
Server-side sessions backed by an opaque cookie value. The cookie itself is
just a random ID (HttpOnly, Secure, SameSite=Lax) -- the actual session
record (email, expiry) lives in the database, so a stolen cookie value alone
still requires the DB record to exist and be unexpired.
"""
from datetime import datetime, timedelta, timezone

from fastapi import Request, HTTPException, Response
from sqlalchemy.orm import Session as DBSession

from backend.config import get_settings
from backend.db.models import UserSession
from backend.db.session import get_db

settings = get_settings()
SESSION_COOKIE_NAME = "session_id"


def create_session(db: DBSession, response: Response, email: str) -> None:
    import uuid
    session_id = str(uuid.uuid4())
    record = UserSession(
        id=session_id,
        email=email,
        expires_at=datetime.now(timezone.utc) + timedelta(hours=settings.SESSION_TTL_HOURS),
    )
    db.add(record)
    db.commit()

    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=session_id,
        httponly=True,
        secure=settings.ENV == "production",
        samesite="lax",
        max_age=settings.SESSION_TTL_HOURS * 3600,
    )


def require_session(request: Request, db: DBSession = None) -> str:
    """FastAPI dependency: raises 401 if there's no valid session, else
    returns the logged-in user's email."""
    from backend.db.session import SessionLocal
    own_db = False
    if db is None:
        db = SessionLocal()
        own_db = True

    try:
        session_id = request.cookies.get(SESSION_COOKIE_NAME)
        if not session_id:
            raise HTTPException(status_code=401, detail="Not authenticated")

        record = db.query(UserSession).filter(UserSession.id == session_id).first()
        if not record or record.expires_at < datetime.now(timezone.utc):
            raise HTTPException(status_code=401, detail="Session expired")

        return record.email
    finally:
        if own_db:
            db.close()
