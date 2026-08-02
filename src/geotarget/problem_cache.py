"""Bounded, source-preserving cache for product-owned validation artifacts."""

from __future__ import annotations

import hashlib
import json
import threading
from collections import OrderedDict
from typing import Any

from geotarget.models import ValidationReport
from geotarget.validation import validate

_MAX_ENTRIES = 64
_LOCK = threading.Lock()
_CACHE: OrderedDict[str, ValidationReport] = OrderedDict()


def _cache_key(problem: dict[str, Any]) -> str:
    payload = json.dumps(
        problem, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def validate_cached(problem: dict[str, Any]) -> tuple[ValidationReport, bool]:
    key = _cache_key(problem)
    with _LOCK:
        cached = _CACHE.get(key)
        if cached is not None:
            _CACHE.move_to_end(key)
            return cached.model_copy(deep=True), True
    report = validate(problem)
    with _LOCK:
        _CACHE[key] = report.model_copy(deep=True)
        _CACHE.move_to_end(key)
        while len(_CACHE) > _MAX_ENTRIES:
            _CACHE.popitem(last=False)
    return report, False


def clear_validation_cache() -> None:
    with _LOCK:
        _CACHE.clear()
