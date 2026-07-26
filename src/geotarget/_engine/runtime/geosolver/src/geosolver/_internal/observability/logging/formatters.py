"""Formatters for structured log events."""

import json
from datetime import datetime, timezone
from typing import Any, Mapping


class LogFormatters:
    """Format log events for machine or human consumers."""

    @staticmethod
    def _timestamp() -> str:
        return datetime.now(timezone.utc).isoformat()

    @classmethod
    def as_payload(cls, event: str, fields: Mapping[str, Any]) -> dict[str, Any]:
        payload = {"timestamp": cls._timestamp(), "event": event}
        payload.update(fields)
        return payload

    @classmethod
    def as_json(cls, event: str, fields: Mapping[str, Any]) -> str:
        return json.dumps(cls.as_payload(event, fields), ensure_ascii=False, sort_keys=True)

    @classmethod
    def as_human(cls, event: str, fields: Mapping[str, Any]) -> str:
        details = " ".join(f"{key}={value}" for key, value in sorted(fields.items()))
        return f"[{cls._timestamp()}] {event}" if not details else f"[{cls._timestamp()}] {event} {details}"
