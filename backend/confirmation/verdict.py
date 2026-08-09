from typing import Dict

from pydantic import BaseModel, field_validator


class LLMVerdict(BaseModel):
    decision: str
    checklist: Dict[str, bool]
    rationale: str

    @field_validator("decision")
    @classmethod
    def decision_valid(cls, v):
        if v not in ("CONFIRM", "REJECT"):
            raise ValueError(f"invalid decision from LLM: {v}")
        return v
