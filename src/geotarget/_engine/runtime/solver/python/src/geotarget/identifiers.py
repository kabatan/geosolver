"""Wire identifier validation shared by the authoring model."""

from __future__ import annotations

import re
import uuid

STABLE_ID_PATTERN = r"^[A-Za-z_][A-Za-z0-9_.-]*$"
PLUGIN_ID_PATTERN = (
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}"
    r"/[A-Za-z_][A-Za-z0-9_.-]*$"
)
SEMVER_PATTERN = (
    r"^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)"
    r"(?:-[0-9A-Za-z.-]+)?(?:\+[0-9A-Za-z.-]+)?$"
)
SHA256_PATTERN = r"^sha256:[0-9a-f]{64}$"

_STABLE_ID = re.compile(STABLE_ID_PATTERN)
_PLUGIN_ID = re.compile(PLUGIN_ID_PATTERN)
_SEMVER = re.compile(SEMVER_PATTERN)
_SHA256 = re.compile(SHA256_PATTERN)


class IdentifierError(ValueError):
    """Raised when a stable wire identifier is malformed."""


def stable_id(value: str, *, field: str = "id") -> str:
    if _STABLE_ID.fullmatch(value) is None:
        raise IdentifierError(f"{field} is not a stable identifier: {value!r}")
    return value


def plugin_id(value: str) -> str:
    if _PLUGIN_ID.fullmatch(value) is None:
        raise IdentifierError(f"plugin_id must be '<canonical UUID>/<stable name>': {value!r}")
    namespace, _ = value.split("/", maxsplit=1)
    if str(uuid.UUID(namespace)) != namespace:
        raise IdentifierError(f"plugin UUID is not canonical lowercase text: {value!r}")
    return value


def semver(value: str, *, field: str = "version") -> str:
    if _SEMVER.fullmatch(value) is None:
        raise IdentifierError(f"{field} is not semantic version text: {value!r}")
    return value


def sha256_id(value: str, *, field: str = "content_hash") -> str:
    if _SHA256.fullmatch(value) is None:
        raise IdentifierError(f"{field} is not a lowercase sha256 identity")
    return value


def qualified_symbol(value: str) -> tuple[str, str]:
    try:
        owner, symbol = value.split("::", maxsplit=1)
    except ValueError as exc:
        raise IdentifierError(
            f"qualified symbol must have the form '<plugin_id>::<symbol>': {value!r}"
        ) from exc
    plugin_id(owner)
    stable_id(symbol, field="symbol")
    return owner, symbol
