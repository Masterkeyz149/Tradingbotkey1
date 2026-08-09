from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.auth.session import require_session
from backend.db.models import Verdict, AuditLog
from backend.db.session import get_db

router = APIRouter()


class OverrideRequest(BaseModel):
    decision: str  # "APPROVE" | "REJECT"


@router.post("/api/verdicts/{verdict_id}/override")
def override_verdict(
    verdict_id: str,
    body: OverrideRequest,
    db: Session = Depends(get_db),
    user_email: str = Depends(require_session),
):
    if body.decision not in ("APPROVE", "REJECT"):
        raise HTTPException(status_code=400, detail="decision must be APPROVE or REJECT")

    verdict = db.query(Verdict).filter(Verdict.id == verdict_id).first()
    if not verdict:
        raise HTTPException(status_code=404, detail="Verdict not found")

    verdict.manual_decision = body.decision
    verdict.manual_decided_at = datetime.now(timezone.utc)
    verdict.manual_actor = user_email

    db.add(AuditLog(
        actor=user_email,
        action=f"manual_{body.decision.lower()}",
        details={"verdict_id": verdict_id},
    ))
    db.commit()

    return {"status": "ok", "verdict_id": verdict_id, "manual_decision": body.decision}
