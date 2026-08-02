"""Bind the frozen endpoint bridge to an authenticated adaptive-HP closure."""

from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
from typing import Mapping


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[4]
FROZEN_BRIDGE = (
    ROOT
    / "research/experiments/EXP-REAL61-008/"
    "hp_endpoint_bridge_v10/run_one_endpoint.py"
)
MANIFEST_PATH = HERE / "transitive_manifest.py"

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _load(name: str, path: Path):
    specification = importlib.util.spec_from_file_location(name, path)
    if specification is None or specification.loader is None:
        raise ImportError(path)
    module = importlib.util.module_from_spec(specification)
    sys.modules[name] = module
    specification.loader.exec_module(module)
    return module


def _manifest_verified(
    document: object,
    *,
    closure_sha256: str,
    arm: str,
) -> bool:
    if not isinstance(document, Mapping):
        return False
    metadata = document.get("adaptive_hp_bridge")
    if not isinstance(metadata, Mapping):
        return False
    verification = metadata.get("transitive_manifest_verification")
    return bool(
        isinstance(verification, Mapping)
        and verification.get("arm") == arm
        and verification.get("closure_sha256") == closure_sha256
        and verification.get("verified_before_backend_load") is True
        and verification.get("verified_before_artifact_write") is True
    )


def _closure_is_current(
    manifest_module: object,
    *,
    closure_sha256: str,
    arm: str,
) -> bool:
    """Recompute the closure at the outer bridge acceptance boundary."""

    try:
        observed = manifest_module.build_manifest(arm)
    except Exception:
        return False
    return bool(
        isinstance(observed, Mapping)
        and observed.get("arm") == arm
        and observed.get("closure_sha256") == closure_sha256
    )


def run_bridge(arm: str) -> None:
    manifest_module = _load(
        "geotarget_exp_v15_243_adaptive_hp_bridge_manifest",
        MANIFEST_PATH,
    )
    manifest = manifest_module.build_manifest(arm)
    bridge = _load(
        f"geotarget_exp_v15_243_adaptive_hp_guarded_bridge_{arm.lower()}",
        FROZEN_BRIDGE,
    )
    if arm == manifest_module.ARM_WITH_1280:
        worker = HERE / "champion_composition_worker.py"
    elif arm == manifest_module.ARM_NO_1280:
        worker = HERE / "champion_composition_worker_no_1280.py"
    else:
        raise SystemExit(f"unknown adaptive HP bridge arm: {arm}")

    bridge.WORKER = worker
    bridge.THREAD_ENVIRONMENT[manifest_module.ARM_ENV] = arm
    bridge.THREAD_ENVIRONMENT[manifest_module.CLOSURE_ENV] = manifest[
        "closure_sha256"
    ]

    original_write = bridge.atomic_write_json

    def authenticated_write(path: Path, document: object) -> None:
        if isinstance(document, Mapping):
            document = dict(document)
            schema = document.get("schema_version")
            if schema == "geotarget.exp008-single-raw-endpoint-hp-plan/v1":
                document["transitive_implementation_manifest"] = manifest
                document["execution_environment_contract"] = {
                    "arm_variable": manifest_module.ARM_ENV,
                    "arm": arm,
                    "closure_variable": manifest_module.CLOSURE_ENV,
                    "closure_sha256": manifest["closure_sha256"],
                    "worker_recomputes_before_backend_load": True,
                    "worker_recomputes_before_artifact_write": True,
                    "bridge_recomputes_before_artifact_acceptance": True,
                    "bridge_rejects_unverified_artifact": True,
                }
            elif schema == "geotarget.exp008-single-raw-endpoint-hp-result/v1":
                document["transitive_implementation_arm"] = arm
                document["transitive_implementation_closure_sha256"] = manifest[
                    "closure_sha256"
                ]
                document["transitive_implementation_current_at_result_write"] = (
                    _closure_is_current(
                        manifest_module,
                        closure_sha256=manifest["closure_sha256"],
                        arm=arm,
                    )
                )
        original_write(path, document)

    original_accepted = bridge._accepted

    def authenticated_accepted(
        document: object,
        source_sha256: str,
        endpoint_sha256: str,
    ) -> bool:
        return bool(
            _closure_is_current(
                manifest_module,
                closure_sha256=manifest["closure_sha256"],
                arm=arm,
            )
            and original_accepted(document, source_sha256, endpoint_sha256)
            and _manifest_verified(
                document,
                closure_sha256=manifest["closure_sha256"],
                arm=arm,
            )
        )

    bridge.atomic_write_json = authenticated_write
    bridge._accepted = authenticated_accepted
    bridge.main()


__all__ = ["run_bridge"]
