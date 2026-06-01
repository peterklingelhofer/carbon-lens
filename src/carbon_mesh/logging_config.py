"""Structured logging configuration for production and development."""

import json
import logging
import sys
from datetime import datetime, timezone

from carbon_mesh.config import settings


class JSONFormatter(logging.Formatter):
    """Emit log records as single-line JSON for log aggregators (Datadog, ELK, etc.)."""

    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info and record.exc_info[1]:
            payload["exception"] = self.formatException(record.exc_info)
        # Attach extra fields if set by middleware
        for key in ("request_id", "method", "path", "status_code", "duration_ms"):
            val = getattr(record, key, None)
            if val is not None:
                payload[key] = val
        return json.dumps(payload, default=str)


def setup_logging() -> None:
    """Configure root logger based on CARBON_LENS_LOG_FORMAT and CARBON_LENS_LOG_LEVEL."""
    root = logging.getLogger()
    root.setLevel(getattr(logging, settings.log_level.upper(), logging.INFO))

    handler = logging.StreamHandler(sys.stdout)

    if settings.log_format == "json":
        handler.setFormatter(JSONFormatter())
    else:
        handler.setFormatter(
            logging.Formatter(
                "%(asctime)s %(levelname)s [%(name)s] %(message)s",
                datefmt="%Y-%m-%dT%H:%M:%S",
            )
        )

    root.handlers = [handler]
