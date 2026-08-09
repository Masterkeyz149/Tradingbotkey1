"""
All configuration comes from environment variables (Railway env vars in
production, a local .env file in development). Nothing here is a secret --
this file just defines what settings exist and their defaults.
"""
import os
from functools import lru_cache


class Settings:
    # --- Core ---
    ENV: str = os.getenv("ENV", "development")  # development | production
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///./local_dev.db")

    # --- Webhook security ---
    WEBHOOK_SHARED_SECRET: str = os.getenv("WEBHOOK_SHARED_SECRET", "")
    WEBHOOK_RATE_LIMIT_PER_MIN: int = int(os.getenv("WEBHOOK_RATE_LIMIT_PER_MIN", "30"))

    # --- LLM confirmation (Google Gemini free tier) ---
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
    LLM_MODEL: str = os.getenv("LLM_MODEL", "gemini-2.5-flash")
    LLM_MAX_RETRIES: int = int(os.getenv("LLM_MAX_RETRIES", "3"))
    # Keep comfortably under Gemini's free-tier per-minute cap.
    LLM_RATE_LIMIT_PER_MIN: int = int(os.getenv("LLM_RATE_LIMIT_PER_MIN", "10"))

    # --- Auth (email magic link) ---
    AUTH_SECRET_KEY: str = os.getenv("AUTH_SECRET_KEY", "")  # sign magic-link tokens & session cookies
    AUTH_ALLOWED_EMAIL: str = os.getenv("AUTH_ALLOWED_EMAIL", "")  # single-user allowlist
    MAGIC_LINK_TTL_MINUTES: int = int(os.getenv("MAGIC_LINK_TTL_MINUTES", "15"))
    SESSION_TTL_HOURS: int = int(os.getenv("SESSION_TTL_HOURS", "24"))
    EMAIL_PROVIDER_API_KEY: str = os.getenv("EMAIL_PROVIDER_API_KEY", "")  # Resend/Postmark
    EMAIL_FROM: str = os.getenv("EMAIL_FROM", "alerts@yourdomain.com")
    APP_BASE_URL: str = os.getenv("APP_BASE_URL", "http://localhost:8000")

    # --- Rules config ---
    RULES_CONFIG_PATH: str = os.getenv("RULES_CONFIG_PATH", "config/rules_config.yaml")

    # --- Execution (gated, off by default) ---
    EXECUTION_ENABLED: bool = os.getenv("EXECUTION_ENABLED", "false").lower() == "true"
    PAPER_TRADING: bool = os.getenv("PAPER_TRADING", "true").lower() == "true"
    MAX_POSITION_SIZE_USD: float = float(os.getenv("MAX_POSITION_SIZE_USD", "0"))
    MAX_DAILY_LOSS_USD: float = float(os.getenv("MAX_DAILY_LOSS_USD", "0"))

    # --- Optional notifications ---
    TELEGRAM_BOT_TOKEN: str = os.getenv("TELEGRAM_BOT_TOKEN", "")
    TELEGRAM_CHAT_ID: str = os.getenv("TELEGRAM_CHAT_ID", "")


@lru_cache
def get_settings() -> Settings:
    return Settings()
