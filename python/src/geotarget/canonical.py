"""RFC 8785 JSON Canonicalization Scheme encoding for protocol identities."""

from __future__ import annotations

import hashlib
from typing import Any, cast

import rfc8785


class CanonicalJsonError(ValueError):
    """Raised when a value cannot be represented as strict canonical JSON."""


def canonical_json(value: object) -> str:
    """Encode *value* as RFC 8785 JCS text.

    JCS fixes object ordering, string escaping and IEEE-754 number rendering.
    Integers outside the interoperable binary64 domain must travel as canonical
    decimal strings in fields whose schema explicitly allows them.
    """

    return canonical_bytes(value).decode("utf-8")


def canonical_bytes(value: object) -> bytes:
    """Return the UTF-8 canonical representation of *value*."""

    try:
        return bytes(rfc8785.dumps(cast(Any, value)))
    except (TypeError, ValueError, rfc8785.CanonicalizationError) as exc:
        raise CanonicalJsonError(str(exc)) from exc


def canonical_hash(value: object) -> str:
    """Return a content identity with an explicit hash-algorithm prefix."""

    digest = hashlib.sha256(canonical_bytes(value)).hexdigest()
    return f"sha256:{digest}"
