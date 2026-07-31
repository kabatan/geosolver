"""Truth-free generated systems for the partial border-basis D0."""

from __future__ import annotations

from copy import deepcopy
import itertools

import mpmath as mp

from candidate import SCHEMA


mp.mp.dps = 90


def _z(value: mp.mpc | mp.mpf | int) -> list[str]:
    item = mp.mpc(value)
    return [mp.nstr(item.real, 85), mp.nstr(item.imag, 85)]


def _point(*items: object) -> list[list[str]]:
    return [_z(mp.mpc(item)) for item in items]


def _problem(
    *,
    variables: list[str],
    equations: list[str],
    predicates: list[dict[str, str]],
    raw_target: str,
    target: int,
    box: list[list[str]],
    cluster: list[list[list[str]]],
) -> dict[str, object]:
    counts = {kind: sum(item["kind"] == kind for item in predicates) for kind in ("guard", "definedness", "branch")}
    return {
        "schema_version": SCHEMA,
        "precision_bits": 256,
        "variables": variables,
        "equations": equations,
        "complete_equality_ledger": True,
        "source_fibre_equality_count": len(equations),
        "predicates": predicates,
        "complete_predicate_ledger": True,
        "predicate_ledger_count": len(predicates),
        "guard_predicate_count": counts["guard"],
        "definedness_predicate_count": counts["definedness"],
        "branch_predicate_count": counts["branch"],
        "raw_target": raw_target,
        "descriptor": {
            "minimal_polynomial_high_to_low": [1, -target],
            "selected_real_root_index": 0,
            "isolating_interval": {
                "left": str(target - 1) + "/1",
                "right": str(target + 1) + "/1",
            },
        },
        "proposal_box": box,
        "approximate_cluster": cluster,
        "cluster_declared_count": len(cluster),
        "cluster_padded": False,
        "truth_used": False,
    }


def quadratic_conjugates() -> dict[str, object]:
    root = mp.sqrt(2)
    return _problem(
        variables=["x"],
        equations=["x**2-2"],
        predicates=[{"expression": "x**2", "relation": "ne", "kind": "definedness", "source": "sqrt-branch"}],
        raw_target="x**2",
        target=2,
        box=[["1", "2"]],
        cluster=[_point(-root), _point(root)],
    )


def bivariate_link() -> dict[str, object]:
    root = mp.sqrt(2)
    return _problem(
        variables=["u", "x"],
        equations=["x**2-2", "u-x"],
        predicates=[
            {"expression": "u*x", "relation": "gt", "kind": "guard", "source": "same-sign"},
            {"expression": "x", "relation": "ne", "kind": "definedness", "source": "nonzero"},
        ],
        raw_target="u*x",
        target=2,
        box=[["1", "2"], ["1", "2"]],
        cluster=[_point(-root, -root), _point(root, root)],
    )


def cubic_with_complex_conjugates() -> dict[str, object]:
    roots = mp.polyroots([1, 0, 0, -2], maxsteps=300, error=False)
    real = mp.root(2, 3)
    return _problem(
        variables=["x"],
        equations=["x**3-2"],
        predicates=[],
        raw_target="x**3",
        target=2,
        box=[[mp.nstr(real - mp.mpf("0.2"), 40), mp.nstr(real + mp.mpf("0.2"), 40)]],
        cluster=[_point(root) for root in roots],
    )


def four_root_separator() -> dict[str, object]:
    xroot, yroot = mp.sqrt(2), mp.sqrt(3)
    cluster = []
    for xsign, ysign in itertools.product((-1, 1), repeat=2):
        x = xsign * xroot
        y = ysign * yroot
        cluster.append(_point(x + 2 * y, x, y))
    positive_u = xroot + 2 * yroot
    return _problem(
        variables=["u", "x", "y"],
        equations=["x**2-2", "y**2-3", "u-x-2*y"],
        predicates=[
            {"expression": "x", "relation": "gt", "kind": "guard", "source": "positive-x"},
            {"expression": "y", "relation": "ge", "kind": "branch", "source": "nonnegative-y-branch"},
        ],
        raw_target="x**2+y**2",
        target=5,
        box=[
            [mp.nstr(positive_u - mp.mpf("0.25"), 40), mp.nstr(positive_u + mp.mpf("0.25"), 40)],
            [mp.nstr(xroot - mp.mpf("0.25"), 40), mp.nstr(xroot + mp.mpf("0.25"), 40)],
            [mp.nstr(yroot - mp.mpf("0.25"), 40), mp.nstr(yroot + mp.mpf("0.25"), 40)],
        ],
        cluster=cluster,
    )


def positives() -> dict[str, dict[str, object]]:
    return {
        "quadratic-conjugates": quadratic_conjugates(),
        "bivariate-link": bivariate_link(),
        "cubic-complex-closure": cubic_with_complex_conjugates(),
        "four-root-separator": four_root_separator(),
    }


def negatives() -> dict[str, dict[str, object]]:
    base = quadratic_conjugates()
    result = {}

    incomplete_cluster = deepcopy(base)
    incomplete_cluster["approximate_cluster"] = [deepcopy(base["approximate_cluster"][1])]
    incomplete_cluster["cluster_declared_count"] = 1
    result["non-galois-stable-cluster"] = incomplete_cluster

    duplicate = deepcopy(base)
    duplicate["approximate_cluster"] = [deepcopy(base["approximate_cluster"][1])] * 2
    result["duplicated-cluster"] = duplicate

    padded = deepcopy(base)
    padded["cluster_padded"] = True
    result["declared-padding"] = padded

    incomplete_predicates = deepcopy(base)
    incomplete_predicates["complete_predicate_ledger"] = False
    result["incomplete-predicate-ledger"] = incomplete_predicates

    wrong_fibre = deepcopy(base)
    wrong_fibre["descriptor"]["minimal_polynomial_high_to_low"] = [1, -3]
    wrong_fibre["descriptor"]["isolating_interval"] = {"left": "2", "right": "4"}
    result["wrong-target-fibre"] = wrong_fibre

    empty_box = deepcopy(base)
    empty_box["proposal_box"] = [["10", "11"]]
    result["empty-proposal-box"] = empty_box

    nonprimitive = deepcopy(base)
    nonprimitive["descriptor"]["minimal_polynomial_high_to_low"] = [2, -4]
    result["nonprimitive-descriptor"] = nonprimitive

    source_mismatch = deepcopy(base)
    source_mismatch["equations"] = ["x**2-3"]
    result["source-generator-mismatch"] = source_mismatch
    return result


def metamorphics() -> dict[str, dict[str, object]]:
    result = {}
    reordered = deepcopy(four_root_separator())
    reordered["equations"] = list(reversed(reordered["equations"]))
    reordered["predicates"] = list(reversed(reordered["predicates"]))
    reordered["approximate_cluster"] = list(reversed(reordered["approximate_cluster"]))
    result["equation-predicate-cluster-order"] = reordered

    renamed = deepcopy(bivariate_link())
    renamed["variables"] = ["a", "b"]
    renamed["equations"] = ["b**2-2", "a-b"]
    renamed["predicates"][0]["expression"] = "a*b"
    renamed["predicates"][1]["expression"] = "b"
    renamed["raw_target"] = "a*b"
    result["variable-renaming"] = renamed

    permuted = deepcopy(bivariate_link())
    permuted["variables"] = ["x", "u"]
    permuted["proposal_box"] = list(reversed(permuted["proposal_box"]))
    permuted["approximate_cluster"] = [[point[1], point[0]] for point in permuted["approximate_cluster"]]
    result["variable-permutation"] = permuted
    return result
