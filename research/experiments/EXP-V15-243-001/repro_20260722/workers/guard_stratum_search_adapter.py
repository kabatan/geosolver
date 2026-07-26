"""Minimal legacy-worker seam for the existing guard-stratum scheduler.

This module only adapts the already implemented ``run_paired_arm`` signature
to the frozen v15 search worker signature.  One process handles one source, so
the small source context captured while constructing the literal prefix is
case-private.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
import sys


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[4]
GUARD_ROOT = (
    ROOT
    / "research/experiments/EXP-V15-243-001/candidates/guard_stratum_novelty"
)
GUARD_ADAPTER = GUARD_ROOT / "v15_adapter.py"
SEARCH_ARM = (
    "precision_isolated_retained_then_strict_nearroot_restart_"
    "direct_broyden_ruiz_tr_lm"
)

if str(GUARD_ROOT) not in sys.path:
    sys.path.insert(0, str(GUARD_ROOT))


def _load_guard():
    name = "geotarget_repro_guard_stratum_existing_adapter"
    specification = importlib.util.spec_from_file_location(name, GUARD_ADAPTER)
    if specification is None or specification.loader is None:
        raise ImportError(GUARD_ADAPTER)
    module = importlib.util.module_from_spec(specification)
    sys.modules[name] = module
    specification.loader.exec_module(module)
    return module


GUARD = _load_guard()
ARMS = (SEARCH_ARM,)
BINDING_RECORD = GUARD.binding_record()
_DOCUMENT = None
_SOURCE_SHA256 = None


def build_literal_prefix(document, base_case, base_policy):
    global _DOCUMENT, _SOURCE_SHA256
    _DOCUMENT = document
    _SOURCE_SHA256 = str(base_policy.source_sha256)
    return GUARD.build_literal_prefix(document, base_case, base_policy)


def compile_program(arm, document):
    if arm != SEARCH_ARM:
        raise ValueError(f"unknown arm: {arm!r}")
    return GUARD.compile_program(document)


def run_local_arm(
    arm,
    *,
    base_case,
    budget,
    program,
    literal_prefix,
    callback_cap,
    callbacks_per_start,
    deadline_monotonic,
):
    if arm != SEARCH_ARM or _DOCUMENT is None or _SOURCE_SHA256 is None:
        raise RuntimeError("guard-stratum source context was not initialized")
    return GUARD.run_paired_arm(
        GUARD.CANDIDATE,
        document=_DOCUMENT,
        formulation_sha256=_SOURCE_SHA256,
        evaluator=budget.evaluator,
        base_case=base_case,
        budget=budget,
        program=program,
        literal_prefix=literal_prefix,
        callback_cap=callback_cap,
        callbacks_per_start=callbacks_per_start,
        deadline_monotonic=deadline_monotonic,
    )


def configuration_manifest():
    return {
        **GUARD.configuration_manifest(),
        "legacy_search_arm_alias": SEARCH_ARM,
        "candidate_arm": GUARD.CANDIDATE,
    }


__all__ = [
    "ARMS",
    "BINDING_RECORD",
    "build_literal_prefix",
    "compile_program",
    "configuration_manifest",
    "run_local_arm",
]
