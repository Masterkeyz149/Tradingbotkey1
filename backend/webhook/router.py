import logging

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import ValidationError
from sqlalchemy.orm import Session

from backend.confirmation.llm_client import get_confirmation, LLMConfirmationError
from backend.dashboard.ws import broadcast_new_signal
from backend.db.models import Signal, Verdict, AuditLog
from backend.db.session import get_db
from backend.logging_config import log_event
from backend.rate_limit import RateLimiter
from backend.webhook.dedupe import is_duplicate
from backend.webhook.schema import TradingViewSignal
from backend.webhook.security import verify_shared_secret
from backend.config import get_settings

router = APIRouter()
logger = logging.getLogger("webhook")
settings = get_settings()

_webhook_limiter = RateLimiter(max_calls=settings.WEBHOOK_RATE_LIMIT_PER_MIN, per_seconds=60)
_llm_limiter = RateLimiter(max_calls=settings.LLM_RATE_LIMIT_PER_MIN, per_seconds=60)


@router.post("/webhook/tradingview", dependencies=[Depends(verify_shared_secret)])
async def receive_tradingview_alert(request: Request, db: Session = Depends(get_db)):
    if not _webhook_limiter.allow():
        raise HTTPException(status_code=429, detail="Webhook rate limit exceeded")

    body = await request.json()

    # 1. Strict schema validation -- reject malformed/out-of-range payloads outright.
    try:
        signal_data = TradingViewSignal(**body)
    except ValidationError as e:
        log_event(logger, "webhook_payload_rejected", error=str(e))
        raise HTTPException(status_code=422, detail=f"Payload failed validation: {e}")

    # 2. Idempotent dedupe -- return 200 without reprocessing a repeat delivery.
    if is_duplicate(db, signal_data.event_id):
        log_event(logger, "webhook_duplicate_ignored", event_id=signal_data.event_id)
        return {"status": "duplicate_ignored"}

    payload_dict = signal_data.model_dump()

    signal = Signal(
        event_id=signal_data.event_id,
        symbol=signal_data.symbol,
        direction=signal_data.direction,
        setup_timeframe=signal_data.setup_timeframe,
        price=signal_data.price,
        raw_payload=payload_dict,
    )
    db.add(signal)
    db.commit()
    db.refresh(signal)

    log_event(logger, "signal_received", event_id=signal.event_id, symbol=signal.symbol, direction=signal.direction)

    # 3. LLM confirmation -- rate-limited to control cost/abuse.
    if not _llm_limiter.allow():
        log_event(logger, "llm_rate_limited_skipping_confirmation", event_id=signal.event_id)
        raise HTTPException(status_code=429, detail="LLM confirmation rate limit exceeded")

    try:
        llm_verdict = get_confirmation(payload_dict)
    except LLMConfirmationError as e:
        log_event(logger, "llm_confirmation_failed", event_id=signal.event_id, error=str(e))
        # Signal is still persisted so nothing is silently lost -- verdict is null,
        # dashboard should show it as "confirmation failed" for manual review.
        raise HTTPException(status_code=502, detail="LLM confirmation failed; signal saved for manual review")

    verdict = Verdict(
        signal_id=signal.id,
        llm_decision=llm_verdict.decision,
        checklist=llm_verdict.checklist,
        rationale=llm_verdict.rationale,
        model_used=settings.LLM_MODEL,
    )
    db.add(verdict)
    db.add(AuditLog(actor="system", action="llm_verdict", details={
        "event_id": signal.event_id, "decision": llm_verdict.decision,
    }))
    db.commit()
    db.refresh(verdict)

    # 4. Push to dashboard in real time.
    await broadcast_new_signal(signal, verdict)

    return {"status": "processed", "decision": llm_verdict.decision}
