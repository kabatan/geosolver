"""Formatters for structured log events."""

import json
from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any


class LogFormatters:
    """Format structured log events as JSON."""

    @staticmethod
    def _timestamp() -> str:
        return datetime.now(UTC).isoformat()

    @classmethod
    def as_payload(cls, event: str, fields: Mapping[str, Any]) -> dict[str, Any]:
        payload = {"timestamp": cls._timestamp(), "event": event}
        payload.update(fields)
        return payload

    @classmethod
    def as_json(cls, event: str, fields: Mapping[str, Any]) -> str:
        return json.dumps(cls.as_payload(event, fields), ensure_ascii=False, sort_keys=True)
