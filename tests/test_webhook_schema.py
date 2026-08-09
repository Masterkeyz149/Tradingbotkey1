import pytest
from pydantic import ValidationError

from backend.webhook.schema import TradingViewSignal

VALID_PAYLOAD = {
    "event_id": "123_XAUUSD_bullish",
    "timestamp": "2026-08-08T13:45:00Z",
    "symbol": "XAUUSD",
    "setup_timeframe": "30",
    "direction": "bullish",
    "price": 2415.32,
    "structure": {
        "bullish": True, "bearish": False, "bos_up": True, "bos_down": False,
        "choch_bull": False, "choch_bear": False,
    },
    "displacement": {"bull_fvg": True, "bear_fvg": False},
    "ote": {
        "zone_high": 2418.10, "zone_low": 2410.55, "trigger_0618": 2413.90,
        "price_in_zone": True, "price_at_trigger": True,
    },
    "killzone": "london",
    "mtf_context": {"bias_tf": "240", "bias_close": 2416.8, "exec_tf": "5", "exec_close": 2415.1},
    "crt": {
        "enabled": False, "signal_bull": False, "signal_bear": False, "confidence": "none",
        "ref_high": None, "ref_low": None, "daily_bias_bullish": True,
    },
    "smt": {
        "enabled": False, "correlated_symbol": "FX:AUDUSD",
        "bullish_divergence": False, "bearish_divergence": False,
    },
    "risk": {
        "stop_reference": 2405.2, "stop_distance": 10.12, "est_risk_pct": 0.42,
        "within_cap": True, "cap_pct": 2.0,
    },
    "target_reference": 2430.0,
}


def test_valid_payload_parses():
    signal = TradingViewSignal(**VALID_PAYLOAD)
    assert signal.symbol == "XAUUSD"
    assert signal.direction == "bullish"


def test_invalid_direction_rejected():
    bad = {**VALID_PAYLOAD, "direction": "sideways"}
    with pytest.raises(ValidationError):
        TradingViewSignal(**bad)


def test_negative_price_rejected():
    bad = {**VALID_PAYLOAD, "price": -5}
    with pytest.raises(ValidationError):
        TradingViewSignal(**bad)


def test_unknown_extra_field_rejected():
    bad = {**VALID_PAYLOAD, "unexpected_field": "malicious_injected_value"}
    with pytest.raises(ValidationError):
        TradingViewSignal(**bad)


def test_invalid_crt_confidence_rejected():
    bad = {**VALID_PAYLOAD}
    bad["crt"] = {**VALID_PAYLOAD["crt"], "confidence": "super_high"}
    with pytest.raises(ValidationError):
        TradingViewSignal(**bad)


def test_missing_required_field_rejected():
    bad = {k: v for k, v in VALID_PAYLOAD.items() if k != "structure"}
    with pytest.raises(ValidationError):
        TradingViewSignal(**bad)
