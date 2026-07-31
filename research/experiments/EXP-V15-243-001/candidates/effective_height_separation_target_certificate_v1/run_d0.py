from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
from typing import Any

import sympy as sp

from candidate import canonical_sha256, prove


HERE = Path(__file__).resolve().parent


def _digest(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def _isolator(coefficients: list[int], approximate: str, *, exponent: int = 300):
    variable = sp.Symbol("z")
    polynomial = sp.Poly.from_list(coefficients, variable, domain=sp.ZZ)
    target = sp.Rational(approximate) if "/" in approximate else sp.N(approximate, 100)
    if polynomial.degree() == 1:
        root = -polynomial.all_coeffs()[1] / polynomial.all_coeffs()[0]
        return [str(root), str(root)], 0
    intervals = polynomial.intervals(eps=sp.Rational(1, 10**exponent))
    chosen_index = min(
        range(len(intervals)),
        key=lambda index: abs(sp.N(sum(intervals[index][0]) / 2, 100) - target),
    )
    (left, right), multiplicity = intervals[chosen_index]
    assert multiplicity == 1
    return [str(left), str(right)], chosen_index


def _fact(variable: str, coefficients: list[int], approximate: str) -> dict[str, Any]:
    isolator, ordinal = _isolator(coefficients, approximate)
    qqbar = {
        "coefficients_high_to_low": coefficients,
        "isolating_interval": isolator,
        "real_root_ordinal": ordinal,
    }
    body: dict[str, Any] = {
        "variable": variable,
        "coefficients_high_to_low": coefficients,
        "isolating_interval": isolator,
        "real_root_ordinal": ordinal,
        "recomputed_l1_height": sum(abs(value) for value in coefficients),
        "independent_proposal_provenance": True,
        "serialized_qqbar": qqbar,
        "serialized_qqbar_sha256": canonical_sha256(qqbar),
    }
    body["fact_sha256"] = canonical_sha256(body)
    return body


def _descriptor(coefficients: list[int], approximate: str, *, broad=None) -> dict[str, Any]:
    isolator, ordinal = _isolator(coefficients, approximate, exponent=100)
    if broad is not None:
        isolator = broad
        variable = sp.Symbol("z")
        polynomial = sp.Poly.from_list(coefficients, variable, domain=sp.ZZ)
        left, right = map(sp.Rational, isolator)
        bound = sp.Rational(2 + max(abs(value) for value in coefficients))
        ordinal = int(polynomial.count_roots(-bound, left))
    return {
        "coefficients_high_to_low": coefficients,
        "isolating_interval": isolator,
        "real_root_ordinal": ordinal,
    }


def _case(
    *,
    tag: str,
    variables: list[str],
    equations: list[str],
    raw_target: str,
    facts: list[dict[str, Any]],
) -> tuple[dict[str, Any], dict[str, Any]]:
    statement = {"variables": variables, "equations": equations, "raw_target": raw_target}
    source_sha = canonical_sha256({"generated_source": statement})
    body: dict[str, Any] = {
        "source_sha256": source_sha,
        "endpoint_float64_sha256": _digest("endpoint:" + tag),
        "system_sha256": canonical_sha256(statement),
        "obligation_ledger_sha256": _digest("ledger:" + tag),
        "lineage_sha256": _digest("lineage:" + tag),
        "source_statement": statement,
        "coordinate_facts": facts,
    }
    body["job_sha256"] = canonical_sha256(body)
    certificate: dict[str, Any] = {
        "schema_version": "generated.same-root-exact-source-certificate/v1",
        "status": "VERIFIED",
        "job_sha256": body["job_sha256"],
        "source_sha256": source_sha,
        "endpoint_float64_sha256": body["endpoint_float64_sha256"],
        "system_sha256": body["system_sha256"],
        "obligation_ledger_sha256": body["obligation_ledger_sha256"],
        "lineage_sha256": body["lineage_sha256"],
        "coordinate_fact_sha256": [item["fact_sha256"] for item in facts],
        "same_endpoint_source_root_unique": True,
        "all_source_equations_exact": True,
        "all_guards_exact": True,
        "all_branches_exact": True,
        "all_coordinate_facts_same_root": True,
        "truth_used": False,
        "coverage": "UNKNOWN",
    }
    certificate["artifact_sha256"] = canonical_sha256(certificate)
    return body, certificate


def _rebind(job: dict[str, Any], certificate: dict[str, Any]) -> None:
    job["job_sha256"] = canonical_sha256({k: v for k, v in job.items() if k != "job_sha256"})
    certificate["job_sha256"] = job["job_sha256"]
    certificate["coordinate_fact_sha256"] = [
        item["fact_sha256"] for item in job["coordinate_facts"]
    ]
    certificate["artifact_sha256"] = canonical_sha256(
        {k: v for k, v in certificate.items() if k != "artifact_sha256"}
    )


def run() -> dict[str, Any]:
    checks: list[dict[str, Any]] = []

    def check(name: str, result: dict[str, Any], expected: str) -> None:
        checks.append(
            {
                "name": name,
                "expected": expected,
                "status": result.get("status"),
                "reason": result.get("reason"),
                "passed": result.get("status") == expected
                and result.get("authority") is False
                and result.get("target_release") is False
                and result.get("canonical_source_replay_required") is True,
            }
        )

    affine_job, affine_cert = _case(
        tag="affine",
        variables=["x", "y"],
        equations=["x-3", "y-2*x-1"],
        raw_target="x+y",
        facts=[_fact("x", [1, -3], "3"), _fact("y", [1, -7], "7")],
    )
    check(
        "affine_rational",
        prove(
            job=affine_job,
            source_root_certificate=affine_cert,
            descriptor=_descriptor([1, -10], "10"),
        ),
        "VERIFIED_PROPOSAL",
    )

    triangular_job, triangular_cert = _case(
        tag="triangular",
        variables=["x", "y"],
        equations=["x**2-2", "y-x**2"],
        raw_target="x+y",
        facts=[_fact("x", [1, 0, -2], "1.4142"), _fact("y", [1, -2], "2")],
    )
    check(
        "triangular_quadratic",
        prove(
            job=triangular_job,
            source_root_certificate=triangular_cert,
            descriptor=_descriptor([1, -4, 2], "3.4142"),
        ),
        "VERIFIED_PROPOSAL",
    )

    coupled_facts = [_fact("x", [1, 0, -2], "1.4142"), _fact("y", [1, 0, -2], "1.4142")]
    coupled_job, coupled_cert = _case(
        tag="coupled",
        variables=["x", "y"],
        equations=["x**2-2", "x*y-2"],
        raw_target="x+y",
        facts=coupled_facts,
    )
    check(
        "coupled_low_degree",
        prove(
            job=coupled_job,
            source_root_certificate=coupled_cert,
            descriptor=_descriptor([1, 0, -8], "2.8284"),
        ),
        "VERIFIED_PROPOSAL",
    )

    permuted_job, permuted_cert = _case(
        tag="coupled-permuted",
        variables=["y", "x"],
        equations=["x*y-2", "x**2-2"],
        raw_target="y+x",
        facts=[copy.deepcopy(coupled_facts[1]), copy.deepcopy(coupled_facts[0])],
    )
    check(
        "variable_equation_permutation",
        prove(
            job=permuted_job,
            source_root_certificate=permuted_cert,
            descriptor=_descriptor([1, 0, -8], "2.8284"),
        ),
        "VERIFIED_PROPOSAL",
    )

    scaled_job, scaled_cert = _case(
        tag="scaled-target",
        variables=["x"],
        equations=["x**2-2"],
        raw_target="2*x",
        facts=[_fact("x", [1, 0, -2], "1.4142")],
    )
    check(
        "reversible_target_scale",
        prove(
            job=scaled_job,
            source_root_certificate=scaled_cert,
            descriptor=_descriptor([1, 0, -8], "2.8284"),
        ),
        "VERIFIED_PROPOSAL",
    )

    near_job, near_cert = _case(
        tag="near-nonzero",
        variables=["x"],
        equations=["x**2-2"],
        raw_target="x+1/10**30",
        facts=[_fact("x", [1, 0, -2], "1.4142")],
    )
    check(
        "near_but_nonzero",
        prove(
            job=near_job,
            source_root_certificate=near_cert,
            descriptor=_descriptor([1, 0, -2], "1.4142", broad=["7/5", "3/2"]),
        ),
        "NOT_PROVED",
    )

    wrong_job, wrong_cert = _case(
        tag="wrong-factor",
        variables=["x"],
        equations=["x**2-2"],
        raw_target="x",
        facts=[_fact("x", [1, 0, -2], "1.4142")],
    )
    check(
        "wrong_factor",
        prove(
            job=wrong_job,
            source_root_certificate=wrong_cert,
            descriptor=_descriptor([1, 0, -3], "1.732", broad=["1", "2"]),
        ),
        "NOT_PROVED",
    )

    bad_height_job = copy.deepcopy(coupled_job)
    bad_height_cert = copy.deepcopy(coupled_cert)
    bad_fact = bad_height_job["coordinate_facts"][0]
    bad_fact["recomputed_l1_height"] = 1
    bad_fact["fact_sha256"] = canonical_sha256(
        {k: v for k, v in bad_fact.items() if k != "fact_sha256"}
    )
    _rebind(bad_height_job, bad_height_cert)
    check(
        "underestimated_coordinate_height",
        prove(
            job=bad_height_job,
            source_root_certificate=bad_height_cert,
            descriptor=_descriptor([1, 0, -8], "2.8284"),
        ),
        "NOT_PROVED",
    )

    for name, flag in (
        ("singular_source_root", "same_endpoint_source_root_unique"),
        ("branch_replay_failure", "all_branches_exact"),
    ):
        certificate = copy.deepcopy(coupled_cert)
        certificate[flag] = False
        certificate["artifact_sha256"] = canonical_sha256(
            {k: v for k, v in certificate.items() if k != "artifact_sha256"}
        )
        check(
            name,
            prove(
                job=coupled_job,
                source_root_certificate=certificate,
                descriptor=_descriptor([1, 0, -8], "2.8284"),
            ),
            "NOT_PROVED",
        )

    ordinal_job = copy.deepcopy(scaled_job)
    ordinal_cert = copy.deepcopy(scaled_cert)
    ordinal_fact = ordinal_job["coordinate_facts"][0]
    ordinal_fact["real_root_ordinal"] = 0
    ordinal_fact["fact_sha256"] = canonical_sha256(
        {k: v for k, v in ordinal_fact.items() if k != "fact_sha256"}
    )
    _rebind(ordinal_job, ordinal_cert)
    check(
        "wrong_coordinate_ordinal",
        prove(
            job=ordinal_job,
            source_root_certificate=ordinal_cert,
            descriptor=_descriptor([1, 0, -8], "2.8284"),
        ),
        "NOT_PROVED",
    )

    result = {
        "schema_version": "geotarget.effective-height-separation-d0/v1",
        "candidate": "EFFECTIVE_HEIGHT_SEPARATION_TARGET_CERTIFICATE",
        "case_count": len(checks),
        "pass_count": sum(item["passed"] for item in checks),
        "false_accept_count": sum(
            item["expected"] == "NOT_PROVED" and item["status"] == "VERIFIED_PROPOSAL"
            for item in checks
        ),
        "checks": checks,
        "authority_emitted": False,
        "truth_used": False,
    }
    result["candidate_sha256"] = canonical_sha256(result)
    return result


if __name__ == "__main__":
    print(json.dumps(run(), indent=2))
