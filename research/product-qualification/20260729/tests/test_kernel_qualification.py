from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass

import numpy as np

from geotarget.kernel_qualification import (
    HarnessConfig,
    Observation,
    _synthetic_unseen_problem,
    compare_core_observations,
    compare_observations,
    generate_probes,
    qualify_cases,
)


def _observation(value: float = 1.0, *, branch: str = "principal") -> Observation:
    return Observation(
        values=(4.0, value),
        transcendental_indices=(1,),
        transcendental_branches=(branch,),
        residuals=(0.0, -0.0),
        guard_outcomes=(True, False),
        hard_feasible=True,
        candidate_record={"record_id": "r0", "rank": 0},
    )


def test_numeric_contract_is_bitwise_except_same_branch_transcendentals() -> None:
    reference = _observation()
    two_ulp = np.nextafter(np.nextafter(1.0, 2.0), 2.0)
    assert compare_observations(reference, _observation(float(two_ulp))) != ()
    assert (
        compare_observations(
            reference,
            _observation(float(two_ulp)),
            allow_transcendental_2ulp=True,
        )
        == ()
    )

    three_ulp = np.nextafter(two_ulp, 2.0)
    assert "value[1]:more_than_2_ulp" in compare_observations(
        reference,
        _observation(float(three_ulp)),
        allow_transcendental_2ulp=True,
    )
    assert "transcendental_branch" in compare_observations(
        reference, _observation(1.0, branch="alternate")
    )

    signed_zero = Observation(
        **{
            **reference.__dict__,
            "values": (-0.0, 1.0),
        }
    )
    positive_zero = Observation(
        **{
            **reference.__dict__,
            "values": (0.0, 1.0),
        }
    )
    assert "value[0]:not_bitwise_equal" in compare_observations(
        signed_zero, positive_zero
    )


def test_decision_fields_are_exactly_equal() -> None:
    reference = _observation()
    changed_record = Observation(
        **{**reference.__dict__, "candidate_record": {"record_id": "r1", "rank": 0}}
    )
    changed_residual = Observation(
        **{**reference.__dict__, "residuals": (0.0, 0.0)}
    )
    changed_guard = Observation(
        **{**reference.__dict__, "guard_outcomes": (False, False)}
    )
    changed_feasibility = Observation(
        **{**reference.__dict__, "hard_feasible": False}
    )
    assert "candidate_record" in compare_observations(reference, changed_record)
    assert "residuals" in compare_observations(reference, changed_residual)
    assert "guards" in compare_observations(reference, changed_guard)
    assert "hard_feasibility" in compare_observations(reference, changed_feasibility)
    signed_record_zero = Observation(
        **{**reference.__dict__, "candidate_record": {"value": -0.0}}
    )
    positive_record_zero = Observation(
        **{**reference.__dict__, "candidate_record": {"value": 0.0}}
    )
    assert "candidate_record" in compare_observations(
        signed_record_zero, positive_record_zero
    )
    changed_selector = Observation(
        **{**reference.__dict__, "selector_trace": ("P:near:2:0",)}
    )
    assert "selector_trace" in compare_observations(reference, changed_selector)


def test_transcendental_residual_tolerance_is_shadow_only_and_branch_bound() -> None:
    two_ulp = float(np.nextafter(np.nextafter(1.0, 2.0), 2.0))
    reference = Observation(
        values=(),
        residuals=(1.0,),
        transcendental_residual_indices=(0,),
        transcendental_residual_branches=("positive",),
    )
    candidate = Observation(
        values=(),
        residuals=(two_ulp,),
        transcendental_residual_indices=(0,),
        transcendental_residual_branches=("positive",),
    )
    assert "residuals" in compare_observations(reference, candidate)
    assert (
        compare_observations(
            reference, candidate, allow_transcendental_2ulp=True
        )
        == ()
    )
    wrong_branch = Observation(
        **{
            **candidate.__dict__,
            "transcendental_residual_branches": ("negative",),
        }
    )
    assert "transcendental_residual_branch" in compare_observations(
        reference, wrong_branch, allow_transcendental_2ulp=True
    )


def test_core_determinism_is_bitwise_even_for_transcendentals() -> None:
    one_core = _observation()
    one_ulp = _observation(float(np.nextafter(1.0, 2.0)))

    assert (
        compare_observations(
            one_core, one_ulp, allow_transcendental_2ulp=True
        )
        == ()
    )
    assert "core_value_not_bitwise_equal" in compare_core_observations(
        one_core, one_ulp
    )


def test_probe_generation_covers_random_boundaries_and_degeneracy() -> None:
    probes = generate_probes(
        "1" * 64,
        (-1.0, -np.inf),
        (1.0, np.inf),
        HarnessConfig(random_probes_per_problem=3),
    )
    kinds = {probe.kind.split(":", 1)[0] for probe in probes}
    assert kinds == {"random", "boundary", "degenerate"}
    assert all(probe.point.dtype == np.float64 for probe in probes)
    assert all(np.array_equal(probe.point, probe.point.copy()) for probe in probes)


def test_synthetic_problem_changes_identity_and_numeric_data_not_ast_types() -> None:
    original = {
        "id": "corpus-case",
        "constraints": [{"def": "Distance(A, B)", "value": 3}],
        "construction": [],
    }
    synthetic = _synthetic_unseen_problem(original, "a" * 64)

    assert synthetic["id"].startswith("kernel-unseen-")
    assert synthetic["constraints"][0]["value"] == 4
    assert isinstance(synthetic["constraints"][0]["value"], int)
    assert original["constraints"][0]["value"] == 3


@dataclass
class FakePrepared:
    case_id: str
    cores: int
    compiled_supported: bool
    corrupt_core: int | None = None
    dimension: int = 1
    lower: tuple[float, ...] = (-1.0,)
    upper: tuple[float, ...] = (1.0,)
    selector_kinds: tuple[str, ...] = ()

    @property
    def support_decision_trace(self):
        opcodes = ["Add", "Distance"]
        if not self.compiled_supported:
            opcodes.append("UnsupportedPrimitive")
            opcodes.sort()
        types = ["Scalar"]
        selectors = sorted(self.selector_kinds)
        semantic_abi = "test.v15/1"
        support_key = hashlib.sha256(
            json.dumps(
                {
                    "ast_opcode_set": opcodes,
                    "resolved_operand_result_type_set": types,
                    "selector_kind_set": selectors,
                    "semantic_abi_version": semantic_abi,
                },
                sort_keys=True,
                separators=(",", ":"),
            ).encode()
        ).hexdigest()
        return {
            "ast_opcode_set": opcodes,
            "resolved_operand_result_type_set": types,
            "selector_kind_set": selectors,
            "semantic_abi_version": semantic_abi,
            "support_key_sha256": support_key,
            "problem_id_read": False,
            "corpus_membership_read": False,
            "truth_read": False,
            "answer_count_read": False,
        }

    @property
    def fallback_reason(self) -> str | None:
        return None if self.compiled_supported else "unsupported_test_node"

    def reference(self, point: np.ndarray) -> Observation:
        return Observation(
            values=(float(point[0]),),
            residuals=(float(point[0]),),
            guard_outcomes=(point[0] >= 0,),
            hard_feasible=bool(abs(point[0]) <= 1),
            candidate_record={
                "case_id": self.case_id,
                "accepted": bool(point[0] >= 0),
                "endpoint_sha256": "e" * 64,
                "record_id": f"{self.case_id}:r0",
                "admission_role": "accepted" if point[0] >= 0 else "rejected",
            },
        )

    def candidate(self, point: np.ndarray) -> Observation:
        result = self.reference(point)
        if self.corrupt_core == self.cores:
            return Observation(**{**result.__dict__, "hard_feasible": not result.hard_feasible})
        return result

    def optimizer_replay_probes(self):
        return (
            {
                "trace_id": f"{self.case_id}:visited",
                "point": [0.25],
                "candidate_record": {
                    "case_id": self.case_id,
                    "accepted": True,
                    "endpoint_sha256": "e" * 64,
                    "record_id": f"{self.case_id}:r0",
                    "admission_role": "accepted",
                },
            },
        )


class FakeAdapter:
    def __init__(self, *, corrupt_core: int | None = None) -> None:
        self.corrupt_core = corrupt_core

    def compiler_manifest(self):
        return {
            "case_specific_routing": False,
            "support_decision_basis": "ast_opcode_type_selector_semantic_abi_only",
            "forbidden_support_inputs": [
                "problem_id",
                "corpus_membership",
                "truth",
                "answer_count",
            ],
            "support_decision_key_fields": [
                "ast_opcode_set",
                "resolved_operand_result_type_set",
                "selector_kind_set",
                "semantic_abi_version",
            ],
            "support_key_includes_problem_id": False,
            "support_key_includes_source_sha256": False,
            "support_key_includes_problem_hash": False,
            "support_key_includes_corpus_shape": False,
        }

    def support_decision_source(self):
        return """
def supports(ast_opcode_set, resolved_types, selector_kinds, semantic_abi_version):
    return all(item in ALLOWED for item in ast_opcode_set + resolved_types + selector_kinds)
"""

    def qualification_capabilities(self):
        return {
            "optimizer_replay": True,
            "candidate_records": True,
            "actual_parallel_execution": True,
            "parallel_core_counts": [1, 2, 4, 8, 15],
        }

    def prepare(self, problem, *, cores: int) -> FakePrepared:
        source = json.dumps(problem)
        selectors = tuple(
            name for name in ("near", "far", "exclude") if f"{name}=" in source
        )
        return FakePrepared(
            case_id=problem["id"],
            cores=cores,
            compiled_supported=not problem.get("force_fallback", False),
            corrupt_core=self.corrupt_core,
            selector_kinds=selectors,
        )


def _cases() -> list[tuple[str, dict, str]]:
    cases = []
    for ordinal in range(145):
        problem = {
            "id": f"case-{ordinal:03d}",
            "force_fallback": ordinal == 0,
        }
        payload = json.dumps(problem, sort_keys=True).encode()
        cases.append(
            (problem["id"], problem, hashlib.sha256(payload).hexdigest())
        )
    return cases


def test_report_gates_145_cases_fallback_and_all_core_counts() -> None:
    report = qualify_cases(
        _cases(),
        FakeAdapter(),
        HarnessConfig(random_probes_per_problem=1, maximum_boundary_coordinates=1),
    )

    assert report["passed"] is True
    assert report["case_count"] == 145
    assert report["fallback_case_count"] == 1
    assert report["optimizer_replay_probe_count"] == 145
    assert report["optimizer_replay_candidate_record_count"] == 145
    assert report["synthetic_unseen_case_count"] == 145
    assert report["policy"]["cores"] == [1, 2, 4, 8, 15]
    assert all(report["gates"].values())


def test_report_rejects_one_core_decision_drift() -> None:
    report = qualify_cases(
        _cases(),
        FakeAdapter(corrupt_core=8),
        HarnessConfig(random_probes_per_problem=0, maximum_boundary_coordinates=0),
    )

    assert report["passed"] is False
    assert report["gates"]["decision_fields_passed"] is False
    assert report["gates"]["core_determinism_1_2_4_8_15_passed"] is False
    assert any(
        row["kind"] == "core_determinism" and row["core"] == 8
        for row in report["mismatch_examples"]
    )


def test_experimental_two_ulp_study_can_never_produce_a_production_pass() -> None:
    report = qualify_cases(
        _cases(),
        FakeAdapter(),
        HarnessConfig(
            random_probes_per_problem=0,
            maximum_boundary_coordinates=0,
            report_mode="experimental_numeric_equivalence",
        ),
    )

    assert report["study_passed"] is True
    assert report["production_admissible"] is False
    assert report["passed"] is False


class CaseRoutedAdapter(FakeAdapter):
    def prepare(self, problem, *, cores: int) -> FakePrepared:
        prepared = super().prepare(problem, cores=cores)
        if str(problem["id"]).startswith("kernel-unseen-"):
            prepared.compiled_supported = False
        return prepared


def test_synthetic_unseen_problem_rejects_case_specific_support_routing() -> None:
    report = qualify_cases(
        _cases(),
        CaseRoutedAdapter(),
        HarnessConfig(random_probes_per_problem=0, maximum_boundary_coordinates=0),
    )

    assert report["passed"] is False
    assert report["gates"]["synthetic_unseen_route_passed"] is False
    assert any(
        row["kind"] == "synthetic_unseen_route"
        for row in report["mismatch_examples"]
    )


class CapabilityFreeAdapter(FakeAdapter):
    qualification_capabilities = None


def test_missing_optimizer_and_parallel_capabilities_fail_closed() -> None:
    report = qualify_cases(
        _cases(),
        CapabilityFreeAdapter(),
        HarnessConfig(random_probes_per_problem=0, maximum_boundary_coordinates=0),
    )

    assert report["passed"] is False
    assert report["gates"]["optimizer_replay_capability_passed"] is False
    assert report["gates"]["parallel_determinism_capability_passed"] is False
    assert report["gates"]["core_determinism_1_2_4_8_15_passed"] is False


class ManifestViolationAdapter(FakeAdapter):
    def compiler_manifest(self):
        return {
            **super().compiler_manifest(),
            "case_specific_routing": True,
        }


def test_manifest_rejects_case_specific_routing_attestation() -> None:
    report = qualify_cases(
        _cases(),
        ManifestViolationAdapter(),
        HarnessConfig(random_probes_per_problem=0, maximum_boundary_coordinates=0),
    )
    assert report["passed"] is False
    assert report["gates"]["compiler_generality_manifest_passed"] is False


class StaticRoutingViolationAdapter(FakeAdapter):
    def support_decision_source(self):
        return """
def supports(ast_primitive_set, inferred_type_set, problem_id):
    return problem_id in KNOWN_CASES
"""


def test_static_support_audit_rejects_problem_identity_reads() -> None:
    report = qualify_cases(
        _cases(),
        StaticRoutingViolationAdapter(),
        HarnessConfig(random_probes_per_problem=0, maximum_boundary_coordinates=0),
    )
    assert report["passed"] is False
    assert report["gates"]["compiler_generality_manifest_passed"] is False
    assert any(
        "static_support_source:problem_id" in row.get("fields", [])
        for row in report["mismatch_examples"]
    )


class IndependentFixtureFallbackAdapter(FakeAdapter):
    def prepare(self, problem, *, cores: int) -> FakePrepared:
        prepared = super().prepare(problem, cores=cores)
        if str(problem.get("id", "")).startswith("kernel-independent-"):
            prepared.compiled_supported = False
        return prepared


def test_independent_selector_compositions_must_enter_compiled_route() -> None:
    report = qualify_cases(
        _cases(),
        IndependentFixtureFallbackAdapter(),
        HarnessConfig(random_probes_per_problem=0, maximum_boundary_coordinates=0),
    )
    assert report["passed"] is False
    assert report["gates"]["independent_ast_composition_passed"] is False


class EmptyTracePrepared(FakePrepared):
    @property
    def support_decision_trace(self):
        if not self.compiled_supported:
            return {
                "ast_opcode_set": [],
                "resolved_operand_result_type_set": [],
                "selector_kind_set": [],
                "semantic_abi_version": "test.v15/1",
                "support_key_sha256": hashlib.sha256(b"empty").hexdigest(),
                "problem_id_read": False,
                "corpus_membership_read": False,
                "truth_read": False,
                "answer_count_read": False,
            }
        return super().support_decision_trace


class EmptyFallbackTraceAdapter(FakeAdapter):
    def prepare(self, problem, *, cores: int) -> FakePrepared:
        prepared = super().prepare(problem, cores=cores)
        return EmptyTracePrepared(**prepared.__dict__)


def test_fallback_support_trace_must_retain_actual_nonempty_signature() -> None:
    report = qualify_cases(
        _cases(),
        EmptyFallbackTraceAdapter(),
        HarnessConfig(random_probes_per_problem=0, maximum_boundary_coordinates=0),
    )
    assert report["passed"] is False
    assert report["gates"]["support_decision_trace_passed"] is False
