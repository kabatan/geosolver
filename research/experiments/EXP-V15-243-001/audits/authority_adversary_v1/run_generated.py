#!/usr/bin/env python3
"""Fixed generated authority falsification for three experimental candidates."""

from __future__ import annotations

from copy import deepcopy
from fractions import Fraction
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
from typing import Any, Mapping

import sympy as sp


R1_ROOT = Path(
    os.environ.get(
        "GEOTARGET_R1_CANDIDATE_ROOT",
        "/home/kabatan/work/solver-wt/target-constrained-nra-witness/"
        "research/experiments/EXP-V15-243-001/candidates/"
        "target_constrained_exact_nra_witness_v1",
    )
)
HERMITE_ROOT = Path(
    os.environ.get(
        "GEOTARGET_HERMITE_CANDIDATE_ROOT",
        "/home/kabatan/work/solver-wt/certified-hermite-witness/"
        "research/experiments/EXP-V15-243-001/candidates/"
        "target_constrained_certified_hermite_d0",
    )
)
REFLECT_ROOT = Path(
    os.environ.get(
        "GEOTARGET_REFLECT_CANDIDATE_ROOT",
        "/home/kabatan/work/solver-wt/archive-exact-reflect-point/"
        "research/experiments/EXP-V15-243-001/candidates/"
        "archive_exact_reflect_point_v1",
    )
)
EXPECTED = {
    R1_ROOT / "candidate.py": (
        "7b98bdfb018d566994291ad75cb2e7f28f62adc960a784ca54d3b68b796586ff"
    ),
    HERMITE_ROOT / "candidate.py": (
        "c0506a294f5d09fa75a5abe37942fd59038b116d58facd45cf77e8a2ff9bdbe8"
    ),
    HERMITE_ROOT / "verifier.py": (
        "5189a3ca7b2629fd9e537499689e9b3ce8ae3048121167c612bb0bf4ac6c2c6d"
    ),
    REFLECT_ROOT / "private_candidate.py": (
        "8c9f5b656db49344b1514b4cfcc293479d016218c05d307a6b5c108adf706fc4"
    ),
    REFLECT_ROOT / "worker.py": (
        "4dcd978baa2070a0fe97b74c5b2668f967ab10339425b72abc3a7c75bc6974ca"
    ),
}
SNAPSHOT_COMMITS = {
    "r1-nra": "0bbc3f8d45ea1c3c22f8d35dd2aa2fa0f0922e97",
    "hermite-d0": "db590f312e744d2c1c08709aeb52e893ca493785",
    "reflect-exact": "a0f2edec83873bc0a3037d09660bd9a11810d915",
}
JULIA = "/home/kabatan/.juliaup/bin/julia"
JULIA_PROJECT = Path(
    "/home/kabatan/work/solver-experiment-runtime/solver/research/experiments/"
    "EXP-REAL61-002/target_elimination"
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load(name: str, path: Path):
    specification = importlib.util.spec_from_file_location(name, path)
    if specification is None or specification.loader is None:
        raise ImportError(path)
    module = importlib.util.module_from_spec(specification)
    sys.modules[name] = module
    specification.loader.exec_module(module)
    return module


def _verify_snapshots() -> dict[str, str]:
    observed = {str(path): _sha256(path) if path.is_file() else "MISSING" for path in EXPECTED}
    expected = {str(path): digest for path, digest in EXPECTED.items()}
    if observed != expected:
        raise RuntimeError(f"candidate snapshot mismatch: {observed}")
    return observed


def _r1_final(result: Mapping[str, Any]) -> bool:
    replay = result.get("independent_replay")
    required = (
        "untouched_source_equations",
        "typed_boolean_guard",
        "division_definedness",
        "raw_target_link",
        "proposal_polynomial_isolator_ordinal",
    )
    return bool(
        result.get("status") == "TARGET_CONSTRAINED_EXACT_WITNESS_READY"
        and result.get("authority_pass") is True
        and isinstance(replay, Mapping)
        and replay.get("pass") is True
        and all(replay.get(name) is True for name in required)
    )


def _reflect_final(result: Mapping[str, Any]) -> bool:
    return bool(
        result.get("status") == "EXACT_TARGET_AUTHORITY_READY"
        and result.get("authority_pass") is True
        and result.get("root_ordinal_attestation_complete") is True
        and result.get("source_raw_answer_exact") is True
        and result.get("target_link_exact") is True
    )


def _record(
    lane: str,
    name: str,
    *,
    expected_final: bool,
    final_authority: bool,
    status: str,
    reason: str | None = None,
    **extra: Any,
) -> dict[str, Any]:
    return {
        "lane": lane,
        "name": name,
        "expected_final_authority": expected_final,
        "final_authority": final_authority,
        "false_authority": bool(final_authority and not expected_final),
        "missed_required_positive": bool(expected_final and not final_authority),
        "status": status,
        "reason": reason,
        **extra,
    }


def _r1_cases(r1) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    x, y = sp.symbols("x y", real=True)

    def source(
        variables,
        equations,
        guard,
        target,
        *,
        definedness=(),
        label="adversary",
    ):
        return r1.PolynomialSource(
            tuple(variables), tuple(equations), guard, target, tuple(definedness), label
        )

    def proposal(coefficients, ordinal, lower, upper):
        return r1.TargetProposal(
            tuple(coefficients), ordinal, Fraction(lower), Fraction(upper)
        )

    sqrt2 = proposal((1, 0, -2), 1, 1, 2)
    regular = source(("x",), (x**2 - 2,), x > 0, x, label="regular")

    cases = [
        (
            "nonradical-embedded-support",
            source(
                ("x", "y"),
                ((x - 1) ** 2, (x - 1) * y, y**2),
                sp.And(x > 0, y + 1 > 0),
                x,
            ),
            proposal((1, -1), 0, Fraction(1, 2), Fraction(3, 2)),
            True,
        ),
        (
            "positive-dimensional-relevant-fibre",
            source(("x", "y"), (x - 1,), y > 0, x),
            proposal((1, -1), 0, Fraction(1, 2), Fraction(3, 2)),
            False,
        ),
        (
            "all-complex-no-real-model",
            source(("x",), (x**2 + 1,), sp.true, x),
            proposal((1, 0), 0, Fraction(-1, 2), Fraction(1, 2)),
            False,
        ),
        (
            "wrong-polynomial-near-numeric-endpoint",
            regular,
            proposal((1_000_000, 0, -2_000_001), 1, 1, 2),
            False,
        ),
        (
            "wrong-root-ordinal-positive-isolator",
            regular,
            proposal((1, 0, -2), 0, 1, 2),
            False,
        ),
        (
            "strict-guard-boundary",
            source(("x",), (x,), x > 0, x),
            proposal((1, 0), 0, Fraction(-1, 2), Fraction(1, 2)),
            False,
        ),
        (
            "boolean-disjunction-valid-selected-branch",
            source(("x",), (x**2 - 1,), sp.Or(x < 0, x > 0), x),
            proposal((1, -1), 0, Fraction(1, 2), Fraction(3, 2)),
            True,
        ),
        (
            "boolean-disjunction-wrong-selector-branch",
            source(("x",), (x**2 - 1,), sp.Or(x < 0, x > 2), x),
            proposal((1, -1), 0, Fraction(1, 2), Fraction(3, 2)),
            False,
        ),
        (
            "phase-sheet-full-turn-expression",
            source(("x",), (x,), sp.true, sp.sin(x + 2 * sp.pi)),
            proposal((1, 0), 0, Fraction(-1, 2), Fraction(1, 2)),
            False,
        ),
        (
            "sqrt-principal-branch-not-polynomial",
            source(("x",), (x - 4,), sp.true, sp.sqrt(x)),
            proposal((1, -2), 0, Fraction(3, 2), Fraction(5, 2)),
            False,
        ),
        (
            "abs-principal-branch-not-polynomial",
            source(("x",), (x + 2,), sp.true, sp.Abs(x)),
            proposal((1, -2), 0, Fraction(3, 2), Fraction(5, 2)),
            False,
        ),
        (
            "division-denominator-zero",
            source(("x",), (x - 1,), sp.true, 1 / (x - 1)),
            proposal((1, 0), 0, Fraction(-1, 2), Fraction(1, 2)),
            False,
        ),
        (
            "irrelevant-unconstrained-aux-explicit-zero-witness",
            source(("x", "y"), (x - 1,), sp.true, x),
            proposal((1, -1), 0, Fraction(1, 2), Fraction(3, 2)),
            True,
        ),
        (
            "guard-relevant-unconstrained-aux",
            source(("x", "y"), (x - 1,), y > 0, x),
            proposal((1, -1), 0, Fraction(1, 2), Fraction(3, 2)),
            False,
        ),
    ]
    accepted_regular: dict[str, Any] | None = None
    for name, problem, proposed, expected_final in cases:
        result = r1.prove(problem, proposed, timeout_seconds=2.0)
        final = _r1_final(result)
        if name == "nonradical-embedded-support" and final:
            accepted_regular = result
        records.append(
            _record(
                "r1-nra",
                name,
                expected_final=expected_final,
                final_authority=final,
                status=str(result.get("status")),
                reason=str(result.get("reason")) if result.get("reason") else None,
            )
        )

    regular_result = r1.prove(regular, sqrt2, timeout_seconds=2.0)
    formula = r1.compile_qf_nra(regular, sqrt2)
    changed_source = source(("x",), (x**2 - 3,), x > 0, x, label="changed")
    replay_ok, replay_reason = r1.independent_replay(
        changed_source,
        sqrt2,
        formula,
        regular_result["model_descriptors"],
    )
    records.append(
        _record(
            "r1-nra",
            "source-mismatch-independent-replay",
            expected_final=False,
            final_authority=bool(replay_ok),
            status="REPLAY_ACCEPTED" if replay_ok else "REPLAY_REJECTED",
            reason=replay_reason,
        )
    )
    mutated_descriptors = deepcopy(regular_result["model_descriptors"])
    mutated_descriptors["x"]["selected_real_root_index"] = 0
    replay_ok, replay_reason = r1.independent_replay(
        regular, sqrt2, formula, mutated_descriptors
    )
    records.append(
        _record(
            "r1-nra",
            "model-wrong-isolator-ordinal",
            expected_final=False,
            final_authority=bool(replay_ok),
            status="REPLAY_ACCEPTED" if replay_ok else "REPLAY_REJECTED",
            reason=replay_reason,
        )
    )
    partial = deepcopy(regular_result)
    partial.pop("independent_replay", None)
    records.append(
        _record(
            "r1-nra",
            "timeout-partial-artifact",
            expected_final=False,
            final_authority=_r1_final(partial),
            status="TRUNCATED_READY_OBJECT",
            reason="independent replay removed",
        )
    )
    timed = r1.prove(regular, sqrt2, timeout_seconds=1e-9)
    records.append(
        _record(
            "r1-nra",
            "backend-timeout",
            expected_final=False,
            final_authority=_r1_final(timed),
            status=str(timed.get("status")),
            reason=str(timed.get("reason")),
        )
    )
    return records


def _hermite_cases(candidate, verifier) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    regular = {
        "variables": ["x", "t"],
        "target_variable": "t",
        "equations": ["x**2 - 2"],
        "target": "x",
        "polynomial": "t**2 - 2",
        "interval": ["1", "2"],
        "guards": ["x"],
    }
    positive = {
        "nonradical-embedded-support": {
            "variables": ["x", "y", "t"],
            "target_variable": "t",
            "equations": ["(x - 1)**2", "(x - 1)*y", "y**2"],
            "target": "x",
            "polynomial": "t - 1",
            "interval": ["1/2", "3/2"],
            "guards": ["x", "y + 1"],
        },
        "positive-dimensional-overall-finite-target-fibre": {
            "variables": ["x", "y", "t"],
            "target_variable": "t",
            "equations": ["y - x**2"],
            "target": "x",
            "polynomial": "(t**2 - 1)*(t**2 - 4)",
            "interval": ["3/2", "5/2"],
            "guards": ["x", "y"],
        },
    }
    negatives = {
        "positive-dimensional-relevant-fibre": {
            "variables": ["x", "y", "t"],
            "target_variable": "t",
            "equations": ["x - 1"],
            "target": "x",
            "polynomial": "t - 1",
            "interval": ["1/2", "3/2"],
            "guards": ["y"],
        },
        "all-complex-no-real": {
            "variables": ["x", "t"],
            "target_variable": "t",
            "equations": ["x**2 + 1"],
            "target": "x",
            "polynomial": "t",
            "interval": ["-1/2", "1/2"],
            "guards": [],
        },
        "wrong-polynomial-near-endpoint": {
            **regular,
            "polynomial": "1000000*t**2 - 2000001",
        },
        "wrong-isolator": {**regular, "interval": ["2", "3"]},
        "strict-guard-boundary": {
            "variables": ["x", "t"],
            "target_variable": "t",
            "equations": ["x"],
            "target": "x",
            "polynomial": "t",
            "interval": ["-1/2", "1/2"],
            "guards": ["x"],
        },
        "boolean-disjunction-not-silently-conjoined": {
            **regular,
            "guards": ["(x > 0) | (x < 0)"],
        },
        "phase-sheet-full-turn-nonpolynomial": {**regular, "target": "sin(x + 2*pi)"},
        "sqrt-principal-branch-nonpolynomial": {**regular, "target": "sqrt(x)"},
        "abs-principal-branch-nonpolynomial": {**regular, "target": "Abs(x)"},
        "division-zero-nonpolynomial": {**regular, "target": "1/(x-x)"},
        "unconstrained-aux": {
            "variables": ["x", "y", "t"],
            "target_variable": "t",
            "equations": ["x - 1"],
            "target": "x",
            "polynomial": "t - 1",
            "interval": ["1/2", "3/2"],
            "guards": [],
        },
    }

    verified_certificate = candidate.certify(regular)
    verified = verifier.verify(regular, verified_certificate)
    records.append(
        _record(
            "hermite-d0",
            "verified-polynomial-certificate-without-untouched-source",
            expected_final=False,
            final_authority=False,
            status="CERTIFICATE_VERIFIED_BUT_SOURCE_REPLAY_ABSENT",
            reason="candidate contract starts after semantic lifting",
            certificate_verified=verified.get("verified") is True,
            has_untouched_source_digest="untouched_source_sha256" in verified_certificate,
            has_untouched_source_replay="untouched_source_replay" in verified_certificate,
        )
    )
    for name, problem in positive.items():
        try:
            certificate = candidate.certify(problem)
            verification = verifier.verify(problem, certificate)
            certificate_ok = verification.get("verified") is True
            status = "CERTIFICATE_VERIFIED"
            reason = None
        except Exception as error:
            certificate_ok = False
            status = "CERTIFICATE_FAILED"
            reason = f"{type(error).__name__}:{error}"
        records.append(
            _record(
                "hermite-d0",
                name,
                expected_final=False,
                final_authority=False,
                status=status,
                reason=reason,
                expected_polynomial_certificate=True,
                polynomial_certificate_verified=certificate_ok,
                untouched_source_replay_present=False,
            )
        )
    for name, problem in negatives.items():
        certificate_claimed = False
        verification_claimed = False
        try:
            certificate = candidate.certify(problem)
            certificate_claimed = True
            verification_claimed = verifier.verify(problem, certificate).get("verified") is True
            status = "NEGATIVE_CERTIFICATE_ISSUED"
            reason = None
        except Exception as error:
            status = "FAIL_CLOSED"
            reason = f"{type(error).__name__}:{error}"
        records.append(
            _record(
                "hermite-d0",
                name,
                expected_final=False,
                final_authority=False,
                status=status,
                reason=reason,
                candidate_false_certificate=bool(certificate_claimed and verification_claimed),
                out_of_subset_uncaught_exception=bool(
                    name == "boolean-disjunction-not-silently-conjoined"
                    and reason is not None
                    and reason.startswith("AttributeError:")
                ),
            )
        )

    mutations = {
        "source-hash-problem-mismatch": lambda cert: cert.update(problem_sha256="0" * 64),
        "wrong-isolator-metadata": lambda cert: cert["target"].update(isolating_interval=["-2", "-1"]),
        "partial-query-artifact": lambda cert: cert["tarski_queries"].pop(),
        "wrong-hermite-entry": lambda cert: cert["tarski_queries"][0]["hermite"][0].__setitem__(0, "999"),
    }
    for name, mutate in mutations.items():
        certificate = deepcopy(verified_certificate)
        mutate(certificate)
        try:
            verifier.verify(regular, certificate)
            rejected = False
            reason = "mutation accepted"
        except Exception as error:
            rejected = True
            reason = f"{type(error).__name__}:{error}"
        records.append(
            _record(
                "hermite-d0",
                name,
                expected_final=False,
                final_authority=not rejected,
                status="MUTATION_REJECTED" if rejected else "MUTATION_ACCEPTED",
                reason=reason,
            )
        )
    records.append(
        _record(
            "hermite-d0",
            "timeout-no-candidate-deadline-contract",
            expected_final=False,
            final_authority=False,
            status="FORMAL_AUTHORITY_DENIED",
            reason="synchronous D0 certify has no deadline or partial-artifact contract",
        )
    )
    return records


def _reflect_document(
    *,
    reflect_expression: str = "Reflect(P, C)",
    answer: str = "R.x",
    guards: list[str] | None = None,
    line: bool = False,
    degenerate_line: bool = False,
) -> dict[str, Any]:
    construction = [{"name": "P", "expr": "Point(x, y)"}]
    if line:
        construction.extend(
            [
                {"name": "A", "expr": "Point(0, 0)"},
                {"name": "B", "expr": "Point(0, 0)" if degenerate_line else "Point(1, 0)"},
                {"name": "L", "expr": "Line(A, B)"},
            ]
        )
    else:
        construction.append({"name": "C", "expr": "Point(4, 7)"})
    construction.append({"name": "R", "expr": reflect_expression})
    return {
        "variables": {"names": ["x", "y"]},
        "construction": construction,
        "constraints": [{"def": "x", "value": 1}, {"def": "y", "value": 2}],
        "guards": [] if guards is None else guards,
        "answer": answer,
    }


def _reflect_call(reflect, document, target, *, timeout=20.0):
    return reflect.certify_exact_coordinate_witness(
        document,
        ["1", "2"],
        ["1", "2"],
        str(target),
        str(target),
        timeout_seconds=timeout,
    )


def _qq_descriptor(coefficients, left, right, ordinal):
    return {
        "coefficients_high_to_low": [str(value) for value in coefficients],
        "isolating_interval": {
            "left": str(left),
            "right": str(right),
            "multiplicity": 1,
            "real_root_index": ordinal,
        },
    }


def _qq_reflect_job(*, target_ordinal: int):
    nodes = [
        {"op": "coordinate", "index": 0},
        {"op": "rational", "value": "0"},
        {"op": "call", "name": "Point", "args": [0, 1], "kwargs": {}},
        {"op": "call", "name": "Point", "args": [1, 1], "kwargs": {}},
        {"op": "call", "name": "Reflect", "args": [2, 3], "kwargs": {}},
        {"op": "call", "name": "CoordinateX", "args": [4], "kwargs": {}},
    ]
    return {
        "truth_used": False,
        "post_process_used": False,
        "coordinate_descriptors": [_qq_descriptor((1, 0, -2), 1, 2, 1)],
        "target_descriptor": _qq_descriptor(
            (1, 0, -2), -2, -1, target_ordinal
        ),
        "nodes": nodes,
        "relation_roots": [],
        "guard_roots": [],
        "bound_roots": [],
        "answer_root": 5,
    }


def _run_qqbar(source: str, job: Mapping[str, Any]) -> dict[str, Any]:
    environment = os.environ.copy()
    environment.update(
        {
            "JULIA_NUM_THREADS": "1",
            "JULIA_NUM_GC_THREADS": "1",
            "OPENBLAS_NUM_THREADS": "1",
            "OMP_NUM_THREADS": "1",
        }
    )
    with tempfile.TemporaryDirectory(prefix="authority-adversary-reflect-") as directory:
        root = Path(directory)
        worker = root / "worker.jl"
        job_path = root / "job.json"
        worker.write_text(source, encoding="utf-8")
        job_path.write_text(json.dumps(job), encoding="utf-8")
        completed = subprocess.run(
            [
                JULIA,
                "--compile=no",
                f"--project={JULIA_PROJECT}",
                "--startup-file=no",
                "--history-file=no",
                str(worker),
                str(job_path),
            ],
            check=True,
            capture_output=True,
            text=True,
            timeout=90,
            env=environment,
        )
    return json.loads(completed.stdout.strip().splitlines()[-1])


def _reflect_cases(reflect) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    cases = [
        (
            "point-reflection-coincident-point-valid",
            {
                "variables": {"names": ["x", "y"]},
                "construction": [
                    {"name": "P", "expr": "Point(x, y)"},
                    {"name": "R", "expr": "Reflect(P, P)"},
                ],
                "constraints": [{"def": "x", "value": 1}, {"def": "y", "value": 2}],
                "guards": [],
                "answer": "R.x",
            },
            "1",
            True,
        ),
        (
            "point-argument-order-confusion",
            _reflect_document(reflect_expression="Reflect(C, P)"),
            "7",
            False,
        ),
        (
            "point-line-correct-overload",
            _reflect_document(
                reflect_expression="Reflect(P, L)", answer="R.y", line=True
            ),
            "-2",
            True,
        ),
        (
            "line-point-wrong-overload",
            _reflect_document(reflect_expression="Reflect(L, P)", line=True),
            "1",
            False,
        ),
        (
            "coincident-line-points-undefined",
            _reflect_document(
                reflect_expression="Reflect(P, L)", line=True, degenerate_line=True
            ),
            "1",
            False,
        ),
        (
            "strict-guard-boundary",
            {
                "variables": {"names": ["x", "y"]},
                "construction": [
                    {"name": "P", "expr": "Point(x, y)"},
                    {"name": "R", "expr": "Reflect(P, P)"},
                ],
                "constraints": [{"def": "x", "value": 1}, {"def": "y", "value": 2}],
                "guards": ["AssumeGt(Distance(P, P), 0)"],
                "answer": "R.x",
            },
            "1",
            False,
        ),
        (
            "wrong-target-near-numeric-endpoint",
            _reflect_document(),
            "70000000000001/10000000000000",
            False,
        ),
        (
            "division-denominator-zero",
            _reflect_document(answer="R.x/(x-x)"),
            "7",
            False,
        ),
        (
            "abs-principal-branch-wrong-sign",
            _reflect_document(answer="abs(R.x)"),
            "-7",
            False,
        ),
        (
            "sqrt-principal-branch-wrong-sign",
            _reflect_document(answer="sqrt(R.x**2)"),
            "-7",
            False,
        ),
        (
            "source-answer-mismatch",
            _reflect_document(answer="R.y"),
            "7",
            False,
        ),
    ]
    valid_result: dict[str, Any] | None = None
    for name, document, target, expected_final in cases:
        result = _reflect_call(reflect, document, target)
        final = _reflect_final(result)
        if name == "point-reflection-coincident-point-valid":
            valid_result = result
        records.append(
            _record(
                "reflect-exact",
                name,
                expected_final=expected_final,
                final_authority=final,
                status=str(result.get("status")),
                reason=str(result.get("failure")) if result.get("failure") else None,
            )
        )

    correct = _run_qqbar(
        reflect.extended_worker_source(),
        _qq_reflect_job(target_ordinal=0),
    )
    wrong = _run_qqbar(
        reflect.extended_worker_source(),
        _qq_reflect_job(target_ordinal=1),
    )
    records.append(
        _record(
            "reflect-exact",
            "qqbar-correct-isolator-ordinal",
            expected_final=True,
            final_authority=correct.get("status") == "EXACT_REPLAY_ACCEPTED",
            status=str(correct.get("status")),
            reason=str(correct.get("error")) if correct.get("error") else None,
        )
    )
    records.append(
        _record(
            "reflect-exact",
            "qqbar-wrong-isolator-ordinal",
            expected_final=False,
            final_authority=wrong.get("status") == "EXACT_REPLAY_ACCEPTED",
            status=str(wrong.get("status")),
            reason=str(wrong.get("error")) if wrong.get("error") else None,
        )
    )

    full_turn = {
        "variables": {"names": ["x", "y"]},
        "construction": [
            {"name": "P", "expr": "Point(x, y)"},
            {"name": "Q", "expr": "Rotate(P, 2*pi)"},
            {"name": "C", "expr": "Point(4, 7)"},
            {"name": "R", "expr": "Reflect(Q, C)"},
        ],
        "constraints": [{"def": "x", "value": 1}, {"def": "y", "value": 2}],
        "guards": [],
        "answer": "R.x",
    }
    phase_result = _reflect_call(reflect, full_turn, "7")
    phase_final = _reflect_final(phase_result)
    records.append(
        _record(
            "reflect-exact",
            "phase-sheet-full-turn-invariance",
            expected_final=phase_final,
            final_authority=phase_final,
            status=str(phase_result.get("status")),
            reason=str(phase_result.get("failure")) if phase_result.get("failure") else None,
            fail_closed_if_unsupported=True,
        )
    )

    timed = _reflect_call(reflect, _reflect_document(), "7", timeout=1e-9)
    records.append(
        _record(
            "reflect-exact",
            "timeout",
            expected_final=False,
            final_authority=_reflect_final(timed),
            status=str(timed.get("status")),
            reason=str(timed.get("failure")) if timed.get("failure") else None,
        )
    )
    partial = deepcopy(valid_result or {})
    partial.pop("root_ordinal_attestation_complete", None)
    records.append(
        _record(
            "reflect-exact",
            "partial-artifact",
            expected_final=False,
            final_authority=_reflect_final(partial),
            status="TRUNCATED_READY_OBJECT",
            reason="root ordinal attestation removed",
        )
    )

    original_hash = reflect.EXPECTED_ORIGINAL_QQBAR_SHA256
    try:
        reflect.EXPECTED_ORIGINAL_QQBAR_SHA256 = "0" * 64
        try:
            reflect.verify_dependencies()
            hash_rejected = False
            hash_reason = "hash mismatch accepted"
        except Exception as error:
            hash_rejected = True
            hash_reason = f"{type(error).__name__}:{error}"
    finally:
        reflect.EXPECTED_ORIGINAL_QQBAR_SHA256 = original_hash
    records.append(
        _record(
            "reflect-exact",
            "dependency-hash-mismatch",
            expected_final=False,
            final_authority=not hash_rejected,
            status="HASH_REJECTED" if hash_rejected else "HASH_ACCEPTED",
            reason=hash_reason,
        )
    )
    return records


def run() -> dict[str, Any]:
    started = time.monotonic()
    snapshots = _verify_snapshots()
    r1 = _load("authority_adversary_r1_candidate", R1_ROOT / "candidate.py")
    hermite = _load("authority_adversary_hermite_candidate", HERMITE_ROOT / "candidate.py")
    verifier = _load("authority_adversary_hermite_verifier", HERMITE_ROOT / "verifier.py")
    reflect = _load("authority_adversary_reflect_candidate", REFLECT_ROOT / "private_candidate.py")
    records = [
        *_r1_cases(r1),
        *_hermite_cases(hermite, verifier),
        *_reflect_cases(reflect),
    ]
    false_authorities = [record for record in records if record["false_authority"]]
    missed_positives = [record for record in records if record["missed_required_positive"]]
    false_certificates = [
        record for record in records if record.get("candidate_false_certificate") is True
    ]
    out_of_subset_uncaught_exceptions = [
        record
        for record in records
        if record.get("out_of_subset_uncaught_exception") is True
    ]
    lane_counts = {
        lane: sum(record["lane"] == lane for record in records)
        for lane in sorted({record["lane"] for record in records})
    }
    return {
        "schema": "geotarget.authority-adversary-generated/v1",
        "truth_scorer_formal_or_real_used": False,
        "cpu": 15,
        "snapshot_commits": SNAPSHOT_COMMITS,
        "snapshot_sha256": snapshots,
        "hermite_snapshot_uncommitted_at_test_time": False,
        "records": records,
        "aggregate": {
            "case_count": len(records),
            "lane_case_count": lane_counts,
            "false_authority_count": len(false_authorities),
            "candidate_false_certificate_count": len(false_certificates),
            "out_of_subset_uncaught_exception_count": len(
                out_of_subset_uncaught_exceptions
            ),
            "missed_required_positive_count": len(missed_positives),
            "exact_untouched_replay_required_for_final_authority": True,
            "elapsed_seconds": time.monotonic() - started,
            "decision": (
                "STOP_AND_NOTIFY_FALSE_AUTHORITY"
                if false_authorities or false_certificates
                else "NO_FALSE_AUTHORITY_IN_FIXED_GENERATED_SUITE"
            ),
        },
    }


def main() -> int:
    result = run()
    print(json.dumps(result, indent=2, sort_keys=True))
    aggregate = result["aggregate"]
    return int(
        aggregate["false_authority_count"] != 0
        or aggregate["candidate_false_certificate_count"] != 0
        or aggregate["missed_required_positive_count"] != 0
    )


if __name__ == "__main__":
    raise SystemExit(main())
