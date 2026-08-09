from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import func
from sqlalchemy.orm import Session

from backend.auth.session import require_session
from backend.db.models import Signal, Verdict
from backend.db.session import get_db

router = APIRouter()


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
