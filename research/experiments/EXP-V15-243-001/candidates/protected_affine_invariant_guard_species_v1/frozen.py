"""Hash-pinned connection to the old G1 typed GuardIR adapter."""

from __future__ import annotations

import hashlib
import importlib.util
from pathlib import Path
import sys


HERE = Path(__file__).resolve().parent
OLD_ROOT = Path(
    "/home/kabatan/work/solver-experiment-runtime/solver/research/experiments/"
    "EXP-V15-243-001/candidates"
)
OLD_CANDIDATE = OLD_ROOT / "guard_stratum_novelty/candidate.py"
OLD_ADAPTER = OLD_ROOT / "guard_stratum_novelty/typed_guard_adapter.py"
CANDIDATE_SHA256 = "e61562f1ec880ad6618646b804cf2151a2a595481b6f13beb4a92bde35d53ffb"
ADAPTER_SHA256 = "48b44d0dadf52701a2a9ccdc511463740a38dd1dc544f67c886c2e49b23fa154"


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ImportError(path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


if _digest(OLD_CANDIDATE) != CANDIDATE_SHA256:
    raise RuntimeError("old G1 candidate changed")
if _digest(OLD_ADAPTER) != ADAPTER_SHA256:
    raise RuntimeError("old G1 typed adapter changed")

candidate = _load("candidate", HERE / "candidate.py")
typed_guard_adapter = _load(
    "protected_affine_invariant_typed_guard_adapter", OLD_ADAPTER
)

configuration = candidate.ArchiveConfiguration()
if (
    configuration.maximum_entries,
    configuration.merge_tolerance,
    configuration.lookahead,
    configuration.insurance_period,
) != (64, 1.0e-8, 12, 4):
    raise RuntimeError("old G1 archive parameters changed")
