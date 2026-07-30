"""Digest-pinned hard boundary for a one-shot Hermite repair child."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import sys
import time
from typing import Any, Mapping, Sequence

from repair_adapter import _parse_descriptor


HERE = Path(__file__).resolve().parent
CHILD = HERE / "hermite_child.py"
ARCHIVE_ROOT = Path(
    os.environ.get("GEOTARGET_ARCHIVE_RUNTIME_ROOT", "/home/kabatan/work/solver-experiment-runtime/solver")
).resolve()
DEADLINE_GUARD = (
    ARCHIVE_ROOT
    / "research/experiments/EXP-V15-243-001/candidates/hp_lock_scheduler/deadline_guard.py"
)
PDEATH_EXEC = DEADLINE_GUARD.with_name("pdeath_exec.py")
SAME_GROUP = ARCHIVE_ROOT / "research/infrastructure/memory_safety/same_group_subprocess.py"
SAFE_SUBPROCESS = ARCHIVE_ROOT / "research/infrastructure/memory_safety/safe_subprocess.py"
EXPECTED_GUARD_SHA256 = {
    DEADLINE_GUARD: "9d26a006bbfc6073221e6e4135ad92072d3151bc3a2c84d2d982d7672e9ca70f",
    PDEATH_EXEC: "36232592cd52b5a48142f311b8e28350afdd7f72c1e031193058ec46d33d1ffc",
    SAME_GROUP: "fda141f0608b09b3919d758ac56db79e8a14e6d63282a7c120d948879c3fe01e",
    SAFE_SUBPROCESS: "76aa547f235bd0ae11c8b567461384b22537a9b98c990db2ed126db0a19b55c5",
}
THREAD_ENVIRONMENT = {
    "OMP_NUM_THREADS": "1",
    "OPENBLAS_NUM_THREADS": "1",
    "MKL_NUM_THREADS": "1",
    "NUMEXPR_NUM_THREADS": "1",
    "VECLIB_MAXIMUM_THREADS": "1",
}
MAX_ARTIFACT_BYTES = 1024 * 1024


class HardChildFailure(RuntimeError):
    pass


@dataclass(frozen=True)
class ChildLimits:
    timeout_seconds: float
    rss_bytes: int = 256 * 1024**2
    address_space_bytes: int = 1024 * 1024**2
    data_bytes: int = 768 * 1024**2
    output_bytes: int = 64 * 1024
    tail_bytes: int = 8 * 1024
    poll_seconds: float = 0.01
    terminate_grace_seconds: float = 0.10

    def validate(self) -> None:
        if not math.isfinite(self.timeout_seconds) or self.timeout_seconds <= 0.0:
            raise ValueError("timeout_seconds must be finite and positive")
        if not 0 < self.rss_bytes <= self.data_bytes <= self.address_space_bytes:
            raise ValueError("invalid memory cap ordering")
        if not 0 <= self.tail_bytes <= self.output_bytes:
            raise ValueError("invalid output caps")
        if not 0.002 <= self.poll_seconds <= 1.0:
            raise ValueError("invalid poll interval")
        if not 0.0 <= self.terminate_grace_seconds <= 0.25:
            raise ValueError("invalid terminate grace")


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify_guard_pins() -> dict[str, str]:
    observed = {str(path): _sha256(path) if path.is_file() else "MISSING" for path in EXPECTED_GUARD_SHA256}
    expected = {str(path): digest for path, digest in EXPECTED_GUARD_SHA256.items()}
    if observed != expected:
        raise HardChildFailure("hard-guard-digest-mismatch")
    return observed


def _load_guard():
    verify_guard_pins()
    archive = str(ARCHIVE_ROOT)
    if archive in sys.path:
        sys.path.remove(archive)
    sys.path.insert(0, archive)
    name = "geotarget_hermite_pinned_hp_deadline_guard"
    specification = importlib.util.spec_from_file_location(name, DEADLINE_GUARD)
    if specification is None or specification.loader is None:
        raise HardChildFailure("hard-guard-load-failed")
    module = importlib.util.module_from_spec(specification)
    sys.modules[name] = module
    specification.loader.exec_module(module)
    loaded_same_group = Path(module.same_group.__file__).resolve()
    loaded_safe = Path(module.same_group.SAFE.__file__).resolve()
    if (
        loaded_same_group != SAME_GROUP.resolve()
        or loaded_safe != SAFE_SUBPROCESS.resolve()
        or _sha256(loaded_same_group) != EXPECTED_GUARD_SHA256[SAME_GROUP]
        or _sha256(loaded_safe) != EXPECTED_GUARD_SHA256[SAFE_SUBPROCESS]
        or Path(module.PDEATH_EXEC).resolve() != PDEATH_EXEC.resolve()
    ):
        raise HardChildFailure("hard-guard-import-closure-mismatch")
    return module


def _request_payload(
    *,
    source: Path,
    source_sha256: str,
    descriptor: Mapping[str, Any],
    endpoint: Sequence[Any],
    deadline_monotonic: float,
) -> bytes:
    base = {
        "schema": "geotarget.hermite-hard-child-request/v1",
        "source": str(source.resolve()),
        "source_sha256": source_sha256,
        "descriptor": dict(descriptor),
        "endpoint": list(endpoint),
        "deadline_monotonic": deadline_monotonic,
    }
    provisional = json.dumps(base, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    base["request_file_sha256"] = hashlib.sha256(provisional).hexdigest()
    # Hash the exact on-disk bytes excluding only the self-referential field.
    return json.dumps(base, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def _valid_child_authority(
    loaded: object,
    *,
    source_sha256: str,
    descriptor: Mapping[str, Any],
) -> bool:
    if not isinstance(loaded, Mapping):
        return False
    independent = loaded.get("independent_verification")
    replay = loaded.get("untouched_source_replay")
    contract = loaded.get("hard_child_contract")
    return bool(
        loaded.get("schema") == "geotarget.target-hermite-repair-a/v1"
        and loaded.get("status") == "TARGET_AUTHORITY_READY"
        and loaded.get("authority_pass") is True
        and loaded.get("source_sha256") == source_sha256
        and loaded.get("source_or_problem_modified") is False
        and loaded.get("truth_used") is False
        and loaded.get("descriptor") == dict(descriptor)
        and isinstance(independent, Mapping)
        and independent.get("verified") is True
        and isinstance(replay, Mapping)
        and replay.get("verified") is True
        and isinstance(contract, Mapping)
        and contract.get("schema") == "geotarget.hermite-hard-child/v1"
        and contract.get("atomic_final_artifact") is True
        and contract.get("partial_artifact_can_authorize") is False
    )


def run_hard_child(
    *,
    source: Path,
    source_sha256: str,
    descriptor: Mapping[str, Any],
    endpoint: Sequence[Any],
    output_dir: Path,
    cpu: int,
    side_seconds: float,
    fault: str | None = None,
    late_marker: Path | None = None,
) -> dict[str, Any]:
    """Run and consume one child. Every boundary failure yields no authority."""

    artifact = output_dir / "RESULT.json"
    request_path = output_dir / "REQUEST.json"
    status_path = output_dir / "PROCESS_STATUS.json"
    artifact.unlink(missing_ok=True)
    status_path.unlink(missing_ok=True)
    try:
        _parse_descriptor(descriptor)
        if cpu != 15:
            raise HardChildFailure("repair-b-is-restricted-to-cpu15")
        if not math.isfinite(side_seconds) or side_seconds < 0.50:
            raise HardChildFailure("insufficient-hard-child-budget")
        source_bytes = source.read_bytes()
        if hashlib.sha256(source_bytes).hexdigest() != source_sha256:
            raise HardChildFailure("source-digest-mismatch")
        guard = _load_guard()
        output_dir.mkdir(parents=True, exist_ok=True)
        deadline = time.monotonic() + side_seconds
        request_bytes = _request_payload(
            source=source,
            source_sha256=source_sha256,
            descriptor=descriptor,
            endpoint=endpoint,
            deadline_monotonic=deadline - 0.20,
        )
        request_path.write_bytes(request_bytes)
        command = [
            "taskset", "-c", str(cpu), sys.executable, str(CHILD),
            "--request", str(request_path), "--output", str(artifact),
        ]
        if fault is not None:
            command.extend(("--fault", fault))
        if late_marker is not None:
            command.extend(("--late-marker", str(late_marker)))
        environment = dict(os.environ)
        environment.update(THREAD_ENVIRONMENT)
        guarded = guard.run_guarded_until(
            command,
            limits=ChildLimits(timeout_seconds=side_seconds),
            absolute_deadline=deadline,
            environment=environment,
            cwd=HERE,
            status_path=status_path,
            finalization_reserve_seconds=0.10,
            teardown_reserve_seconds=0.10,
            contain_parent=True,
            rss_scope="closure",
        )
        process = guarded.to_dict()
        if not guarded.accepted_output or guarded.classification != "SUCCESS":
            artifact.unlink(missing_ok=True)
            return {"authority": None, "failure_reason": f"hard-child:{guarded.classification}", "process": process}
        if not artifact.is_file() or artifact.stat().st_size > MAX_ARTIFACT_BYTES:
            artifact.unlink(missing_ok=True)
            return {"authority": None, "failure_reason": "missing-or-oversize-artifact", "process": process}
        try:
            loaded = json.loads(artifact.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError):
            artifact.unlink(missing_ok=True)
            return {"authority": None, "failure_reason": "partial-or-malformed-artifact", "process": process}
        if not _valid_child_authority(loaded, source_sha256=source_sha256, descriptor=descriptor):
            artifact.unlink(missing_ok=True)
            return {"authority": None, "failure_reason": "child-authority-rejected", "process": process}
        return {
            "authority": dict(loaded),
            "failure_reason": None,
            "process": process,
            "artifact_sha256": _sha256(artifact),
            "artifact_bytes": artifact.stat().st_size,
            "guard_pins": verify_guard_pins(),
        }
    except Exception as error:  # noqa: BLE001 - candidate must fail closed
        artifact.unlink(missing_ok=True)
        reason = getattr(error, "reason", None) or str(error) or type(error).__name__
        return {"authority": None, "failure_reason": f"runner:{reason}", "process": None}


__all__ = ["ChildLimits", "EXPECTED_GUARD_SHA256", "run_hard_child", "verify_guard_pins"]
