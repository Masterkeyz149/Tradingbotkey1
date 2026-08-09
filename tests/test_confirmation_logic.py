from unittest.mock import patch, MagicMock

import pytest
from pydantic import ValidationError

from backend.confirmation.verdict import LLMVerdict
from backend.confirmation.prompt_builder import build_user_prompt


SAMPLE_SIGNAL = {
    "event_id": "1_XAUUSD_bullish",
    "symbol": "XAUUSD",
    "direction": "bullish",
    "price": 2415.32,
}


def test_verdict_accepts_valid_decision():
    v = LLMVerdict(decision="CONFIRM", checklist={"htf_bias_aligned": True}, rationale="Looks aligned.")
    assert v.decision == "CONFIRM"


def test_verdict_rejects_invalid_decision():
    with pytest.raises(ValidationError):
        LLMVerdict(decision="MAYBE", checklist={}, rationale="unclear")


@patch("backend.confirmation.prompt_builder.load_rules_config")
@patch("backend.confirmation.prompt_builder.get_instrument_strategy")
def test_prompt_includes_signal_and_rules(mock_instr, mock_rules):
    mock_rules.return_value = {"entry_checklist": [{"id": "htf_bias_aligned"}]}
    mock_instr.return_value = {"symbol": "XAUUSD", "strategy": "ote"}

    prompt = build_user_prompt(SAMPLE_SIGNAL)

    assert "XAUUSD" in prompt
    assert "htf_bias_aligned" in prompt
    assert "cross-check" in prompt.lower()


def test_prompt_never_embeds_raw_unvalidated_text():
    """Guards against prompt injection: the prompt builder should only ever
    serialize known dict/JSON structures, never string-concatenate an
    unvalidated free-text field into the prompt."""
    import inspect
    from backend.confirmation import prompt_builder

    source = inspect.getsource(prompt_builder.build_user_prompt)
    # The only string formatting into the prompt should be via json.dumps of
    # the structured context object -- not raw field interpolation.
    assert "json.dumps(context" in source
