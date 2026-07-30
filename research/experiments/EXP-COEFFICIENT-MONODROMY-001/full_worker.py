"""Current adaptive full worker plus leftover-only coefficient-monodromy tail."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import sys
import time
import types
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
ADAPTIVE_ROOT = (
    ROOT / "research/experiments/EXP-V15-243-001/candidates/"
    "progressive_adaptive_hybrid_v1"
)
ADAPTIVE_ENTRYPOINT = ADAPTIVE_ROOT / "full_worker.py"
ADAPTIVE_ENTRYPOINT_SHA256 = (
    "7d6f168d8679732c672842e6b7a44573d190449ad0fbe4cc09a7b9112ddc9500"
)
ADAPTIVE_WRAPPER = ADAPTIVE_ROOT / "full_wrapper.py"
ADAPTIVE_WRAPPER_SHA256 = (
    "4c4640a3bce5719d66f577c0093eabe93916476e319b8a595003a16f73dfb9b4"
)
THIN_CONNECTION = HERE / "thin_real_connection.py"
THIN_CONNECTION_SHA256 = (
    "7717d71071e9d600a1ec2a1bad3fccd5d20f4b264d5bc7af4efa7cbfc8e7241f"
)
DEFAULT_FROZEN_ROOT = Path("/home/kabatan/work/solver-experiment-runtime/solver")
BASELINE_FLOOR = 0.75
BASELINE_SERVICE_FRACTION = 1.0
ROUTE_TOTAL_WORK = 16_000
MIN_SIDE_SECONDS = 0.05


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load(name: str, path: Path) -> Any:
    specification = importlib.util.spec_from_file_location(name, path)
    if specification is None or specification.loader is None:
        raise RuntimeError(f"cannot import {path}")
    module = importlib.util.module_from_spec(specification)
    sys.modules[name] = module
    specification.loader.exec_module(module)
    return module


def _load_thin_connection() -> Any:
    # A private package name makes thin_real_connection's relative import bind
    # this experiment's coefficient candidate, never another generic module.
    package_name = "geotarget_coefficient_monodromy_full_worker_private"
    package = types.ModuleType(package_name)
    package.__path__ = [str(HERE)]
    sys.modules[package_name] = package
    return _load(f"{package_name}.thin_real_connection", THIN_CONNECTION)


def _verify_dependencies() -> None:
    expected = {
        ADAPTIVE_ENTRYPOINT: ADAPTIVE_ENTRYPOINT_SHA256,
        ADAPTIVE_WRAPPER: ADAPTIVE_WRAPPER_SHA256,
        THIN_CONNECTION: THIN_CONNECTION_SHA256,
    }
    for path, digest in expected.items():
        if not path.is_file() or _sha256(path) != digest:
            raise RuntimeError(f"full-worker dependency changed: {path}")


_verify_dependencies()
ADAPTIVE = _load(
    "geotarget_coefficient_monodromy_current_adaptive_wrapper",
    ADAPTIVE_WRAPPER,
)
THIN = _load_thin_connection()


def _baseline_payload(
    descriptors: Mapping[str, Mapping[str, object]], keys: Sequence[str]
) -> bytes:
    return json.dumps(
        [descriptors[key] for key in keys],
        ensure_ascii=False,
        allow_nan=False,
        separators=(",", ":"),
    ).encode("utf-8")


def _successful_start(
    descriptor_key: Any,
    candidates: Sequence[Any],
    attempts: Sequence[Mapping[str, object]],
    baseline_keys: frozenset[str],
):
    by_digest = {candidate.endpoint_sha256: candidate for candidate in candidates}
    for attempt in attempts:
        descriptor = attempt.get("descriptor")
        digest = attempt.get("endpoint_float64_sha256")
        if (
            attempt.get("authority_pass") is True
            and isinstance(descriptor, Mapping)
            and isinstance(digest, str)
            and digest in by_digest
        ):
            key = descriptor_key(descriptor)
            if key in baseline_keys:
                return by_digest[digest], key
    return None


def install(
    base: Any,
    *,
    frozen_root: Path,
    clock=time.monotonic,
    thin: Any = THIN,
) -> dict[str, object]:
    """Install one candidate-private post-search service decorator."""

    original_service = base._service_candidates
    original_plan = base._plan
    original_descriptor_key = base._descriptor_key
    original_fresh_replay = base._fresh_replay_candidates
    original_source_contract = base._source_contract
    final_schema = base.SCHEMA

    def plan_wrapper(**kwargs):
        plan = original_plan(**kwargs)
        decorated = dict(plan)
        decorated.update(
            {
                "coefficient_monodromy_full_worker": True,
                "coefficient_monodromy_worker_sha256": _sha256(Path(__file__)),
                "coefficient_monodromy_thin_connection_sha256": (
                    THIN_CONNECTION_SHA256
                ),
                "coefficient_monodromy_current_adaptive_entrypoint_sha256": (
                    ADAPTIVE_ENTRYPOINT_SHA256
                ),
                "coefficient_monodromy_service_baseline_fraction": (
                    BASELINE_SERVICE_FRACTION
                ),
                "coefficient_monodromy_service_side_fraction": 0.0,
                "coefficient_monodromy_tail_only_after_baseline_return": True,
                "coefficient_monodromy_baseline_service_budget_reduced": False,
                "coefficient_monodromy_zero_surplus_returns_baseline_identity": True,
                "coefficient_monodromy_search_union_or_recluster": False,
                "coefficient_monodromy_global_search_or_subdivision": False,
                "coefficient_monodromy_proposal_authority": False,
                "canonical_source_guard_raw_target_authority_unchanged": True,
                "truth_case_family_target_or_previous_outcome_routing": False,
                "final_result_schema_unchanged": True,
            }
        )
        return decorated

    def service_wrapper(
        *,
        source: Path,
        source_sha256: str,
        candidates: Sequence[Any],
        cpu: int,
        output: Path,
        hard_deadline: float,
    ):
        finalize_reserve = float(base.FINALIZE_RESERVE_SECONDS)
        baseline_result = original_service(
            source=source,
            source_sha256=source_sha256,
            candidates=candidates,
            cpu=cpu,
            output=output,
            hard_deadline=hard_deadline,
        )
        attempts, descriptors, statistics = baseline_result
        try:
            baseline_keys = tuple(descriptors)
            payload = _baseline_payload(descriptors, baseline_keys)
            start = _successful_start(
                original_descriptor_key,
                candidates,
                attempts,
                frozenset(baseline_keys),
            )
        except Exception:  # noqa: BLE001 - decoration must never lose baseline
            return baseline_result
        additions: dict[str, dict[str, object]] = {}
        side_attempts: list[Mapping[str, object]] = []
        side_statistics: list[dict[str, object]] = []
        route_reason = "BASELINE_ONLY_NO_AUTHORITY_START"
        route_eligible = False
        route_used = 0
        if start is None:
            return baseline_result
        if clock() >= hard_deadline - finalize_reserve - MIN_SIDE_SECONDS:
            return baseline_result

        accepted_candidate, accepted_key = start
        try:
            source_payload, document = original_source_contract(source, source_sha256)
            if source.read_bytes() != source_payload:
                raise RuntimeError("source bytes changed during side route")
            replay_ordinal = 0

            def canonical_replay(point: tuple[float, ...]) -> str | None:
                nonlocal replay_ordinal
                if tuple(point) == tuple(accepted_candidate.endpoint):
                    return accepted_key
                if clock() >= hard_deadline - finalize_reserve - MIN_SIDE_SECONDS:
                    return None
                replayed = original_fresh_replay(
                    document,
                    [list(point)],
                    hard_deadline=hard_deadline - finalize_reserve,
                )
                if not replayed:
                    return None
                replay_attempts, replay_descriptors, replay_statistics = (
                    original_service(
                        source=source,
                        source_sha256=source_sha256,
                        candidates=replayed,
                        cpu=cpu,
                        output=(
                            output
                            / "coefficient-monodromy"
                            / f"replay-{replay_ordinal:03d}"
                        ),
                        hard_deadline=hard_deadline,
                    )
                )
                replay_ordinal += 1
                side_attempts.extend(replay_attempts)
                side_statistics.append(dict(replay_statistics))
                if not replay_descriptors:
                    return None
                key = next(iter(replay_descriptors))
                additions.setdefault(key, dict(replay_descriptors[key]))
                return key

            connected = thin.connect(
                document,
                source_sha256=source_sha256,
                accepted_source_point=accepted_candidate.endpoint,
                baseline_payload=payload,
                baseline_descriptors=baseline_keys,
                total_work=ROUTE_TOTAL_WORK,
                canonical_replay=canonical_replay,
                common_control_root=frozen_root,
            )
            if connected.baseline_payload != payload:
                raise RuntimeError("baseline payload bytes changed")
            if connected.descriptors[: len(baseline_keys)] != baseline_keys:
                raise RuntimeError("baseline descriptor order changed")
            allowed = connected.descriptors[len(baseline_keys) :]
            route_reason = connected.reason
            route_eligible = connected.eligible
            route_used = connected.side_work_used
        except Exception:  # noqa: BLE001 - side route fails closed
            return baseline_result

        allowed_additions: list[tuple[str, dict[str, object]]] = []
        for key in allowed:
            if key in descriptors or any(item[0] == key for item in allowed_additions):
                continue
            descriptor = additions.get(key)
            if descriptor is not None:
                allowed_additions.append((key, descriptor))
        if not allowed_additions:
            return baseline_result
        try:
            if tuple(descriptors) != baseline_keys:
                return baseline_result
            if _baseline_payload(descriptors, baseline_keys) != payload:
                return baseline_result
        except Exception:  # noqa: BLE001 - baseline custody fails closed
            return baseline_result

        merged_descriptors = dict(descriptors)
        for key, descriptor in allowed_additions:
            merged_descriptors[key] = descriptor
        if tuple(merged_descriptors)[: len(baseline_keys)] != baseline_keys:
            return baseline_result

        merged_statistics = dict(statistics)
        merged_statistics.update(
            {
                "coefficient_monodromy_binding": (
                    "current adaptive service then additive canonical replay"
                ),
                "coefficient_monodromy_baseline_fraction": (BASELINE_SERVICE_FRACTION),
                "coefficient_monodromy_baseline_deadline": hard_deadline,
                "coefficient_monodromy_hard_deadline": hard_deadline,
                "coefficient_monodromy_baseline_descriptor_count": len(baseline_keys),
                "coefficient_monodromy_baseline_payload_sha256": hashlib.sha256(
                    payload
                ).hexdigest(),
                "coefficient_monodromy_baseline_order_preserved": (
                    tuple(merged_descriptors)[: len(baseline_keys)] == baseline_keys
                ),
                "coefficient_monodromy_side_descriptor_count": (
                    len(merged_descriptors) - len(baseline_keys)
                ),
                "coefficient_monodromy_side_statistics": side_statistics,
                "coefficient_monodromy_route_reason": route_reason,
                "coefficient_monodromy_route_eligible": route_eligible,
                "coefficient_monodromy_charged_side_work": route_used,
                "coefficient_monodromy_truth_or_case_outcome_read": False,
                "coefficient_monodromy_canonical_authority_unchanged": True,
            }
        )
        return list(attempts) + side_attempts, merged_descriptors, merged_statistics

    base._plan = plan_wrapper
    base._service_candidates = service_wrapper
    if base.SCHEMA != final_schema:
        raise RuntimeError("final solve-result schema changed")
    if base._descriptor_key is not original_descriptor_key:
        raise RuntimeError("descriptor authority changed")
    if base._fresh_replay_candidates is not original_fresh_replay:
        raise RuntimeError("source replay seam changed")
    if base._source_contract is not original_source_contract:
        raise RuntimeError("source contract changed")
    return {
        "schema": "geotarget.exp-coefficient-monodromy-full-binding/v2",
        "baseline_fraction": BASELINE_SERVICE_FRACTION,
        "adaptive_entrypoint_sha256": ADAPTIVE_ENTRYPOINT_SHA256,
        "adaptive_wrapper_sha256": ADAPTIVE_WRAPPER_SHA256,
        "thin_connection_sha256": THIN_CONNECTION_SHA256,
        "final_result_schema": final_schema,
        "canonical_authority_unchanged": True,
    }


def configure(*, frozen_root: Path):
    control = ADAPTIVE.configure(
        frozen_root=frozen_root,
        enable_hybrid=True,
    )
    install(control.CHAMPION.BASE, frozen_root=frozen_root)
    return control


def main() -> None:
    frozen_root = Path(
        os.environ.get("GEOTARGET_FROZEN_SOLVER_ROOT", str(DEFAULT_FROZEN_ROOT))
    ).resolve()
    configure(frozen_root=frozen_root).main()


if __name__ == "__main__":
    main()
