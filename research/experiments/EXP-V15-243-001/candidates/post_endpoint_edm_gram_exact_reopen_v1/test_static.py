from __future__ import annotations

import ast
from pathlib import Path


HERE = Path(__file__).resolve().parent


def test_sources_parse() -> None:
    for name in (
        "candidate.py",
        "run_generated_d0.py",
        "run_real_gate.py",
        "execution_guard.py",
        "exact_worker_guard.py",
        "run_execution_mutation_d0.py",
    ):
        ast.parse((HERE / name).read_text(encoding="utf-8"), filename=name)


def test_no_source_parser_or_routing() -> None:
    text = (HERE / "candidate.py").read_text(encoding="utf-8")
    for token in ("ast.parse", "case_id", "problem_id", "known_target_count", "offline_truth"):
        assert token not in text


def test_both_reflections_are_explicit() -> None:
    text = (HERE / "candidate.py").read_text(encoding="utf-8")
    assert "point.reflected()" in text
    assert '"both_reflections_enumerated": True' in text


def test_exact_gate_is_digest_distinct_outcome_blind_abba() -> None:
    text = (HERE / "run_real_gate.py").read_text(encoding="utf-8")
    for token in (
        "APPROVED_PYTHON_SHA256",
        "PANEL_PROVENANCE_SHA256",
        "candidate_endpoint_digest_equals_baseline",
        '("candidate", candidate_attempts[0])',
        '("baseline", endpoint)',
        '("candidate", candidate_attempts[1])',
        '"source_or_problem_modified"',
        '"source_raw_answer_exact"',
        '"target_link_exact"',
        '"all_precision_lanes_guard_and_hard_feasible"',
    ):
        assert token in text
    assert text.count('_run_exact(\n                        arguments.python.resolve()') == 1


def test_exact_gate_has_candidate_private_fail_closed_boundary() -> None:
    runner = (HERE / "run_real_gate.py").read_text(encoding="utf-8")
    boundary = (HERE / "execution_guard.py").read_text(encoding="utf-8")
    child = (HERE / "exact_worker_guard.py").read_text(encoding="utf-8")
    for token in (
        "FormalRunLease(",
        "runtime_closure_sha256",
        "ordinary_proposal_bytes",
        "_strict_descriptor_ready",
        "atomic_write_0600",
        "run_contained",
    ):
        assert token in runner
    for token in (
        "fcntl.LOCK_EX | fcntl.LOCK_NB",
        "hmac.new",
        "start_new_session=True",
        "os.killpg",
        "RSS_CAP_TERMINATED",
        "OUTPUT_CAP_POSTEXIT_REJECTED",
        "artifact escaped its frozen output root",
    ):
        assert token in boundary
    for token in (
        "verify_inherited_handoff",
        "verify_runtime_closure",
        "verify_attempt_byte_bindings",
        "resource.RLIMIT_AS",
        "resource.RLIMIT_DATA",
        "resource.RLIMIT_FSIZE",
        "os.execve",
    ):
        assert token in child
    assert "subprocess.run(" not in runner


def test_descriptor_schema_is_strict_and_recomputed() -> None:
    text = (HERE / "run_real_gate.py").read_text(encoding="utf-8")
    for token in (
        "polynomial.is_irreducible is not True",
        "sp.gcd(polynomial, polynomial.diff()).degree() != 0",
        "polynomial.count_roots(left_q, right_q) != 1",
        "int(roots_left) != ordinal",
        'set(isolator) != {"left", "right", "multiplicity", "real_root_index"}',
    ):
        assert token in text
