"""Hash-pinned public old-G1 panel loaded against the protected candidate."""

from __future__ import annotations

import hashlib
import importlib.util
from pathlib import Path
import sys

from frozen import candidate, typed_guard_adapter  # noqa: F401


OLD_PANEL = Path(
    "/home/kabatan/work/solver-experiment-runtime/solver/research/experiments/"
    "EXP-V15-243-001/candidates/wave17_guard_stratum_novelty_g1/panel.py"
)
OLD_PANEL_SHA256 = "a8e39a2e4bf7e224e5eb71fa5d7e6860200886f46ff194c7dd2ef3eeb5271186"
if hashlib.sha256(OLD_PANEL.read_bytes()).hexdigest() != OLD_PANEL_SHA256:
    raise RuntimeError("old G1 public panel changed")
spec = importlib.util.spec_from_file_location("protected_affine_old_g1_panel", OLD_PANEL)
if spec is None or spec.loader is None:
    raise ImportError(OLD_PANEL)
_panel = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = _panel
spec.loader.exec_module(_panel)

STRUCTURES = _panel.STRUCTURES
STRATA = _panel.STRATA
SEEDS = _panel.SEEDS
TRANSFORMS = _panel.TRANSFORMS
PREFIX_SIZE = _panel.PREFIX_SIZE
LAUNCHES = _panel.LAUNCHES
build_case = _panel.build_case
run_arm = _panel.run_arm
