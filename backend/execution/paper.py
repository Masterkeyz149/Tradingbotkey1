"""
Phase 6 (optional, gated): paper trading simulation.

This is intentionally a stub. Position tracking, fill simulation, and P&L
math depend on decisions we haven't made yet (per-instrument contract specs,
spread/slippage assumptions, which account currency, etc.) -- filling those
in blind would produce numbers you couldn't trust. Flesh this out once
you're ready for this phase; happy to do it then.

Guardrail that IS already enforced regardless: nothing in this module runs
unless EXECUTION_ENABLED=true in settings, and even then this file only
simulates -- backend/execution/live.py (not yet built) would be a separate,
further-gated module for real broker calls.
"""
from backend.config import get_settings

settings = get_settings()


def simulate_fill(signal_payload: dict, verdict_decision: str) -> dict:
    if not settings.EXECUTION_ENABLED:
        return {"status": "skipped", "reason": "EXECUTION_ENABLED is false"}

    if verdict_decision != "CONFIRM":
        return {"status": "skipped", "reason": "signal not confirmed"}

    # TODO: implement once position sizing / contract spec inputs are defined.
    raise NotImplementedError("Paper execution not yet implemented -- Phase 6 pending scope confirmation")
