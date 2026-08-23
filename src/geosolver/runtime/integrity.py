from __future__ import annotations

import hashlib
import json
from importlib.resources import files
from importlib.resources.abc import Traversable
from typing import Any

PRODUCT_SUFFIXES = frozenset({".jl", ".json", ".py", ".toml"})


def load_engine_lock() -> dict[str, Any]:
    lock = files("geosolver").joinpath("engine-lock.json")
    value = json.loads(lock.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("engine lock must be a JSON object")
    return value


def _product_files(root: Traversable, relative: str = "") -> list[tuple[str, Traversable]]:
    selected: list[tuple[str, Traversable]] = []
    for entry in root.iterdir():
        path = f"{relative}/{entry.name}" if relative else entry.name
        if entry.is_dir():
            if entry.name not in {"__pycache__", "frontend"}:
                selected.extend(_product_files(entry, path))
            continue
        suffix = "." + entry.name.rsplit(".", 1)[-1] if "." in entry.name else ""
        if entry.name != "engine-lock.json" and suffix in PRODUCT_SUFFIXES:
            selected.append((path, entry))
    return selected


def source_tree_hash() -> str:
    digest = hashlib.sha256()
    for relative, resource in sorted(_product_files(files("geosolver"))):
        digest.update(relative.encode("utf-8"))
        digest.update(b"\0")
        # Git may materialize text as LF or CRLF depending on platform policy.
        # Both represent the same product source and must produce the same lock.
        digest.update(resource.read_bytes().replace(b"\r\n", b"\n"))
        digest.update(b"\0")
    return f"sha256:{digest.hexdigest()}"


def locked_engine_hash(name: str) -> str:
    lock = load_engine_lock()
    engines = lock.get("engines")
    if not isinstance(engines, dict) or not isinstance(engines.get(name), dict):
        raise ValueError(f"engine {name!r} is absent from the engine lock")
    value = engines[name].get("hash")
    if not isinstance(value, str) or not value.startswith("sha256:"):
        raise ValueError(f"engine {name!r} has an invalid locked hash")
    return value


def verify_engine_lock() -> tuple[bool, str]:
    lock = load_engine_lock()
    expected = lock.get("source_tree_hash")
    actual = source_tree_hash()
    if expected != actual:
        return False, f"source tree hash mismatch: expected {expected}, got {actual}"
    if lock.get("schema_version") != 1 or lock.get("artifact_protocol_version") != 1:
        return False, "unsupported engine lock or artifact protocol version"
    if set(lock.get("engines", {})) != {"standard", "reference"}:
        return False, "engine lock must contain standard and reference"
    return True, actual
