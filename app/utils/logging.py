import logging
import sys
from datetime import datetime, timezone
from typing import Any

from pythonjsonlogger.json import JsonFormatter

from app.utils.request_context import request_id_ctx


class RequestIdFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = request_id_ctx.get()
        return True


class AppJsonFormatter(JsonFormatter):
    """Garante timestamp ISO e level em cada linha JSON."""

    def add_fields(
        self,
        log_record: dict[str, Any],
        record: logging.LogRecord,
        message_dict: dict[str, Any],
    ) -> None:
        super().add_fields(log_record, record, message_dict)
        log_record["timestamp"] = datetime.fromtimestamp(
            record.created, tz=timezone.utc
        ).isoformat()
        log_record["level"] = record.levelname


def setup_logging(level: str = "INFO", *, json_logs: bool = True) -> None:
    root = logging.getLogger()
    if root.handlers:
        return

    handler = logging.StreamHandler(sys.stdout)
    handler.addFilter(RequestIdFilter())

    if json_logs:
        fmt = AppJsonFormatter(
            "%(message)s",
            json_ensure_ascii=False,
        )
    else:
        fmt = logging.Formatter(
            fmt="%(asctime)s %(levelname)s [%(request_id)s] [%(name)s] %(message)s",
            datefmt="%Y-%m-%dT%H:%M:%S",
        )

    handler.setFormatter(fmt)
    root.addHandler(handler)
    root.setLevel(level.upper())


def log_extra(**kwargs: Any) -> dict[str, Any]:
    return {"extra": kwargs}
