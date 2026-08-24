"""Compatibility helpers for legacy console logging."""

from __future__ import annotations

import sys
from typing import TextIO

from geosolver.engine.standard.config.environment.log_mode import get_log_mode

from .formatters import LogFormatters


def emit_legacy_log(
    *values: object,
    sep: str = " ",
    end: str = "\n",
    file: TextIO | None = None,
    flush: bool = False,
) -> None:
    """Drop-in replacement for print() with optional JSON log output."""
    stream = sys.stdout if file is None else file
    message = sep.join(str(value) for value in values)
    mode = get_log_mode("human")
    output = LogFormatters.as_json("solver_message", {"message": message}) if mode == "json" else message
    stream.write(f"{output}{end}")
    if flush and hasattr(stream, "flush"):
        stream.flush()
