#!/usr/bin/env python3
"""Aggregate-only degree-one real-radical SOS certificate census."""

from __future__ import annotations

import argparse
import contextlib
import hashlib
import importlib.util
import itertools
import json
import math
import os
from pathlib import Path
import signal
import sys
from typing import Mapping

import sympy as sp
from sympy.solvers.simplex import linprog

import candidate as local_candidate


REQUESTS_SHA256 = "ee424315256582652ea0df72a05c21903a5fd4366867c6788129a79e4f80fd35"
SOURCE_ROOT = Path(
    "/home/kabatan/work/solver-experiment-results/partial-ideal-root-readiness-v1/"
    "degree1-inputs"
).resolve()
REQUEST_KEYS = frozenset({"source_path", "endpoint", "candidate_relation_high_to_low"})
FORBIDDEN_KEYS = frozenset({
    "id", "family", "truth", "answer", "target", "outcome", "result",
    "score", "known_count", "witness", "reason",
})
DOCUMENT_IDENTITY_KEYS = frozenset({
    "id", "problem_id", "case_id", "family", "group", "truth", "expected",
    "expected_target", "outcome", "result", "score", "known_count",
})
RECORD_SECONDS = 3.0
SOS_DEGREE = 3
RADICAL_EXPONENTS = (1, 2)

TARGET_ROOT = Path(
    "/home/kabatan/work/solver-wt/target-constrained-nra-witness/"
    "research/experiments/EXP-V15-243-001/candidates/"
    "target_constrained_exact_nra_witness_v1"
)
GUIDED_ROOT = Path(
    "/home/kabatan/work/solver-wt/guided-target-ideal-membership-v1/"
    "research/experiments/EXP-V15-243-001/candidates/"
    "guided_target_ideal_membership_v1"
)
PINNED = {
    TARGET_ROOT / "candidate.py": "7b98bdfb018d566994291ad75cb2e7f28f62adc960a784ca54d3b68b796586ff",
    TARGET_ROOT / "applicability.py": "8b3ae91409f56f9ba08597bd022fba0497c1e63341fcc5a04bd0e44c46c95b26",
    GUIDED_ROOT / "ideal_membership.py": "74915d163e471df9e745735a8f5e3f7a128950d72c94d581c6435ffd081b60b4",
    GUIDED_ROOT / "typed_join.py": "a2ecdd7c406642464f550e3ce91d2cc24ed0f8c67ad7f513a62c6350ee930e26",
}


class CensusRejected(RuntimeError):
    pass


def _load(name, path):
    if hashlib.sha256(path.read_bytes()).hexdigest() != PINNED[path]:
        raise RuntimeError("pinned dependency changed")
    specification = importlib.util.spec_from_file_location(name, path)
    if specification is None or specification.loader is None:
        raise ImportError(path)
    module = importlib.util.module_from_spec(specification)
    sys.modules[name] = module
    specification.loader.exec_module(module)
    return module


def _external_modules():
    local_module = sys.modules.get("candidate")
    prior_ideal = sys.modules.get("ideal_membership")
    try:
        target_backend = _load("candidate", TARGET_ROOT / "candidate.py")
        applicability = _load(
            "real_radical_sos_pinned_applicability", TARGET_ROOT / "applicability.py"
        )
        ideal = _load("ideal_membership", GUIDED_ROOT / "ideal_membership.py")
        typed = _load("real_radical_sos_pinned_typed_join", GUIDED_ROOT / "typed_join.py")
    finally:
        if local_module is None:
            sys.modules.pop("candidate", None)
        else:
            sys.modules["candidate"] = local_module
        if prior_ideal is None:
            sys.modules.pop("ideal_membership", None)
        else:
            sys.modules["ideal_membership"] = prior_ideal
    return target_backend, applicability, ideal, typed


TARGET_BACKEND, APPLICABILITY, IDEAL, TYPED = _external_modules()


@contextlib.contextmanager
def _record_deadline():
    previous = signal.getsignal(signal.SIGALRM)

    def timeout(_signum, _frame):
        raise TimeoutError("fixed record certificate deadline")

    signal.signal(signal.SIGALRM, timeout)
    signal.setitimer(signal.ITIMER_REAL, RECORD_SECONDS)
    try:
        yield
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, previous)


def _zero(expression):
    value = sp.factor(sp.cancel(sp.together(expression)))
    return value == 0 or value.is_zero is True or value.equals(0) is True


def _proposal_root(coefficients):
    if (
        not isinstance(coefficients, list)
        or len(coefficients) != 2
        or any(type(value) is not int for value in coefficients)
    ):
        raise CensusRejected("degree-one projection rejected")
    leading, constant = coefficients
    if leading <= 0 or math.gcd(abs(leading), abs(constant)) != 1:
        raise CensusRejected("degree-one projection rejected")
    return sp.Rational(-constant, leading)


def _endpoint(values):
    if not isinstance(values, list) or not values:
        raise CensusRejected("endpoint rejected")
    result = [float(value) for value in values]
    if not all(math.isfinite(value) for value in result):
        raise CensusRejected("endpoint rejected")
    return result


def _source_path(value):
    path = Path(str(value)).resolve(strict=True)
    if path.parent != SOURCE_ROOT or not path.is_file():
        raise CensusRejected("source custody root rejected")
    if path.suffix != ".json" or len(path.stem) != 4 or not path.stem.isdigit():
        raise CensusRejected("source custody name rejected")
    return path


def _primitive_compile(document):
    if not isinstance(document, Mapping) or document.get("post_process") not in (None, ""):
        raise CensusRejected("raw target source rejected")
    if DOCUMENT_IDENTITY_KEYS & set(document):
        raise CensusRejected("source identity boundary rejected")
    source, _metadata = APPLICABILITY._legacy_target_link_source(
        document, include_private_bridge_ledger=True
    )
    return source


def _polynomialize(source):
    state = APPLICABILITY._source_state_from_source(source)
    symbols = tuple(state["relevant"])
    equations = tuple(
        sp.Poly(value, *symbols, domain=sp.QQ).as_expr()
        for value in state["equations"]
        if not _zero(value)
    )
    if not equations:
        raise CensusRejected("empty equality ideal")
    by_name = {symbol.name: symbol for symbol in state["symbols"]}
    substitutions = {
        symbol: by_name[symbol.name]
        for symbol in sp.sympify(source.raw_target).free_symbols
        if symbol.name in by_name
    }
    target = sp.sympify(source.raw_target).xreplace(substitutions)
    numerator, denominator = TARGET_BACKEND._rational_parts(target)
    if denominator != 1:
        raise CensusRejected("raw target denominator rejected")
    target = TARGET_BACKEND._poly(numerator, symbols).as_expr()
    return symbols, equations, target


def _unit_ideal(basis):
    return _zero(basis.reduce(sp.Integer(1))[1])


def _psd_exact(matrix):
    if matrix != matrix.T or any(value.is_Rational is not True for value in matrix):
        return False
    indices = range(matrix.rows)
    return all(
        matrix.extract(subset, subset).det() >= 0
        for size in range(1, matrix.rows + 1)
        for subset in itertools.combinations(indices, size)
    )


def _coefficient_system(basis, symbols, monomials, powered):
    target_remainder = sp.Poly(basis.reduce(powered)[1], *symbols, domain=sp.QQ)
    pairs = []
    remainders = []
    for i in range(len(monomials)):
        for j in range(i, len(monomials)):
            multiplier = 1 if i == j else 2
            remainder = sp.Poly(
                basis.reduce(sp.expand(multiplier * monomials[i] * monomials[j]))[1],
                *symbols,
                domain=sp.QQ,
            )
            if i == j or not remainder.is_zero:
                pairs.append((i, j))
                remainders.append(remainder)
    exponents = sorted(
        set(target_remainder.as_dict()).union(
            *(set(value.as_dict()) for value in remainders)
        )
    )
    rows = [
        [value.as_dict().get(exponent, sp.Integer(0)) for value in remainders]
        for exponent in exponents
    ]
    right = [-target_remainder.as_dict().get(exponent, sp.Integer(0)) for exponent in exponents]
    return pairs, sp.Matrix(rows), sp.Matrix(right)


def _matrix_from_solution(size, pairs, solution):
    matrix = sp.zeros(size)
    for (i, j), value in zip(pairs, solution, strict=True):
        matrix[i, j] = matrix[j, i] = sp.cancel(value)
    return matrix


def _compact_gram(monomials, matrix):
    active = tuple(
        index
        for index in range(matrix.rows)
        if any(matrix[index, other] != 0 for other in range(matrix.cols))
    )
    if not active:
        return (sp.Integer(1),), sp.zeros(1)
    return (
        tuple(monomials[index] for index in active),
        matrix.extract(active, active),
    )


def _gram_candidates(monomials, pairs, equalities, right):
    unknowns = sp.symbols(f"__gram_0:{len(pairs)}")
    solution_set = sp.linsolve((equalities, right), unknowns)
    if solution_set is not sp.EmptySet:
        try:
            affine = next(iter(solution_set))
        except StopIteration:
            affine = None
        if affine is not None:
            free = set().union(*(value.free_symbols for value in affine)) & set(unknowns)
            solution = tuple(sp.cancel(value.subs({symbol: 0 for symbol in free})) for value in affine)
            matrix = _matrix_from_solution(len(monomials), pairs, solution)
            compact_monomials, compact = _compact_gram(monomials, matrix)
            if _psd_exact(compact):
                yield compact_monomials, compact

    off_diagonal = [index for index, (i, j) in enumerate(pairs) if i != j]
    variable_count = len(pairs) + len(off_diagonal)
    objective = [sp.Integer(0)] * variable_count
    for index, (i, j) in enumerate(pairs):
        if i == j:
            objective[index] = sp.Integer(1)
    inequalities = []
    bounds = []
    absolute_index = {}
    for index, (i, j) in enumerate(pairs):
        bounds.append((0, None) if i == j else (None, None))
    for offset, pair_index in enumerate(off_diagonal):
        t_index = len(pairs) + offset
        absolute_index[pair_index] = t_index
        bounds.append((0, None))
        first = [sp.Integer(0)] * variable_count
        first[pair_index], first[t_index] = 1, -1
        inequalities.append(first)
        second = [sp.Integer(0)] * variable_count
        second[pair_index], second[t_index] = -1, -1
        inequalities.append(second)
    for row in range(len(monomials)):
        inequality = [sp.Integer(0)] * variable_count
        diagonal = None
        for index, (i, j) in enumerate(pairs):
            if i == j == row:
                diagonal = index
            elif row in (i, j) and index in absolute_index:
                inequality[absolute_index[index]] += 1
        if diagonal is None:
            raise CensusRejected("Gram diagonal missing")
        inequality[diagonal] -= 1
        inequalities.append(inequality)
    extended_equalities = equalities.row_join(sp.zeros(equalities.rows, len(off_diagonal)))
    try:
        _objective, solution = linprog(
            objective,
            inequalities,
            [sp.Integer(0)] * len(inequalities),
            extended_equalities,
            right,
            bounds=bounds,
        )
    except Exception:
        return
    matrix = _matrix_from_solution(len(monomials), pairs, solution[: len(pairs)])
    compact_monomials, compact = _compact_gram(monomials, matrix)
    if _psd_exact(compact):
        yield compact_monomials, compact


def _search(symbols, equations, target, q, basis):
    monomials = tuple(sorted(
        sp.polys.monomials.itermonomials(symbols, SOS_DEGREE),
        key=lambda value: (sp.Poly(value, *symbols).total_degree(), sp.default_sort_key(value)),
    ))
    for m in RADICAL_EXPONENTS:
        powered = sp.expand((target - q) ** (2 * m))
        pairs, equalities, right = _coefficient_system(
            basis, symbols, monomials, powered
        )
        for certificate_monomials, gram in _gram_candidates(
            monomials, pairs, equalities, right
        ):
            vector = sp.Matrix(certificate_monomials)
            sos = sp.expand((vector.T * gram * vector)[0])
            cofactors = IDEAL._cofactor_witness(
                equations, sp.expand(powered + sos), symbols
            )
            if cofactors is None:
                continue
            result = local_candidate.solve(
                local_candidate.Source(
                    tuple(symbols), tuple(equations), target, q, True, False, False
                ),
                local_candidate.Certificate(
                    tuple(equations), tuple(cofactors), m, certificate_monomials,
                    sp.ImmutableMatrix(gram),
                ),
            )
            if result.identity_ready and not result.authority_emitted:
                return m, gram
    return None


def _summarize(requests):
    counts = {
        "input": 0,
        "degree_one_projection": 0,
        "primitive_cover": 0,
        "safe_qq_equalities_and_target": 0,
        "consistent_nonunit_ideal": 0,
        "direct_h_miss": 0,
        "direct_h2_miss": 0,
        "sos_search_attempted": 0,
        "identity_ready": 0,
        "identity_ready_m1": 0,
        "identity_ready_m2": 0,
        "typed_root_exact_replay_available_on_identity": 0,
        "identity_external_join_available": 0,
        "unexpected_authority_or_release": 0,
    }
    joined_signatures = set()
    for request in requests:
        counts["input"] += 1
        try:
            if not isinstance(request, Mapping) or set(request) != REQUEST_KEYS:
                raise CensusRejected("request shape rejected")
            if FORBIDDEN_KEYS & set(request):
                raise CensusRejected("identity boundary rejected")
            q = _proposal_root(request["candidate_relation_high_to_low"])
            endpoint = _endpoint(request["endpoint"])
            counts["degree_one_projection"] += 1
            source_path = _source_path(request["source_path"])
            document = json.loads(source_path.read_bytes())
            with _record_deadline():
                source = _primitive_compile(document)
                counts["primitive_cover"] += 1
                symbols, equations, target = _polynomialize(source)
                counts["safe_qq_equalities_and_target"] += 1
                basis = sp.groebner(equations, *symbols, order="grevlex", domain=sp.QQ)
                if _unit_ideal(basis):
                    raise CensusRejected("unit ideal")
                counts["consistent_nonunit_ideal"] += 1
                h = sp.expand(target - q)
                if _zero(basis.reduce(h)[1]):
                    continue
                counts["direct_h_miss"] += 1
                if _zero(basis.reduce(sp.expand(h**2))[1]):
                    continue
                counts["direct_h2_miss"] += 1
                counts["sos_search_attempted"] += 1
                found = _search(symbols, equations, target, q, basis)
                if found is None:
                    continue
                m, gram = found
                counts["identity_ready"] += 1
                counts[f"identity_ready_m{m}"] += 1
                signature = (
                    len(symbols), len(equations),
                    max(sp.Poly(value, *symbols).total_degree() for value in equations),
                    m, gram.rank(),
                )
                try:
                    TYPED.prepare_typed_regular_job(source_path, endpoint)
                except Exception:
                    continue
                counts["typed_root_exact_replay_available_on_identity"] += 1
                counts["identity_external_join_available"] += 1
                joined_signatures.add(signature)
        except Exception:
            continue
    join = counts["identity_external_join_available"]
    gate = join >= 4 and len(joined_signatures) >= 2
    return {
        "schema_version": "geotarget.real-radical-sos-static-certificate-census/v1",
        "counts": counts,
        "anonymous_identity_typed_static_signature_count": len(joined_signatures),
        "gate": "REAL_GATE_PASS" if gate else "REAL_GATE_STOP",
        "authority": False,
        "target_release": False,
        "individual_records_emitted": False,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--requests", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--expected-cpu", type=int, default=14)
    arguments = parser.parse_args()
    if os.sched_getaffinity(0) != {arguments.expected_cpu}:
        raise SystemExit("census must be pinned to the expected CPU")
    payload = arguments.requests.read_bytes()
    if hashlib.sha256(payload).hexdigest() != REQUESTS_SHA256:
        raise SystemExit("degree-one panel SHA-256 mismatch")
    requests = json.loads(payload)
    if not isinstance(requests, list) or len(requests) != 85:
        raise SystemExit("degree-one panel custody mismatch")
    result = _summarize(requests)
    arguments.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
