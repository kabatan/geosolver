"""One-bit corrective for accepted semantic-invalid restoration moves.

The frozen direct-Broyden source is hash-bound and transformed by exactly one
auditable source-block replacement.  An invalid trial still increments the
same diagnostic counter, but an unconditional semantic refresh is requested
only when the frozen raw acceptance rejects that trial.  If the invalid move
is accepted as lexicographic restoration progress, its usable direct-Broyden
update survives unless one of the unchanged poor-ratio, secant-defect, small-
denominator, linear-failure, or zero-step triggers independently refreshes it.

No evaluator, proposal, coordinate, bound, cache, precision, trust, damping,
acceptance, endpoint, or source-problem behavior is otherwise changed.
"""

from __future__ import annotations

from dataclasses import replace
import hashlib
from pathlib import Path
import sys
from types import ModuleType
from typing import Mapping


HERE = Path(__file__).resolve().parent
BASE_PATH = HERE.parent / "candidate.py"
BASE_SHA256 = "e9c9bd7fc950baafdb90b8899c86ef6286da539b868f6fd0e00664b709dd0caa"
REFERENCE_NAME = (
    "precision_isolated_accepted_invalid_retained_direct_broyden_ruiz_tr_lm"
)

OLD_BLOCK = """        if not trial.semantics_valid:
            counters["semantic_invalid_trials"] += 1
            _request_refresh(counters, "semantic_invalid")
            refresh_requested = True
"""

NEW_BLOCK = """        if not trial.semantics_valid:
            counters["semantic_invalid_trials"] += 1
            accepted_invalid_restoration, _accepted_invalid_reason = (
                _ROW._ROW._raw_nonmonotone_accept(
                    trial,
                    current,
                    tuple(objectives),
                    tuple(relation_norms),
                    predicted_reduction,
                    base,
                )
            )
            if not accepted_invalid_restoration:
                _request_refresh(counters, "semantic_invalid")
                refresh_requested = True
"""


def _load_patched_base() -> tuple[ModuleType, str]:
    source_bytes = BASE_PATH.read_bytes()
    if hashlib.sha256(source_bytes).hexdigest() != BASE_SHA256:
        raise RuntimeError("frozen direct-Broyden base candidate changed")
    source = source_bytes.decode("utf-8")
    if source.count(OLD_BLOCK) != 1:
        raise RuntimeError("approved semantic-invalid refresh block is not unique")
    patched = source.replace(OLD_BLOCK, NEW_BLOCK, 1)
    name = "geotarget_exp008_direct_broyden_accepted_invalid_corrective_kernel"
    cached = sys.modules.get(name)
    if cached is not None:
        return cached, patched
    module = ModuleType(name)
    module.__file__ = str(BASE_PATH)
    module.__package__ = ""
    sys.modules[name] = module
    exec(compile(patched, str(BASE_PATH), "exec"), module.__dict__)
    return module, patched


_PATCHED, PATCHED_SOURCE = _load_patched_base()
PATCHED_SOURCE_SHA256 = hashlib.sha256(PATCHED_SOURCE.encode("utf-8")).hexdigest()
OLD_BLOCK_SHA256 = hashlib.sha256(OLD_BLOCK.encode("utf-8")).hexdigest()
NEW_BLOCK_SHA256 = hashlib.sha256(NEW_BLOCK.encode("utf-8")).hexdigest()

ADProgram = _PATCHED.ADProgram
CandidateOutcome = _PATCHED.CandidateOutcome
Configuration = _PATCHED.Configuration
compile_program = _PATCHED.compile_program
solve_local = _PATCHED.solve_local
REFERENCE = replace(_PATCHED.REFERENCE, name=REFERENCE_NAME)
CONFIGURATIONS = {REFERENCE_NAME: REFERENCE}


def configuration_manifest(
    configuration: Configuration = REFERENCE,
) -> Mapping[str, object]:
    payload = dict(_PATCHED.configuration_manifest(configuration))
    payload.update(
        {
            "candidate": configuration.name,
            "corrective_wave": "accepted semantic-invalid restoration retains usable direct-Broyden update",
            "frozen_base_candidate_sha256": BASE_SHA256,
            "patched_kernel_source_sha256": PATCHED_SOURCE_SHA256,
            "source_patch_replacement_count": 1,
            "old_block_sha256": OLD_BLOCK_SHA256,
            "new_block_sha256": NEW_BLOCK_SHA256,
            "only_behavioral_delta": (
                "semantic-invalid refresh predicate: refresh rejected invalid; "
                "accepted invalid relies on unchanged independent model-quality triggers"
            ),
            "refresh_triggers": [
                "rejected or exception semantic-invalid trial",
                "two consecutive raw model ratios below 0.05",
                "accepted pre-update secant defect above 0.85",
                "linear or zero-step model failure",
                "unusable Broyden denominator",
            ],
            "accepted_invalid_move_acceptance_authority": (
                "same frozen raw lexicographic/nonmonotone predicate, evaluated twice "
                "without an evaluator call"
            ),
            "proposal_precision_cache_trust_damping_and_step_solver_changed": False,
            "source_problem_modified": False,
            "variables_or_equations_changed": False,
            "source_rewrite_or_reparameterization": False,
            "gauge_or_symmetry_reduction": False,
            "added_or_inferred_bounds": False,
            "case_family_truth_target_count_or_outcome_routing": False,
        }
    )
    return payload


def delta_manifest() -> Mapping[str, object]:
    return {
        "base_candidate_sha256": BASE_SHA256,
        "patched_kernel_source_sha256": PATCHED_SOURCE_SHA256,
        "replacement_count": 1,
        "old_block_sha256": OLD_BLOCK_SHA256,
        "new_block_sha256": NEW_BLOCK_SHA256,
        "old_block_occurrences_in_base": BASE_PATH.read_text(encoding="utf-8").count(
            OLD_BLOCK
        ),
        "all_other_base_source_bytes_preserved": True,
    }


__all__ = [
    "ADProgram",
    "BASE_SHA256",
    "CONFIGURATIONS",
    "CandidateOutcome",
    "Configuration",
    "PATCHED_SOURCE_SHA256",
    "REFERENCE",
    "REFERENCE_NAME",
    "compile_program",
    "configuration_manifest",
    "delta_manifest",
    "solve_local",
]
