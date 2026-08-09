"""
Thin wrapper around the Google Gemini API (free tier) for the confirmation
call. Retries transient failures with exponential backoff; never retries on
a validation failure of the model's own output (that's a logic bug, not a
network blip, and should surface loudly instead of silently retrying).

Uses Gemini's structured-output mode (response_mime_type=application/json)
so the model is constrained to return JSON directly -- no markdown fences
to strip in practice, but we defensively handle them anyway in case a
future model version adds them back.
"""
import json
import logging
import time

import google.generativeai as genai
from google.api_core import exceptions as google_exceptions
from pydantic import ValidationError

from backend.config import get_settings
from backend.confirmation.prompt_builder import SYSTEM_PROMPT, build_user_prompt
from backend.confirmation.verdict import LLMVerdict
from backend.logging_config import log_event

logger = logging.getLogger("confirmation.llm_client")
settings = get_settings()

genai.configure(api_key=settings.GEMINI_API_KEY)

_RETRYABLE_ERRORS = (
    google_exceptions.ServiceUnavailable,
    google_exceptions.ResourceExhausted,   # rate limit / quota
    google_exceptions.DeadlineExceeded,
    google_exceptions.InternalServerError,
)


class LLMConfirmationError(Exception):
    pass


def _get_model() -> genai.GenerativeModel:
    return genai.GenerativeModel(
        model_name=settings.LLM_MODEL,
        system_instruction=SYSTEM_PROMPT,
        generation_config={
            "response_mime_type": "application/json",
            "max_output_tokens": 1000,
            "temperature": 0.0,  # deterministic-as-possible for a rules-checking task
        },
    )


def get_confirmation(signal_payload: dict) -> LLMVerdict:
    user_prompt = build_user_prompt(signal_payload)
    model = _get_model()

    last_error = None
    for attempt in range(1, settings.LLM_MAX_RETRIES + 1):
        try:
            response = model.generate_content(user_prompt)
            raw_text = (response.text or "").strip()
            # Defensive: strip markdown fences if the model ever adds them.
            raw_text = raw_text.removeprefix("```json").removeprefix("```").removesuffix("```").strip()

            parsed = json.loads(raw_text)
            verdict = LLMVerdict(**parsed)

            log_event(
                logger, "llm_confirmation_success",
                symbol=signal_payload.get("symbol"),
                decision=verdict.decision,
                attempt=attempt,
            )
            return verdict

        except _RETRYABLE_ERRORS as e:
            last_error = e
            wait = min(2 ** attempt, 20)
            log_event(logger, "llm_call_retry", attempt=attempt, error=str(e), wait_seconds=wait)
            time.sleep(wait)

        except (json.JSONDecodeError, ValidationError) as e:
            # Model returned something that isn't valid JSON matching our schema.
            # Don't retry blindly -- log the raw output for debugging and fail loud.
            log_event(logger, "llm_output_validation_failed", error=str(e))
            raise LLMConfirmationError(f"LLM returned invalid structured output: {e}") from e

    raise LLMConfirmationError(f"LLM call failed after {settings.LLM_MAX_RETRIES} attempts: {last_error}")
