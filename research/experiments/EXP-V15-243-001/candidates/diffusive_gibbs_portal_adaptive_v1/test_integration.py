from __future__ import annotations

import importlib.util
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace
import sys

import numpy as np


HERE = Path(__file__).resolve().parent


def _load():
    name = "test_digs_adaptive_integration"
    spec = importlib.util.spec_from_file_location(name, HERE / "search_adapter.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def test_mix_preserves_three_quarters_sources_and_insurance() -> None:
    adapter = _load()
    points = tuple(np.asarray([float(index), -float(index)]) for index in range(16))
    prefix = SimpleNamespace(points=points, sources=tuple(f"s{index}" for index in range(16)))
    proposals = tuple(np.asarray([100.0 + index, 200.0]) for index in range(4))
    mixed, audit = adapter._mixed_prefix(prefix, proposals)
    assert mixed.sources == prefix.sources
    assert audit["digs_prefix_byte_identical"] == 12
    assert audit["digs_prefix_changed"] == 4
    assert audit["digs_zero_mod4_insurance_exact"] == 1
    for index in range(0, 16, 4):
        assert mixed.points[index].tobytes() == points[index].tobytes()


def test_small_prefix_fails_closed_without_replacement() -> None:
    adapter = _load()
    assert adapter._replacement_ordinals(3) == ()
    assert adapter.BINDING_RECORD["canonical_source_replay_modified"] is False
    assert adapter.BINDING_RECORD["scout_callback_fraction_max"] == 0.25


def test_arm_entrypoint_hash_chain() -> None:
    arm = json.loads((HERE / "arm.json").read_text())
    assert arm["entrypoint"] == "full_worker.py"
    assert hashlib.sha256((HERE / "full_worker.py").read_bytes()).hexdigest() == arm[
        "mechanism_hash"
    ]
    wrapper_sha = hashlib.sha256((HERE / "full_wrapper.py").read_bytes()).hexdigest()
    assert wrapper_sha in (HERE / "full_worker.py").read_text()


def test_full_wrapper_noop_and_candidate_binding() -> None:
    path = HERE / "full_wrapper.py"
    name = "test_digs_full_wrapper"
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    wrapper = importlib.util.module_from_spec(spec)
    sys.modules[name] = wrapper
    spec.loader.exec_module(wrapper)
    root = Path("/home/kabatan/work/solver-experiment-runtime/solver")
    control = wrapper.configure(frozen_root=root, enable_portal=False)
    assert control.CHAMPION.BASE.SEARCH_ARM == (
        "precision_isolated_retained_then_strict_nearroot_restart_direct_broyden_ruiz_tr_lm"
    )
    candidate = wrapper.configure(frozen_root=root, enable_portal=True)
    assert candidate.CHAMPION.BASE.SEARCH_ARM == wrapper.SEARCH_ARM
    assert candidate.CHAMPION.BASE.SEARCH_WORKER == HERE / "search_worker.py"
