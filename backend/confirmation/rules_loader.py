"""
Loads the editable methodology rules from config/rules_config.yaml. Keeping
this in a config file (not hardcoded in Python) means you can tune
thresholds, instrument-strategy mapping, and checklist wording without
touching code or redeploying logic.
"""
import functools

import yaml

from backend.config import get_settings

settings = get_settings()


@functools.lru_cache
def load_rules_config() -> dict:
    with open(settings.RULES_CONFIG_PATH, "r") as f:
        return yaml.safe_load(f)


def get_instrument_strategy(symbol: str) -> dict | None:
    rules = load_rules_config()
    for entry in rules.get("instruments", []):
        if entry["symbol"].upper() == symbol.upper():
            return entry
    return None
