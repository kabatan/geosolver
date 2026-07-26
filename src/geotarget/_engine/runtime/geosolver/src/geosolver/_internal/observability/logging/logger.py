"""Structured logger with optional scoped context."""

from contextlib import AbstractContextManager
from dataclasses import dataclass
from typing import Any

from .formatters import LogFormatters


@dataclass
class _LogScope(AbstractContextManager["_LogScope"]):
    logger: "StructuredLogger"
    fields: dict[str, Any]

    def __enter__(self) -> "_LogScope":
        self.logger.push_context(**self.fields)
        return self

    def __exit__(self, exc_type, exc, exc_tb) -> None:
        self.logger.pop_context()


class StructuredLogger:
    """Collect structured log lines in json or human-readable mode."""

    def __init__(self, mode: str = "human") -> None:
        if mode not in {"human", "json"}:
            raise ValueError("mode must be 'human' or 'json'")
        self.mode = mode
        self._lines: list[str] = []
        self._stack: list[dict[str, Any]] = []

    def push_context(self, **fields: Any) -> None:
        self._stack.append(dict(fields))

    def pop_context(self) -> None:
        if self._stack:
            self._stack.pop()

    def scope(self, **fields: Any) -> _LogScope:
        return _LogScope(logger=self, fields=dict(fields))

    def info(self, event: str, **fields: Any) -> str:
        merged: dict[str, Any] = {}
        for frame in self._stack:
            merged.update(frame)
        merged.update(fields)
        line = LogFormatters.as_json(event, merged) if self.mode == "json" else LogFormatters.as_human(event, merged)
        self._lines.append(line)
        return line

    def lines(self) -> list[str]:
        return list(self._lines)
