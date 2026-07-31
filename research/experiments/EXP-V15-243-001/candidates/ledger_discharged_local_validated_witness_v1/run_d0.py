from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
from typing import Any

from candidate import canonical_sha256, normalize_and_discharge, prove_proposal


HERE = Path(__file__).resolve().parent


def legacy(kind: str, source: str) -> dict[str, str]:
    return {"kind": kind, "source": source, "detail": "generated typed seam"}


def guard(item: dict[str, str], expression: str, relation: str) -> dict[str, Any]:
    return {
        "kind": "canonical-guard",
        "covers_legacy_sha256": [canonical_sha256(item)],
        "expression": expression,
        "relation": relation,
    }


def make_artifacts(
    *,
    variables: list[str],
    equations: list[str],
    target: str,
    box: list[list[str]],
    target_interval: list[str],
    legacy_items: list[dict[str, str]],
    typed_items: list[dict[str, Any]],
    tag: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    statement = {
        "variables": variables,
        "source_equations": equations,
        "target_expression": target,
    }
    source_sha = hashlib.sha256(("generated-source:" + tag).encode()).hexdigest()
    body: dict[str, Any] = {
        "source_sha256": source_sha,
        "system_sha256": canonical_sha256(statement),
        "system": {
            **statement,
            "replay_obligations": legacy_items,
            "typed_replay_obligations": typed_items,
        },
    }
    body["job_sha256"] = canonical_sha256(body)
    certificate: dict[str, Any] = {
        "schema_version": "generated.krawczyk/v1",
        "status": "VERIFIED",
        "source_sha256": source_sha,
        "system_sha256": body["system_sha256"],
        "job_sha256": body["job_sha256"],
        "regular_unique_root_verified": True,
        "all_compiled_equations_verified": True,
        "all_compiled_predicates_verified": True,
        "target_interval_exactly_derived_from_source_box": True,
        "certified_box": box,
        "certified_target_interval": target_interval,
        "truth_used": False,
        "coverage": "UNKNOWN",
    }
    certificate["artifact_sha256"] = canonical_sha256(certificate)
    return body, certificate


def periodic_typed(items: list[dict[str, str]], *, sheet: int = 0, guards=None) -> dict[str, Any]:
    return {
        "kind": "periodic-sheet-reconstruction",
        "covers_legacy_sha256": [canonical_sha256(item) for item in items],
        "cosine_variable": "c",
        "sine_variable": "s",
        "principal_turn": "1/4",
        "frequency": "1",
        "offset": "0",
        "selected_sheet": sheet,
        "parameter_bound": {
            "lower": "0",
            "upper": "1/2",
            "lower_closed": True,
            "upper_closed": True,
        },
        "parameter_guards": guards or [{"relation": "gt", "rhs": "0"}],
    }


def run() -> dict[str, Any]:
    checks: list[dict[str, Any]] = []

    strict_legacy = [legacy("canonical-guard", "x > 0")]
    strict_job, strict_cert = make_artifacts(
        variables=["x"],
        equations=["(x-1)*(x**2-2)"],
        target="x",
        box=[["7/5", "3/2"]],
        target_interval=["7/5", "3/2"],
        legacy_items=strict_legacy,
        typed_items=[guard(strict_legacy[0], "x", "gt")],
        tag="strict",
    )
    strict = prove_proposal(
        job=strict_job,
        certificate=strict_cert,
        coefficients_high_to_low=[1, 0, -2],
        descriptor_selection_interval=["1", "2"],
    )
    checks.append(
        {
            "name": "strict_guard_and_localized_factor",
            "passed": strict.get("status") == "VERIFIED"
            and strict.get("source_certificate_join_verified") is True
            and strict.get("canonical_source_replay_required") is True
            and strict.get("authority") is False,
            "status": strict.get("status"),
            "reason": strict.get("reason"),
        }
    )

    boundary_job = copy.deepcopy(strict_job)
    boundary_job["system"]["typed_replay_obligations"] = [
        guard(strict_legacy[0], "x**2-2", "gt")
    ]
    boundary_job["job_sha256"] = canonical_sha256(
        {k: v for k, v in boundary_job.items() if k != "job_sha256"}
    )
    boundary_cert = copy.deepcopy(strict_cert)
    boundary_cert["job_sha256"] = boundary_job["job_sha256"]
    boundary_cert["artifact_sha256"] = canonical_sha256(
        {k: v for k, v in boundary_cert.items() if k != "artifact_sha256"}
    )
    boundary = normalize_and_discharge(boundary_job, boundary_cert)
    checks.append(
        {
            "name": "strict_guard_boundary_crossing",
            "passed": boundary.get("status") == "NOT_CERTIFIED",
            "status": boundary.get("status"),
            "reason": boundary.get("reason"),
        }
    )

    wrong_poly = prove_proposal(
        job=strict_job,
        certificate=strict_cert,
        coefficients_high_to_low=[1, 0, -3],
        descriptor_selection_interval=["1", "2"],
    )
    checks.append(
        {
            "name": "false_target_polynomial",
            "passed": wrong_poly.get("status") == "NOT_PROVED"
            and wrong_poly.get("target_release") is False,
            "status": wrong_poly.get("status"),
            "reason": wrong_poly.get("reason"),
        }
    )

    periodic_legacy = [
        legacy("canonical-guard", "0 < t < 1/2"),
        legacy("periodic-parameter-guard", "t sheet in source bound"),
        legacy("trig-parameter-reconstruction", "c=cos(2*pi*t),s=sin(2*pi*t)"),
    ]
    periodic_job, periodic_cert = make_artifacts(
        variables=["c", "s"],
        equations=["c", "s-1"],
        target="s",
        box=[["-1/100", "1/100"], ["99/100", "101/100"]],
        target_interval=["99/100", "101/100"],
        legacy_items=periodic_legacy,
        typed_items=[periodic_typed(periodic_legacy)],
        tag="periodic",
    )
    periodic = prove_proposal(
        job=periodic_job,
        certificate=periodic_cert,
        coefficients_high_to_low=[1, -1],
        descriptor_selection_interval=["0", "2"],
    )
    checks.append(
        {
            "name": "periodic_exact_sheet_reconstruction",
            "passed": periodic.get("status") == "VERIFIED"
            and periodic.get("canonical_source_replay_required") is True,
            "status": periodic.get("status"),
            "reason": periodic.get("reason"),
        }
    )

    for name, typed in (
        ("wrong_periodic_sheet", periodic_typed(periodic_legacy, sheet=1)),
        (
            "periodic_guard_boundary",
            periodic_typed(periodic_legacy, guards=[{"relation": "gt", "rhs": "1/4"}]),
        ),
    ):
        job = copy.deepcopy(periodic_job)
        job["system"]["typed_replay_obligations"] = [typed]
        job["job_sha256"] = canonical_sha256({k: v for k, v in job.items() if k != "job_sha256"})
        cert = copy.deepcopy(periodic_cert)
        cert["job_sha256"] = job["job_sha256"]
        cert["artifact_sha256"] = canonical_sha256(
            {k: v for k, v in cert.items() if k != "artifact_sha256"}
        )
        result = normalize_and_discharge(job, cert)
        checks.append(
            {
                "name": name,
                "passed": result.get("status") == "NOT_CERTIFIED",
                "status": result.get("status"),
                "reason": result.get("reason"),
            }
        )

    selector_legacy = [legacy("intersection-selector", "first circle/line intersection")]

    def selector_job(y_value: int, separation: str, branch_relation: str = "gt"):
        typed = {
            "kind": "intersection-selector",
            "covers_legacy_sha256": [canonical_sha256(selector_legacy[0])],
            "branch_expression": "y",
            "branch_relation": branch_relation,
            "separation_expression": separation,
        }
        return make_artifacts(
            variables=["x", "y"],
            equations=["x", f"y-({y_value})"],
            target="y",
            box=[["-1/100", "1/100"], [str(y_value), str(y_value)]],
            target_interval=[f"{100 * y_value - 1}/100", f"{100 * y_value + 1}/100"],
            legacy_items=selector_legacy,
            typed_items=[typed],
            tag=f"selector-{y_value}-{separation}-{branch_relation}",
        )

    selected_job, selected_cert = selector_job(1, "2*y")
    selected = prove_proposal(
        job=selected_job,
        certificate=selected_cert,
        coefficients_high_to_low=[1, -1],
        descriptor_selection_interval=["0", "2"],
    )
    checks.append(
        {
            "name": "intersection_selector",
            "passed": selected.get("status") == "VERIFIED",
            "status": selected.get("status"),
            "reason": selected.get("reason"),
        }
    )
    wrong_job, wrong_cert = selector_job(-1, "2*y")
    wrong = normalize_and_discharge(wrong_job, wrong_cert)
    checks.append(
        {
            "name": "wrong_intersection_sheet",
            "passed": wrong.get("status") == "NOT_CERTIFIED",
            "status": wrong.get("status"),
            "reason": wrong.get("reason"),
        }
    )
    coincident_job, coincident_cert = selector_job(0, "2*y", "ge")
    coincident = normalize_and_discharge(coincident_job, coincident_cert)
    checks.append(
        {
            "name": "coincident_intersection_selector",
            "passed": coincident.get("status") == "NOT_CERTIFIED",
            "status": coincident.get("status"),
            "reason": coincident.get("reason"),
        }
    )

    untyped_job = copy.deepcopy(strict_job)
    untyped_job["system"]["typed_replay_obligations"] = []
    untyped_job["job_sha256"] = canonical_sha256(
        {k: v for k, v in untyped_job.items() if k != "job_sha256"}
    )
    untyped_cert = copy.deepcopy(strict_cert)
    untyped_cert["job_sha256"] = untyped_job["job_sha256"]
    untyped_cert["artifact_sha256"] = canonical_sha256(
        {k: v for k, v in untyped_cert.items() if k != "artifact_sha256"}
    )
    untyped = normalize_and_discharge(untyped_job, untyped_cert)
    checks.append(
        {
            "name": "untyped_legacy_obligation",
            "passed": untyped.get("status") == "NOT_CERTIFIED",
            "status": untyped.get("status"),
            "reason": untyped.get("reason"),
        }
    )

    tampered_cert = copy.deepcopy(strict_cert)
    tampered_cert["certified_box"] = [["1", "2"]]
    tampered = normalize_and_discharge(strict_job, tampered_cert)
    checks.append(
        {
            "name": "tampered_krawczyk_box",
            "passed": tampered.get("status") == "NOT_CERTIFIED",
            "status": tampered.get("status"),
            "reason": tampered.get("reason"),
        }
    )

    result = {
        "schema_version": "geotarget.ledger-discharged-local-validated-witness-d0/v1",
        "candidate": "LEDGER_DISCHARGED_LOCAL_VALIDATED_WITNESS_REPAIR_A",
        "case_count": len(checks),
        "pass_count": sum(item["passed"] for item in checks),
        "false_accept_count": sum(
            item["status"] == "VERIFIED" and not item["passed"] for item in checks
        ),
        "checks": checks,
        "frozen_localized_link_sha256": (
            "d1b0ddef62ce1cfc52639364184cadcd0a97a1cf82fa61c724e49f0a47a016bd"
        ),
        "canonical_replay_bypassed": False,
        "authority_emitted": False,
        "truth_used": False,
    }
    result["candidate_sha256"] = canonical_sha256(result)
    return result


if __name__ == "__main__":
    print(json.dumps(run(), indent=2))
