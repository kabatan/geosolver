#!/usr/bin/env python3
"""One isolated anonymous source row for relation-domain CSP census."""

from __future__ import annotations

import argparse
import ast
from collections import Counter
import hashlib
import json
from pathlib import Path
import stat
from typing import Any, Mapping

import candidate


SCHEMA = "geotarget.relation-domain-csp-anonymous-row/v1"
SOURCE_ROOT = Path(
    "/home/kabatan/work/solver-experiment-results/partial-ideal-root-readiness-v1/"
    "degree1-inputs"
).resolve()
OUTPUT_ROOT = Path(
    "/home/kabatan/work/solver-experiment-results/"
    "relation-domain-csp-degree1-census-v1"
).resolve()
FORBIDDEN_KEYS = frozenset(
    {
        "id",
        "problem_id",
        "case_id",
        "family",
        "group",
        "truth",
        "expected",
        "expected_target",
        "outcome",
        "result",
        "score",
        "known_count",
    }
)


class RowRejected(ValueError):
    pass


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _path(path: Path, *, source: bool) -> Path:
    if path.is_symlink():
        raise RowRejected("SYMLINK_REJECTED")
    resolved = path.resolve(strict=True) if source else path.resolve()
    root = SOURCE_ROOT if source else OUTPUT_ROOT / "rows"
    if resolved.parent != root or resolved.suffix != ".json":
        raise RowRejected("CUSTODY_PATH_REJECTED")
    if source and (
        not resolved.is_file()
        or not stat.S_ISREG(resolved.lstat().st_mode)
        or len(resolved.stem) != 4
        or not resolved.stem.isdigit()
    ):
        raise RowRejected("SOURCE_FILE_REJECTED")
    if not source and resolved.exists():
        raise RowRejected("OUTPUT_EXISTS")
    return resolved


def _call_kinds(expressions: list[str]) -> Counter[str]:
    result: Counter[str] = Counter()
    for expression in expressions:
        try:
            root = ast.parse(expression, mode="eval")
        except (SyntaxError, ValueError):
            result["SYNTAX_REJECTED"] += 1
            continue
        for node in ast.walk(root):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                result[node.func.id] += 1
    return result


def _structural_signature(document: Mapping[str, Any], result: Mapping[str, Any]) -> str:
    variables = document.get("variables", {}).get("names", [])
    variable_names = set(variables) if isinstance(variables, list) else set()
    construction = document.get("construction") or ()
    constraints = document.get("constraints") or ()
    guards = document.get("guards") or ()
    construction_expressions = [
        str(item.get("expr", "")) for item in construction if isinstance(item, Mapping)
    ]
    constraint_expressions = [
        str(item.get("def", "")) for item in constraints if isinstance(item, Mapping)
    ]
    dependency_widths = []
    for expression in constraint_expressions:
        try:
            names = {node.id for node in ast.walk(ast.parse(expression, mode="eval")) if isinstance(node, ast.Name)}
        except (SyntaxError, ValueError):
            names = set()
        dependency_widths.append(len(names & variable_names))
    payload = {
        "source_variable_count": len(variable_names),
        "finite_domain_variable_count": result.get("finite_domain_variable_count"),
        "relation_count": result.get("relation_count"),
        "construction_call_multiset": sorted(_call_kinds(construction_expressions).items()),
        "constraint_call_multiset": sorted(_call_kinds(constraint_expressions).items()),
        "constraint_dependency_widths": sorted(dependency_widths),
        "guard_call_multiset": sorted(_call_kinds([str(item) for item in guards]).items()),
    }
    return _sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode())


def _reason_category(value: object) -> str:
    text = str(value).split(":", 1)[0]
    return text if text.replace("_", "").isalnum() and len(text) <= 80 else "OTHER_FAIL_CLOSED"


def run(source: Path, source_sha256: str) -> dict[str, Any]:
    source = _path(source, source=True)
    payload = source.read_bytes()
    if _sha256(payload) != source_sha256:
        raise RowRejected("SOURCE_SHA256_MISMATCH")
    document = json.loads(payload)
    if not isinstance(document, Mapping) or FORBIDDEN_KEYS & set(document):
        raise RowRejected("ANONYMITY_OR_TRUTH_BOUNDARY_REJECTED")
    proposal = candidate.build_proposals(document)
    ready = proposal.get("status") == "PROPOSAL_READY_HOLD"
    replay = candidate.audit_untouched_full_replay(document, proposal) if ready else None
    proposal_count = int(proposal.get("proposal_count", 0)) if ready else 0
    replay_pass = (
        int(replay.get("full_source_raw_target_replay_pass_count", 0))
        if isinstance(replay, Mapping)
        else 0
    )
    authority_violation = bool(
        proposal.get("authority_pass") is not False
        or proposal.get("target_release") is not False
        or (
            isinstance(replay, Mapping)
            and (
                replay.get("authority_pass") is not False
                or replay.get("target_release") is not False
            )
        )
    )
    return {
        "schema_version": SCHEMA,
        "status": "PROPOSAL_READY_HOLD" if ready else "NOT_APPLICABLE_BASELINE_FALLBACK",
        "reason_category": "READY" if ready else _reason_category(proposal.get("reason")),
        "proposal_count": proposal_count,
        "full_replay_pass_count": replay_pass,
        "full_replay_all": bool(ready and proposal_count > 0 and replay_pass == proposal_count),
        "structural_signature_sha256": _structural_signature(document, proposal),
        "selection_read_raw_target": proposal.get("selection_read_raw_target") is not False,
        "selection_used_case_id_family_truth_or_outcome": proposal.get(
            "selection_used_case_id_family_truth_or_outcome"
        ) is not False,
        "authority_or_release_violation": authority_violation,
        "truth_score_outcome_read": False,
        "formal_authority_invoked": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--source-sha256", required=True)
    parser.add_argument("--output", type=Path, required=True)
    arguments = parser.parse_args()
    output = _path(arguments.output, source=False)
    result = run(arguments.source, arguments.source_sha256)
    output.write_text(json.dumps(result, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
