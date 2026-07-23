import json
import logging
import os
import sys
from datetime import datetime, timezone

_RESERVED_RECORD_ATTRS = frozenset(
    logging.LogRecord("", 0, "", 0, "", (), None).__dict__.keys()
    | {"message", "asctime"}
)


def configure_logging(level: str | None = None) -> None:
    """Configure the root logger to emit one JSON object per line on stdout.

    Reads the level from the `LOG_LEVEL` env var (default `INFO`) unless
    `level` is given explicitly. JSON output is designed to be scraped by
    Promtail/Grafana Alloy and queried in Grafana via Loki.
    """
    resolved_level = (level or os.environ.get("LOG_LEVEL", "INFO")).upper()

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(_JsonFormatter())

    root = logging.getLogger()
    root.setLevel(resolved_level)
    root.handlers = [handler]


class _JsonFormatter(logging.Formatter):
    """Render a LogRecord as a single-line JSON object."""

    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": datetime.fromtimestamp(
                record.created, tz=timezone.utc
            ).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        for key, value in record.__dict__.items():
            if key not in _RESERVED_RECORD_ATTRS:
                payload[key] = value

        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)

        return json.dumps(payload, default=str)
