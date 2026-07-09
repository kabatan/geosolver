"""Deterministic JSON encoding used for protocol identities."""

from __future__ import annotations

import hashlib
import json


class CanonicalJsonError(ValueError):
    """Raised when a value cannot be represented as strict canonical JSON."""


def canonical_json(value: object) -> str:
    """Encode *value* with stable object ordering and no insignificant whitespace.

    The protocol hash is over these UTF-8 bytes. A consumer should hash the
    received canonical bytes rather than parse and re-serialize floating-point
    values in another language.
    """

    try:
        return json.dumps(
            value,
            allow_nan=False,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )
    except (TypeError, ValueError) as exc:
        raise CanonicalJsonError(str(exc)) from exc


def canonical_bytes(value: object) -> bytes:
    """Return the UTF-8 canonical representation of *value*."""

    return canonical_json(value).encode("utf-8")


def canonical_hash(value: object) -> str:
    """Return a content identity with an explicit hash-algorithm prefix."""

    digest = hashlib.sha256(canonical_bytes(value)).hexdigest()
    return f"sha256:{digest}"
