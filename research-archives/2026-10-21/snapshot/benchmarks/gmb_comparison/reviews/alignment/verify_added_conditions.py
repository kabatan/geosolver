"""Exact synthetic checks for the two original-alignment additions.

This imports neither solver, reads no saved witness, and runs no optimization.
The finite checks supplement the general proof in the alignment review JSONs.
"""

import json
from fractions import Fraction
from itertools import combinations, permutations, product


def orientation(a, b, c):
    return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])


def added_order_conditions(points):
    a, b, c, k, q = points
    first = orientation(c, a, k) * orientation(c, a, b) < 0
    second = orientation(k, a, q) * orientation(k, a, b) < 0
    return first and second


def complete_cyclic_order(points):
    if len(set(points)) != 5:
        return False
    reference = orientation(*points[:3])
    return reference != 0 and all(
        reference * orientation(points[i], points[j], points[k]) > 0
        for i, j, k in combinations(range(5), 3)
    )


def exact_distance_squared(point, a, b):
    dx, dy = b[0] - a[0], b[1] - a[1]
    length_squared = dx * dx + dy * dy
    if length_squared == 0:
        raise ValueError("line endpoints coincide")
    parameter = Fraction(
        (point[0] - a[0]) * dx + (point[1] - a[1]) * dy,
        length_squared,
    )
    foot = a[0] + parameter * dx, a[1] + parameter * dy
    actual = (point[0] - foot[0]) ** 2 + (point[1] - foot[1]) ** 2
    assert actual == Fraction(orientation(a, b, point) ** 2, length_squared)
    return actual


def verify_order():
    # Eight exact points on x*x+y*y=25, in their counterclockwise order.
    circle = [(5, 0), (3, 4), (0, 5), (-3, 4), (-5, 0), (-3, -4), (0, -5), (3, -4)]
    tested = accepted = repeated = reflected = 0
    for a, b, c in permutations(range(8), 3):
        for k, q in product(range(8), repeat=2):
            points = tuple(circle[i] for i in (a, b, c, k, q))
            expected = complete_cyclic_order(points)
            actual = added_order_conditions(points)
            assert expected == actual, (a, b, c, k, q)
            mirror = tuple((x, -y) for x, y in points)
            assert added_order_conditions(mirror) == actual
            assert complete_cyclic_order(mirror) == expected
            repeated += len(set(points)) != 5
            accepted += actual
            tested += 1
            reflected += 1
    assert tested == 21504 and accepted == 560
    return {
        "base_assignments_checked": tested,
        "accepted_cyclic_orders": accepted,
        "duplicate_assignments_rejected": repeated,
        "reflected_assignments_checked": reflected,
        "mismatches": 0,
        "arithmetic": "exact integers",
        "scope": "order conditions only, not natural IMO configurations",
    }


def verify_nearer_tangent():
    examples = [
        ("M_closer", (0, 0), (1, 0), (0, 1), (0, 2), True),
        ("N_closer", (0, 0), (1, 0), (0, 2), (0, 1), False),
        ("same_side_tie", (0, 0), (1, 0), (0, 1), (1, 1), False),
        ("opposite_side_tie", (0, 0), (1, 0), (0, 1), (0, -1), False),
        ("zero_vs_positive", (0, 0), (5, 0), (2, 0), (0, 1), True),
        ("nonhorizontal_line", (2, 3), (5, 7), (-2, 6), (-6, 9), True),
    ]
    transforms = [
        lambda p: p,
        lambda p: (p[0], -p[1]),
        lambda p: (-p[1], p[0]),
        lambda p: (11 - 3 * p[1], -7 + 3 * p[0]),
    ]
    tested = 0
    for name, a, b, m, n, expected in examples:
        for transform in transforms:
            aa, bb, mm, nn = (transform(p) for p in (a, b, m, n))
            actual = exact_distance_squared(nn, aa, bb) > exact_distance_squared(mm, aa, bb)
            assert actual == expected, name
            tested += 1
    try:
        exact_distance_squared((1, 0), (0, 0), (0, 0))
    except ValueError:
        invalid_line_rejected = True
    else:
        raise AssertionError("a coincident-endpoint line must be undefined")
    return {
        "base_examples": len(examples),
        "transformed_examples_checked": tested,
        "tie_cases_rejected": 2,
        "degenerate_line_rejected": invalid_line_rejected,
        "mismatches": 0,
        "arithmetic": "exact rational foot and squared distance",
        "scope": "distance-order condition only, not natural IMO configurations",
    }


def main():
    print(
        json.dumps(
            {
                "cyclic_order": verify_order(),
                "nearer_tangent": verify_nearer_tangent(),
                "natural_cases_executed": 0,
                "saved_witnesses_read": 0,
                "optimizer_invocations": 0,
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
