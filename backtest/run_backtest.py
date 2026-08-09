"""
Replays historical signals (already logged in Postgres, or supplied as a
JSON file of payloads) through the current LLM confirmation layer and rules
config, WITHOUT touching the live dashboard/DB tables used by the real
webhook flow. Use this before trusting a rules-config change or a model
swap live.

Usage:
    python -m backtest.run_backtest --source db --limit 200
    python -m backtest.run_backtest --source file --path historical_signals.json

Outputs a summary: confirm/reject counts, and if outcome_r_multiple is
present in the source data, expectancy (mean R) and win rate.
"""
import argparse
import json
import sys
import time

from backend.confirmation.llm_client import get_confirmation, LLMConfirmationError
from backend.db.models import Signal, Verdict
from backend.db.session import SessionLocal


def load_from_db(limit: int):
    db = SessionLocal()
    try:
        signals = db.query(Signal).order_by(Signal.received_at.desc()).limit(limit).all()
        return [
            {"payload": s.raw_payload, "event_id": s.event_id, "known_outcome_r": None}
            for s in signals
        ]
    finally:
        db.close()


def load_from_file(path: str):
    with open(path) as f:
        return json.load(f)


def run_backtest(cases: list[dict], delay_seconds: float = 0.5):
    results = []
    for i, case in enumerate(cases, 1):
        payload = case["payload"]
        try:
            verdict = get_confirmation(payload)
            results.append({
                "event_id": case.get("event_id"),
                "symbol": payload.get("symbol"),
                "decision": verdict.decision,
                "rationale": verdict.rationale,
                "known_outcome_r": case.get("known_outcome_r"),
            })
        except LLMConfirmationError as e:
            results.append({"event_id": case.get("event_id"), "error": str(e)})
        print(f"[{i}/{len(cases)}] processed", file=sys.stderr)
        time.sleep(delay_seconds)  # be gentle on rate limits during a large backtest
    return results


def summarize(results: list[dict]):
    confirmed = [r for r in results if r.get("decision") == "CONFIRM"]
    rejected = [r for r in results if r.get("decision") == "REJECT"]
    errors = [r for r in results if "error" in r]

    print("\n--- Backtest Summary ---")
    print(f"Total: {len(results)}  Confirmed: {len(confirmed)}  Rejected: {len(rejected)}  Errors: {len(errors)}")

    with_outcomes = [r for r in confirmed if r.get("known_outcome_r") is not None]
    if with_outcomes:
        r_values = [r["known_outcome_r"] for r in with_outcomes]
        expectancy = sum(r_values) / len(r_values)
        win_rate = sum(1 for r in r_values if r > 0) / len(r_values) * 100
        print(f"Of confirmed signals with known outcomes: expectancy={expectancy:.2f}R, win_rate={win_rate:.1f}%")
    else:
        print("No known_outcome_r values supplied -- expectancy/win-rate not computed.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", choices=["db", "file"], required=True)
    parser.add_argument("--path", help="Path to historical_signals.json (required if --source file)")
    parser.add_argument("--limit", type=int, default=100)
    args = parser.parse_args()

    if args.source == "db":
        cases = load_from_db(args.limit)
    else:
        if not args.path:
            parser.error("--path is required when --source file")
        cases = load_from_file(args.path)

    results = run_backtest(cases)
    with open("backtest_results.json", "w") as f:
        json.dump(results, f, indent=2)
    summarize(results)
    print("Full results written to backtest_results.json")
