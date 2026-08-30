from __future__ import annotations

import hashlib
import json
from importlib.metadata import PackageNotFoundError, version
from importlib.resources import files
from importlib.resources.abc import Traversable
from typing import Any

PRODUCT_SUFFIXES = frozenset({".json", ".py", ".toml"})


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


def _sha256_json(value: object) -> str:
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=lambda item: {"mpf_binary": item._mpf_},
    )
    return f"sha256:{hashlib.sha256(encoded.encode('utf-8')).hexdigest()}"


def dependency_lock_hash() -> str:
    """Hash the packaged snapshot generated from the resolved uv lock."""
    return _sha256_json(json.loads(files("geosolver").joinpath("dependency-lock.json").read_text()))


def installed_dependencies() -> dict[str, str]:
    locked = json.loads(files("geosolver").joinpath("dependency-lock.json").read_text())
    result = {}
    for name in locked["packages"]:
        try:
            result[name] = version(name)
        except PackageNotFoundError:
            continue  # optional, development-only, or other-platform dependency
    return result


def resolved_config_hash() -> str:
    """Hash the single-engine public runtime defaults."""
    from dataclasses import asdict

    from geosolver.engine.standard.contracts.external_pipeline_config import ExternalPipelineConfig

    return _sha256_json(
        {
            "engine": "standard",
            "default_time_limit_seconds": 180,
            "default_cores": 1,
            "artifact_protocol_version": 3,
            "pipeline": asdict(
                ExternalPipelineConfig.production_baseline_tier(seed=0, total_time_budget_sec=178.0)
            ),
        }
    )


def engine_identity_hashes() -> dict[str, str]:
    """Return the hashes carried by every public result."""
    return {
        "source_hash": source_tree_hash(),
        "resolved_config_hash": resolved_config_hash(),
        "dependency_lock_hash": dependency_lock_hash(),
    }


def expected_engine_lock() -> dict[str, Any]:
    """Build the canonical lock document for the single research engine."""
    source_hash = source_tree_hash()
    return {
        "schema_version": 2,
        "artifact_protocol_version": 3,
        "source_tree_hash": source_hash,
        "resolved_config_hash": resolved_config_hash(),
        "dependency_lock_hash": dependency_lock_hash(),
        "engines": {
            "standard": {
                "hash": source_hash,
                "platforms": ["linux", "windows", "macos"],
                "canonical_time_limit_seconds": 180,
                "canonical_cores": 1,
                "completeness": "unknown",
            }
        },
    }


def verify_engine_lock() -> tuple[bool, str]:
    lock = load_engine_lock()
    expected = expected_engine_lock()
    actual = expected["source_tree_hash"]
    if lock.get("source_tree_hash") != actual:
        return (
            False,
            f"source tree hash mismatch: expected {lock.get('source_tree_hash')}, got {actual}",
        )
    if lock.get("schema_version") != 2 or lock.get("artifact_protocol_version") != 3:
        return False, "unsupported engine lock or artifact protocol version"
    if set(lock.get("engines", {})) != {"standard"}:
        return False, "engine lock must contain only the standard engine"
    if lock != expected:
        return False, "engine lock metadata does not match the resolved runtime contract"
    return True, actual
