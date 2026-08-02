"""Single authority for optimized-engine qualification and public defaults."""

from __future__ import annotations

import hashlib
import json
import re
from copy import deepcopy
from datetime import datetime
from functools import lru_cache
from importlib.resources import files
from typing import Any


def report_summary_sha256(summary: dict[str, Any]) -> str:
    """Return the digest of the embedded, canonical qualification evidence."""

    payload = json.dumps(
        summary,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


@lru_cache(maxsize=1)
def _validated_policy() -> dict[str, Any]:
    value = json.loads(
        files("geotarget").joinpath("qualification.json").read_text(encoding="utf-8")
    )
    return validate_policy(value)


def policy() -> dict[str, Any]:
    """Return an independent qualification snapshot.

    The embedded policy is process-wide authority. Returning a copy prevents
    an API consumer or diagnostic caller from accidentally mutating the
    cached authority for later requests.
    """

    return deepcopy(_validated_policy())


def validate_policy(value: dict[str, Any]) -> dict[str, Any]:
    """Fail closed unless promotion state and its evidence are self-consistent."""

    promoted = bool(
        value.get("promotion_status") == "qualified"
        and value.get("correctness_gate_passed") is True
        and value.get("performance_gate_passed") is True
    )
    if (value.get("default_engine") == "optimized") != promoted:
        raise RuntimeError("optimized qualification policy is internally inconsistent")
    if promoted:
        qualified_at = value.get("qualified_at")
        report_sha256 = value.get("report_sha256")
        report_summary = value.get("report_summary")
        try:
            timestamp = datetime.fromisoformat(str(qualified_at))
        except ValueError as error:
            raise RuntimeError("optimized qualification timestamp is invalid") from error
        if timestamp.tzinfo is None:
            raise RuntimeError("optimized qualification timestamp must include a timezone")
        if (
            not isinstance(report_sha256, str)
            or re.fullmatch(r"[0-9a-f]{64}", report_sha256) is None
        ):
            raise RuntimeError("optimized qualification report checksum is invalid")
        if not isinstance(report_summary, dict):
            raise RuntimeError("optimized qualification report summary is missing")
        try:
            actual_report_sha256 = report_summary_sha256(report_summary)
        except (TypeError, ValueError) as error:
            raise RuntimeError(
                "optimized qualification report summary is not canonical JSON"
            ) from error
        if actual_report_sha256 != report_sha256:
            raise RuntimeError("optimized qualification report checksum does not match summary")
    return value


def optimized_is_qualified() -> bool:
    return policy()["promotion_status"] == "qualified"


DEFAULT_ENGINE = "optimized" if policy()["default_engine"] == "optimized" else "reference"
DEFAULT_RUN_MODE = "adaptive" if DEFAULT_ENGINE == "optimized" else "fixed_time"
DEFAULT_MAX_TIME_SECONDS = 900.0 if DEFAULT_ENGINE == "optimized" else 180.0
DEFAULT_CORES: str | int = "auto" if DEFAULT_ENGINE == "optimized" else 1
