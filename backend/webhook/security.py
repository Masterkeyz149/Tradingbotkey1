"""
TradingView alerts can include a custom header if you're on a paid plan with
webhook customization; if not, the shared secret can instead be embedded as
a field inside the JSON body itself (see pine script "webhook_secret" note
below) and checked here the same way. Either path uses constant-time
comparison to avoid timing attacks.
"""
import hmac

from fastapi import Header, HTTPException

from backend.config import get_settings

settings = get_settings()


def verify_shared_secret(x_webhook_secret: str | None = Header(default=None)) -> None:
    if not settings.WEBHOOK_SHARED_SECRET:
        # Fail closed: never allow an unauthenticated webhook, even in dev,
        # unless a secret has been explicitly configured.
        raise HTTPException(status_code=500, detail="Webhook secret not configured on server")

    if not x_webhook_secret or not hmac.compare_digest(x_webhook_secret, settings.WEBHOOK_SHARED_SECRET):
        raise HTTPException(status_code=401, detail="Invalid or missing webhook secret")
