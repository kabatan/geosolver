"""Candidate-private seam that redirects every champion-v1 HP authority load.

Call ``install(implementation)`` immediately after loading
``candidates/adaptive_hp/adapter.py`` and before ``run_champion_adapter``.
No search, schedule, endpoint, or exactification policy is changed.
"""

from __future__ import annotations

import hashlib
from pathlib import Path


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[4]
AUTHORITY_WRAPPER = HERE / "authority_adapter_wrapper.py"
THIN_RUNNER = (
    ROOT
    / "research/experiments/EXP-REAL61-008/hp_precision_schedule_v11/run_candidate_one.py"
)
BROYDEN_RUNNER = (
    ROOT
    / "research/experiments/EXP-REAL61-008/hp_combined_broyden_publicgate_v17/run_candidate_one.py"
)
PUBLIC_RUNNER = (
    ROOT
    / "research/experiments/EXP-REAL61-008/public_gate_progressive_hp_v16/run_candidate_one.py"
)
EXPECTED_SHA256 = {
    THIN_RUNNER: "d1337a71a2a4caf0d0ea8de54f9e4cb1ba846f7d6c031b8b119a4e97a529b41e",
    BROYDEN_RUNNER: "303ade5a4fec3f896cef6eb4e4fe2f65d42b3446022f40dcb6f528884c0adb6d",
    PUBLIC_RUNNER: "93dc8552fc142a96c8f0d3e16cd41d69e5533fe8eb0891d26edff5e650c78405",
}


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify_seams() -> dict[str, str]:
    observed: dict[str, str] = {}
    for path, expected in EXPECTED_SHA256.items():
        digest = _sha256(path)
        if digest != expected:
            raise RuntimeError(f"champion HP seam changed: {path}")
        observed[str(path)] = digest
    return observed


def install(implementation) -> dict[str, object]:
    """Redirect direct, thin, and event-Broyden adapter loads fail-closed."""

    verify_seams()
    if getattr(implementation, "_point_on_circle_semantic_repair", False):
        return implementation._point_on_circle_semantic_repair_manifest
    if Path(implementation.THIN_RUNNER_PATH).resolve() != THIN_RUNNER.resolve():
        raise RuntimeError("unexpected thin HP runner")
    if Path(implementation.BROYDEN_RUNNER_PATH).resolve() != BROYDEN_RUNNER.resolve():
        raise RuntimeError("unexpected Broyden HP runner")

    implementation.AUTHORITY_ADAPTER_PATH = AUTHORITY_WRAPPER
    original_load = implementation._load_module

    def redirected_load(name, path):
        module = original_load(name, path)
        resolved = Path(path).resolve()
        if resolved == THIN_RUNNER.resolve():
            module.ADAPTER_PATH = AUTHORITY_WRAPPER
        elif resolved == BROYDEN_RUNNER.resolve() and not getattr(
            module, "_point_on_circle_public_runner_redirected", False
        ):
            original_public_load = module._load_public_runner

            def redirected_public_load():
                public = original_public_load()
                if Path(public.ADAPTER_PATH).resolve().name != "adapter.py":
                    raise RuntimeError("unexpected public-gate authority seam")
                public.ADAPTER_PATH = AUTHORITY_WRAPPER
                return public

            module._load_public_runner = redirected_public_load
            module._point_on_circle_public_runner_redirected = True
        return module

    manifest = {
        "schema_version": (
            "geotarget.exp-v15-243.point-on-circle-champion-integration/v1"
        ),
        "authority_wrapper": str(AUTHORITY_WRAPPER),
        "optional_endpoint_canonicalization_enabled": False,
        "source_or_endpoint_modified": False,
        "direct_authority_redirected": True,
        "thin_authority_redirected": True,
        "event_broyden_authority_redirected": True,
        "case_family_truth_target_or_prior_outcome_routing": False,
        "verified_seams": verify_seams(),
    }
    implementation._load_module = redirected_load
    implementation._point_on_circle_semantic_repair = True
    implementation._point_on_circle_semantic_repair_manifest = manifest
    return manifest


__all__ = ["AUTHORITY_WRAPPER", "install", "verify_seams"]

