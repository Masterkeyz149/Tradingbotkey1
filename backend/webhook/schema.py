"""
Strict schema for the JSON payload sent by the Pine Script alert() call.
Anything that doesn't match this shape is rejected before it touches any
downstream logic (LLM confirmation, DB, dashboard).
"""
from typing import Optional

from pydantic import BaseModel, Field, field_validator

ALLOWED_DIRECTIONS = {"bullish", "bearish", "crt_bullish", "crt_bearish"}
ALLOWED_CRT_CONFIDENCE = {"high", "medium", "none"}
ALLOWED_KILLZONES = {"asia", "london", "new_york", "none"}


class StructureBlock(BaseModel):
    bullish: bool
    bearish: bool
    bos_up: bool
    bos_down: bool
    choch_bull: bool
    choch_bear: bool


class DisplacementBlock(BaseModel):
    bull_fvg: bool
    bear_fvg: bool


class OTEBlock(BaseModel):
    zone_high: Optional[float] = None
    zone_low: Optional[float] = None
    trigger_0618: Optional[float] = None
    price_in_zone: bool
    price_at_trigger: bool


class MTFContextBlock(BaseModel):
    bias_tf: str
    bias_close: Optional[float] = None
    exec_tf: str
    exec_close: Optional[float] = None


class CRTBlock(BaseModel):
    enabled: bool
    signal_bull: bool
    signal_bear: bool
    confidence: str
    ref_high: Optional[float] = None
    ref_low: Optional[float] = None
    daily_bias_bullish: bool

    @field_validator("confidence")
    @classmethod
    def confidence_valid(cls, v):
        if v not in ALLOWED_CRT_CONFIDENCE:
            raise ValueError(f"invalid crt confidence: {v}")
        return v


class SMTBlock(BaseModel):
    enabled: bool
    correlated_symbol: str
    bullish_divergence: bool
    bearish_divergence: bool


class RiskBlock(BaseModel):
    stop_reference: Optional[float] = None
    stop_distance: Optional[float] = None
    est_risk_pct: Optional[float] = None
    within_cap: bool
    cap_pct: float


class TradingViewSignal(BaseModel):
    event_id: str = Field(..., max_length=200)
    timestamp: str
    symbol: str = Field(..., max_length=20)
    setup_timeframe: str
    direction: str
    price: float = Field(..., gt=0)
    structure: StructureBlock
    displacement: DisplacementBlock
    ote: OTEBlock
    killzone: str
    mtf_context: MTFContextBlock
    crt: CRTBlock
    smt: SMTBlock
    risk: RiskBlock
    target_reference: Optional[float] = None

    @field_validator("direction")
    @classmethod
    def direction_valid(cls, v):
        if v not in ALLOWED_DIRECTIONS:
            raise ValueError(f"invalid direction: {v}")
        return v

    @field_validator("killzone")
    @classmethod
    def killzone_valid(cls, v):
        if v not in ALLOWED_KILLZONES:
            raise ValueError(f"invalid killzone: {v}")
        return v

    model_config = {"extra": "forbid"}  # reject unknown/unexpected fields outright
