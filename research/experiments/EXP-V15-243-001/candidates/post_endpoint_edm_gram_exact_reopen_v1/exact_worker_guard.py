#!/usr/bin/env python3.12
"""Fail-closed child seam for the frozen exact-coordinate worker."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import resource
import sys

import execution_guard as guard


EXPECTED_RUNTIME_CLOSURE_SHA256 = (
    "ec2d5c933d947549194e9226170702360a8e3d350d69b7c07267afe2624a55a9"
)


def verify_runtime_closure(manifest: dict[str, object]) -> dict[str, object]:
    closure = manifest.get("runtime_closure")
    if (
        not isinstance(closure, dict)
        or manifest.get("runtime_closure_sha256") != EXPECTED_RUNTIME_CLOSURE_SHA256
        or guard.sha256_bytes(guard.canonical_json(closure))
        != EXPECTED_RUNTIME_CLOSURE_SHA256
    ):
        raise PermissionError("exact transitive runtime closure changed")
    for name, record in closure.items():
        if not isinstance(record, dict) or set(record) != {"path", "sha256"}:
            raise PermissionError(f"malformed runtime closure record: {name}")
        path = Path(str(record["path"])).resolve()
        observed = (
            guard.tree_sha256(path)
            if name == "geosolver_source_tree" and path.is_dir()
            else guard.sha256_bytes(path.read_bytes())
        )
        if observed != record["sha256"]:
            raise PermissionError(f"runtime closure drift: {name}")
    return closure


def verify_attempt_byte_bindings(
    manifest: dict[str, object], attempt_root: Path
) -> None:
    for key in ("source", "ordinary_proposal"):
        record = manifest.get(key)
        if not isinstance(record, dict) or set(record) != {"path", "sha256"}:
            raise PermissionError(f"{key} byte binding is absent")
        path = Path(str(record.get("path", ""))).resolve()
        if path.parent != attempt_root.resolve():
            raise PermissionError(f"{key} escaped attempt root")
        if guard.sha256_bytes(path.read_bytes()) != record.get("sha256"):
            raise PermissionError(f"{key} all-byte SHA mismatch")


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--attempt-manifest", type=Path, required=True)
    parser.add_argument("--worker", type=Path, required=True)
    parser.add_argument("--python", type=Path, required=True)
    parser.add_argument("worker_arguments", nargs=argparse.REMAINDER)
    return parser


def main() -> None:
    arguments = _parser().parse_args()
    payload = arguments.attempt_manifest.read_bytes()
    guard.verify_inherited_handoff(payload)
    manifest = json.loads(payload)
    if manifest.get("schema_version") != "geotarget.edm-exact-attempt/v1":
        raise PermissionError("exact attempt schema mismatch")
    closure = verify_runtime_closure(manifest)
    if manifest.get("worker_path") != str(arguments.worker.resolve()):
        raise PermissionError("exact worker path differs from authorized attempt")
    if manifest.get("python_path") != str(arguments.python.resolve()):
        raise PermissionError("exact Python differs from authorized attempt")
    if (
        closure.get("exact_worker", {}).get("path") != str(arguments.worker.resolve())
        or closure.get("formal_python", {}).get("path") != str(arguments.python.resolve())
    ):
        raise PermissionError("worker/Python is outside the fixed runtime closure")
    verify_attempt_byte_bindings(manifest, arguments.attempt_manifest.parent)
    limits = manifest.get("limits")
    if not isinstance(limits, dict):
        raise PermissionError("resource limits absent")
    for kind, resource_kind in (
        ("address_space_bytes", resource.RLIMIT_AS),
        ("data_bytes", resource.RLIMIT_DATA),
        ("file_bytes", resource.RLIMIT_FSIZE),
    ):
        value = int(limits[kind])
        if value <= 0:
            raise PermissionError("invalid resource limit")
        resource.setrlimit(resource_kind, (value, value))
    os.umask(0o077)
    fixed_julia_shim = Path(str(manifest.get("fixed_julia_shim", "")))
    if (
        not fixed_julia_shim.is_symlink()
        or fixed_julia_shim.resolve()
        != Path(str(closure.get("julia", {}).get("path", ""))).resolve()
    ):
        raise PermissionError("fixed Julia shim changed")
    environment = dict(guard.STATIC_ENVIRONMENT)
    environment.update(
        {
            "PATH": str(fixed_julia_shim.parent) + ":/usr/bin:/bin",
            "TMPDIR": str(arguments.attempt_manifest.parent.resolve()),
        }
    )
    worker_arguments = list(arguments.worker_arguments)
    if worker_arguments and worker_arguments[0] == "--":
        worker_arguments.pop(0)
    encoded_arguments = b"\0".join(item.encode("utf-8") for item in worker_arguments)
    if guard.sha256_bytes(encoded_arguments) != manifest.get("worker_arguments_sha256"):
        raise PermissionError("worker argv differs from authorized attempt")
    os.execve(
        arguments.python.resolve(),
        [str(arguments.python.resolve()), str(arguments.worker.resolve()), *worker_arguments],
        environment,
    )


if __name__ == "__main__":
    main()
