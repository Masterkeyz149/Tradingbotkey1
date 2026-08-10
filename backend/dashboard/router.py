import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Query, Request, HTTPException
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import Session

from backend.auth.session import require_session
from backend.confirmation.llm_client import get_confirmation, LLMConfirmationError
from backend.dashboard.ws import broadcast_new_signal
from backend.db.models import Signal, Verdict, AuditLog
from backend.db.session import get_db
from backend.config import get_settings

router = APIRouter()
settings = get_settings()


class ManualSignalRequest(BaseModel):
    symbol: str
    direction: str  # "bullish" | "bearish"
    price: float
    htf_bias_aligned: bool
    liquidity_swept: bool
    structure_break_confirmed: bool
    displacement_present: bool
    price_in_ote: bool
    notes: str = ""


@router.post("/api/manual-signal")
async def submit_manual_signal(
    body: ManualSignalRequest,
    db: Session = Depends(get_db),
    user_email: str = Depends(require_session),
):
    """Log a signal you spotted yourself on the chart -- runs through the
    same LLM confirmation checklist as an automated webhook signal, without
    needing TradingView's webhook feature. Requires being logged in, since
    (unlike the webhook) this route trusts the caller's identity instead of
    a shared secret."""
    if body.direction not in ("bullish", "bearish"):
        raise HTTPException(status_code=400, detail="direction must be 'bullish' or 'bearish'")

    payload_dict = {
        "event_id": f"manual_{uuid.uuid4()}",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "symbol": body.symbol.upper(),
        "direction": body.direction,
        "price": body.price,
        "source": "manual_entry",
        "entered_by": user_email,
        "checklist_inputs": {
            "htf_bias_aligned": body.htf_bias_aligned,
            "liquidity_swept": body.liquidity_swept,
            "structure_break_confirmed": body.structure_break_confirmed,
            "displacement_present": body.displacement_present,
            "price_in_ote": body.price_in_ote,
        },
        "notes": body.notes,
    }

    signal = Signal(
        event_id=payload_dict["event_id"],
        symbol=payload_dict["symbol"],
        direction=body.direction,
        setup_timeframe="manual",
        price=body.price,
        raw_payload=payload_dict,
    )
    db.add(signal)
    db.commit()
    db.refresh(signal)

    db.add(AuditLog(actor=user_email, action="manual_signal_entered", details={"event_id": signal.event_id}))
    db.commit()

    try:
        llm_verdict = get_confirmation(payload_dict)
    except LLMConfirmationError as e:
        raise HTTPException(status_code=502, detail=f"LLM confirmation failed; signal saved for manual review: {e}")

    verdict = Verdict(
        signal_id=signal.id,
        llm_decision=llm_verdict.decision,
        checklist=llm_verdict.checklist,
        rationale=llm_verdict.rationale,
        model_used=settings.LLM_MODEL,
    )
    db.add(verdict)
    db.commit()
    db.refresh(verdict)

    await broadcast_new_signal(signal, verdict)

    return {"status": "processed", "decision": llm_verdict.decision}


@router.get("/api/signals")
def list_signals(
    request: Request,
    limit: int = Query(50, le=200),
    db: Session = Depends(get_db),
    _user: str = Depends(require_session),
):
    rows = (
        db.query(Signal, Verdict)
        .outerjoin(Verdict, Verdict.signal_id == Signal.id)
        .order_by(Signal.received_at.desc())
        .limit(limit)
        .all()
    )
    return [
        {
            "id": s.id,
            "event_id": s.event_id,
            "symbol": s.symbol,
            "direction": s.direction,
            "price": s.price,
            "received_at": s.received_at.isoformat() if s.received_at else None,
            "verdict": None if v is None else {
                "llm_decision": v.llm_decision,
                "checklist": v.checklist,
                "rationale": v.rationale,
                "manual_decision": v.manual_decision,
                "outcome_r_multiple": v.outcome_r_multiple,
            },
        }
        for s, v in rows
    ]


@router.get("/api/stats")
def get_stats(request: Request, db: Session = Depends(get_db), _user: str = Depends(require_session)):
    total = db.query(func.count(Signal.id)).scalar()
    confirmed = db.query(func.count(Verdict.id)).filter(Verdict.llm_decision == "CONFIRM").scalar()
    rejected = db.query(func.count(Verdict.id)).filter(Verdict.llm_decision == "REJECT").scalar()
    manual_overrides = db.query(func.count(Verdict.id)).filter(Verdict.manual_decision.isnot(None)).scalar()

    r_multiples = [
        r[0] for r in db.query(Verdict.outcome_r_multiple).filter(Verdict.outcome_r_multiple.isnot(None)).all()
    ]
    expectancy = sum(r_multiples) / len(r_multiples) if r_multiples else None

    return {
        "total_signals": total,
        "confirmed": confirmed,
        "rejected": rejected,
        "manual_overrides": manual_overrides,
        "expectancy_r": expectancy,
        "trades_with_outcome": len(r_multiples),
    }
