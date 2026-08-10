"""
Email magic-link login for a single-user dashboard.

Flow:
  1. User enters their email on /login.
  2. We generate a random token, store only its HASH + expiry in the DB,
     and email a link containing the raw token.
  3. User clicks the link -> we hash the presented token, look up the match,
     check expiry + not-already-used, then issue a session cookie.

Only AUTH_ALLOWED_EMAIL may request a link -- this is a single-user system,
not open signup.
"""
import hashlib
import logging
import secrets
from datetime import datetime, timedelta, timezone

import httpx
from sqlalchemy.orm import Session

from backend.config import get_settings
from backend.db.models import MagicLinkToken, AuditLog
from backend.logging_config import log_event

logger = logging.getLogger("auth.magic_link")
settings = get_settings()


def _hash_token(raw_token: str) -> str:
    return hashlib.sha256(raw_token.encode()).hexdigest()


def request_magic_link(db: Session, email: str) -> bool:
    """Returns True if a link was sent. Silently no-ops for unknown emails
    so we don't leak which addresses are valid."""
    if email.lower() != settings.AUTH_ALLOWED_EMAIL.lower():
        log_event(logger, "magic_link_requested_unknown_email", email=email)
        return False

    raw_token = secrets.token_urlsafe(32)
    record = MagicLinkToken(
        email=email,
        token_hash=_hash_token(raw_token),
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=settings.MAGIC_LINK_TTL_MINUTES),
    )
    db.add(record)
    db.commit()

    link = f"{settings.APP_BASE_URL}/auth/verify?token={raw_token}"
    _send_email(email, link)
    log_event(logger, "magic_link_sent", email=email)
    return True


def _send_email(to_email: str, link: str) -> None:
    """Sends via a transactional email provider (Resend example below).
    Swap the request body for Postmark/SES/etc. if you prefer a different
    provider -- the rest of the auth flow doesn't care."""
    if not settings.EMAIL_PROVIDER_API_KEY:
        # Dev fallback: log the link instead of emailing it.
        log_event(logger, f"magic_link_dev_mode_no_email_sent link={link}", link=link)
        return

    try:
        resp = httpx.post(
            "https://api.resend.com/emails",
            headers={"Authorization": f"Bearer {settings.EMAIL_PROVIDER_API_KEY}"},
            json={
                "from": settings.EMAIL_FROM,
                "to": [to_email],
                "subject": "Your trading dashboard sign-in link",
                "html": f"<p>Click to sign in (expires in {settings.MAGIC_LINK_TTL_MINUTES} min):</p>"
                        f'<p><a href="{link}">{link}</a></p>',
            },
            timeout=10,
        )
        resp.raise_for_status()
    except httpx.HTTPError as e:
        log_event(logger, "magic_link_email_send_failed", error=str(e))
        raise


def verify_magic_link(db: Session, raw_token: str) -> str | None:
    """Returns the email if the token is valid and unused, else None.
    Marks the token used on success (single-use)."""
    token_hash = _hash_token(raw_token)
    record = db.query(MagicLinkToken).filter(MagicLinkToken.token_hash == token_hash).first()

    if not record or record.used:
        return None
    if record.expires_at < datetime.now(timezone.utc):
        return None

    record.used = True
    db.add(AuditLog(actor=record.email, action="login", details={"method": "magic_link"}))
    db.commit()
    return record.email
