"""
SECURITY-CRITICAL: this prompt must only ever contain structured data we
control (the validated webhook payload + our own rules config) -- never raw,
unsanitized text from an external source. The webhook schema already
constrains every field to a fixed type/enum before it gets here, which is
what makes it safe to interpolate: there's no free-text field an attacker
could use to inject instructions.
"""
import json

from backend.confirmation.rules_loader import load_rules_config, get_instrument_strategy

SYSTEM_PROMPT = """You are a rules-based trade-setup confirmation filter. You do not invent \
trade ideas, do not use outside knowledge of current markets, and do not override the \
user's risk rules. Your ONLY job: given a structured signal and the user's own written \
methodology, decide CONFIRM or REJECT by checking the signal against the entry checklist, \
and explain which checklist items passed or failed.

Respond ONLY with a JSON object, no markdown fences, no preamble, in exactly this shape:
{
  "decision": "CONFIRM" | "REJECT",
  "checklist": {"<item_id>": true | false, ...},
  "rationale": "<2-4 sentence explanation, plain language>"
}
"""


def build_user_prompt(signal_payload: dict) -> str:
    rules = load_rules_config()
    instrument_strategy = get_instrument_strategy(signal_payload["symbol"])

    context = {
        "signal": signal_payload,
        "methodology_rules": rules,
        "instrument_strategy_for_this_symbol": instrument_strategy,
    }
    return (
        "Evaluate this signal against the checklist and methodology below. "
        "Cross-check that the signal's setup type matches the strategy tagged "
        "for this instrument (e.g. don't apply the OTE/sweep model to a pair "
        "tagged for momentum continuation). If CRT confidence is 'medium', "
        "weigh that as a lower-certainty factor. If SMT divergence flags are "
        "present, weigh them as supporting/contradicting context.\n\n"
        f"DATA:\n{json.dumps(context, indent=2)}"
    )
