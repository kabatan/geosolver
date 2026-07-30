from __future__ import annotations

from dataclasses import dataclass
import unittest

from source_affinity import AFFINE, NONLINEAR, find_affine_blocks, residual_affinity


@dataclass(frozen=True)
class Node:
    op: str
    inputs: tuple[int, ...]
    payload: object
    sort: str
    support: frozenset[int]


@dataclass(frozen=True)
class Program:
    nodes: tuple[Node, ...]
    residual_outputs: tuple[int, ...]
    dimension: int

    @property
    def residual_dimension(self) -> int:
        return len(self.residual_outputs)


def variable(position: int) -> Node:
    return Node("variable", (), position, "scalar", frozenset((position,)))


def constant(value: float = 1.0) -> Node:
    return Node("constant", (), value, "scalar", frozenset())


class SourceAffinityTest(unittest.TestCase):
    def test_variable_coefficient_block_is_jointly_affine(self) -> None:
        nodes = (
            variable(0),
            variable(1),
            Node("mul", (0, 1), None, "scalar", frozenset((0, 1))),
            constant(2.0),
            Node("mul", (3, 1), None, "scalar", frozenset((1,))),
            Node("add", (2, 4), None, "scalar", frozenset((0, 1))),
        )
        program = Program(nodes, (5,), 2)
        self.assertEqual(residual_affinity(program, (1,)), (AFFINE,))
        self.assertTrue(find_affine_blocks(program))

    def test_quadratic_and_branch_operations_fail_closed(self) -> None:
        square = Program(
            (
                variable(0),
                Node("mul", (0, 0), None, "scalar", frozenset((0,))),
            ),
            (1,),
            1,
        )
        sine = Program(
            (
                variable(0),
                Node("sin", (0,), None, "scalar", frozenset((0,))),
            ),
            (1,),
            1,
        )
        self.assertEqual(residual_affinity(square, (0,)), (NONLINEAR,))
        self.assertEqual(residual_affinity(sine, (0,)), (NONLINEAR,))
        self.assertFalse(find_affine_blocks(square))
        self.assertFalse(find_affine_blocks(sine))

    def test_affine_point_parameter_but_not_distance(self) -> None:
        nodes = (
            variable(0),
            constant(0.0),
            constant(1.0),
            Node("point", (1, 1), None, "point", frozenset()),
            Node("point", (2, 1), None, "point", frozenset()),
            Node("point_on_segment", (3, 4, 0), None, "point", frozenset((0,))),
            Node("attribute", (5,), "x", "scalar", frozenset((0,))),
            Node("distance", (5, 3), ("point", "point"), "scalar", frozenset((0,))),
        )
        affine = Program(nodes, (6,), 1)
        nonlinear = Program(nodes, (7,), 1)
        self.assertEqual(residual_affinity(affine, (0,)), (AFFINE,))
        self.assertEqual(residual_affinity(nonlinear, (0,)), (NONLINEAR,))

    def test_structural_rank_requires_distinct_rows(self) -> None:
        program = Program(
            (
                variable(0),
                variable(1),
                Node("add", (0, 1), None, "scalar", frozenset((0, 1))),
            ),
            (2,),
            2,
        )
        signatures = find_affine_blocks(program)
        self.assertTrue(any(signature[2] == 1 for signature in signatures))
        self.assertFalse(any(signature[2] == 2 for signature in signatures))


if __name__ == "__main__":
    unittest.main()
