"""
Phase 5 (optional): Telegram push for urgent pings when you're not looking
at the dashboard. Not the primary interface -- the dashboard is.

Wire this into webhook/router.py after a confirmed signal if/when you want
it: call notify_telegram(signal, verdict) right after the broadcast_new_signal
call. Left disconnected for now since it's optional and you may prefer email
or browser push instead -- say the word and I'll wire whichever you want.
"""
import httpx

from backend.config import get_settings

settings = get_settings()


def notify_telegram(symbol: str, direction: str, decision: str, rationale: str) -> None:
    if not settings.TELEGRAM_BOT_TOKEN or not settings.TELEGRAM_CHAT_ID:
        return  # not configured -- no-op

    text = f"*{symbol}* {direction} — *{decision}*\n{rationale}"
    url = f"https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}/sendMessage"
    try:
        httpx.post(url, json={
            "chat_id": settings.TELEGRAM_CHAT_ID,
            "text": text,
            "parse_mode": "Markdown",
        }, timeout=10)
    except httpx.HTTPError:
        pass  # best-effort secondary channel -- never let this break the primary flow
