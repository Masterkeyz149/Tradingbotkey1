"""
Structured (JSON-lines) logging. Every log line is a JSON object so it's
greppable and, more importantly, so Railway's log viewer / any log drain
can parse it. Never log secrets -- see redact().
"""
import json
import logging
import sys
import time

_SECRET_KEYS = {"webhook_shared_secret", "api_key", "password", "token", "secret", "authorization"}


def redact(data: dict) -> dict:
    """Recursively strip anything that looks like a secret before logging it."""
    if not isinstance(data, dict):
        return data
    out = {}
    for k, v in data.items():
        if any(s in k.lower() for s in _SECRET_KEYS):
            out[k] = "***REDACTED***"
        elif isinstance(v, dict):
            out[k] = redact(v)
        else:
            out[k] = v
    return out


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(record.created)),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        extra = getattr(record, "extra_fields", None)
        if extra:
            payload.update(redact(extra))
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        return json.dumps(payload)


def setup_logging(level: str = "INFO") -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(level)


def log_event(logger: logging.Logger, msg: str, **fields):
    logger.info(msg, extra={"extra_fields": fields})
