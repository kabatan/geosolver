from __future__ import annotations

import copy
import os
import unittest

import aggregate_scans
import connector
import source_gate


SOURCE_SHA = "a" * 64


def equality_cycle_source() -> dict:
    return {
        "task": "solve",
        "variables": {"names": ["x", "y", "z"]},
        "construction": [
            {"name": "A", "expr": "Point(0,0)"},
            {"name": "B", "expr": "Point(1,0)"},
            {"name": "L", "expr": "Line(A,B)"},
        ],
        "constraints": [
            {"def": "x", "value": "y"},
            {"def": "y", "value": "z"},
            {"def": "z", "value": "x"},
            {"def": "x", "value": 0},
        ],
        "guards": [],
        "bounds": None,
        "answer": "x",
        "post_process": None,
    }


def geometry_cycle_source() -> dict:
    return {
        "task": "solve",
        "variables": {"names": ["x", "y", "t"]},
        "construction": [
            {"name": "A", "expr": "Point(0,0)"},
            {"name": "B", "expr": "Point(2,0)"},
            {"name": "L", "expr": "Line(A,B)"},
            {"name": "gamma", "expr": "Circle(A,1)"},
            {"name": "P", "expr": "Point(x,y)"},
            {"name": "Q", "expr": "PointOnLine(L,t)"},
            {"name": "R", "expr": "PointOnCircle(gamma,t)"},
            {"name": "X", "expr": "Intersect(L,gamma,n=0)"},
        ],
        "constraints": [
            {"def": "OnSegment(P,A,B)", "value": 0},
            {"def": "OnLine(P,L)", "value": 0},
            {"def": "x", "value": "y"},
        ],
        "guards": ["Bound(t,(0,1))"],
        "bounds": None,
        "answer": "x",
        "post_process": "",
    }


class SourceGateTests(unittest.TestCase):
    def test_closed_equality_and_geometry_cycles_pass_static_gate(self):
        equality = source_gate.scan(equality_cycle_source(), SOURCE_SHA)
        geometry = source_gate.scan(geometry_cycle_source(), SOURCE_SHA)
        for result in (equality, geometry):
            self.assertTrue(result["eligible"])
            self.assertEqual(result["closed_factor_count"], result["factor_total"])
            self.assertGreaterEqual(result["cycle_rank"], 1)
            self.assertGreaterEqual(len(result["factor_kind_counts"]), 2)
            self.assertLessEqual(result["sheet_product"], 8)
            self.assertTrue(result["typed_inverse_and_collapse"])
            self.assertEqual(result["factor_duplication_total_weight"], 1)

    def test_moving_opaque_ambiguous_tangent_zero_and_strict_fail_whole_source(self):
        variants = []
        moving = geometry_cycle_source()
        moving["construction"][2]["expr"] = "Line(P,B)"
        variants.append(moving)
        opaque = geometry_cycle_source()
        opaque["constraints"][0] = {"def": "Distance(P,A)", "value": 1}
        variants.append(opaque)
        ambiguous = geometry_cycle_source()
        ambiguous["construction"][-1]["expr"] = "Intersect(L,gamma)"
        variants.append(ambiguous)
        tangent = geometry_cycle_source()
        tangent["construction"].insert(2, {"name": "C", "expr": "Point(-2,1)"})
        tangent["construction"].insert(3, {"name": "D", "expr": "Point(2,1)"})
        tangent["construction"][4]["expr"] = "Line(C,D)"
        variants.append(tangent)
        zero = geometry_cycle_source()
        zero["construction"][3]["expr"] = "Circle(A,0)"
        variants.append(zero)
        strict = geometry_cycle_source()
        strict["guards"] = ["t < 1"]
        variants.append(strict)
        tied = geometry_cycle_source()
        tied["bounds"] = {"t": [0, 2]}
        variants.append(tied)
        composite = geometry_cycle_source()
        composite["construction"][4]["expr"] = "Point(x+y,y)"
        variants.append(composite)
        for document in variants:
            result = source_gate.scan(document, SOURCE_SHA)
            self.assertFalse(result["eligible"])
            self.assertEqual(result["decision"], "UNKNOWN_FULL_ATTEMPT_FALLBACK")

    def test_sincos_requires_explicit_period_one_phase(self):
        explicit = geometry_cycle_source()
        explicit["construction"].insert(-1, {"name": "S", "expr": "Point(cos(2*pi*t),sin(2*pi*t))"})
        self.assertTrue(source_gate.scan(explicit, SOURCE_SHA)["eligible"])
        implicit = geometry_cycle_source()
        implicit["construction"].insert(-1, {"name": "S", "expr": "Point(cos(t),sin(t))"})
        result = source_gate.scan(implicit, SOURCE_SHA)
        self.assertFalse(result["eligible"])
        self.assertEqual(result["decision"], "UNKNOWN_FULL_ATTEMPT_FALLBACK")

    def test_sheet_product_above_eight_and_small_factor_graph_hold(self):
        excessive = geometry_cycle_source()
        for index in range(4):
            excessive["construction"].insert(
                -1,
                {"name": f"S{index}", "expr": "PointOnCircle(gamma,t)"},
            )
        result = source_gate.scan(excessive, SOURCE_SHA)
        self.assertFalse(result["eligible"])
        self.assertFalse(result["static_gates"]["sheet_product_at_most_8"])
        small = equality_cycle_source()
        small["constraints"] = small["constraints"][:2]
        result = source_gate.scan(small, SOURCE_SHA)
        self.assertFalse(result["eligible"])
        self.assertFalse(result["static_gates"]["factor_count_3_to_16"])

    def test_recurrence_requires_four_attempts_and_two_anonymous_hashes(self):
        first = source_gate.scan(equality_cycle_source(), SOURCE_SHA)
        second = source_gate.scan(geometry_cycle_source(), SOURCE_SHA)
        self.assertNotEqual(
            first["anonymous_structural_fingerprint_sha256"],
            second["anonymous_structural_fingerprint_sha256"],
        )
        held = aggregate_scans.aggregate([first, first, second])
        passed = aggregate_scans.aggregate([first, first, second, second])
        self.assertFalse(held["recurrence_gate_pass"])
        self.assertTrue(passed["recurrence_gate_pass"])
        self.assertFalse(passed["individual_source_rows_emitted"])

    def test_cpu14_only(self):
        self.assertEqual(os.sched_getaffinity(0), {14})


class ConnectorTests(unittest.TestCase):
    def test_partition_is_gate_bound_and_never_exceeds_one_quarter(self):
        scan = source_gate.scan(geometry_cycle_source(), SOURCE_SHA)
        recurrence = aggregate_scans.aggregate([scan, scan, source_gate.scan(equality_cycle_source(), SOURCE_SHA), source_gate.scan(equality_cycle_source(), SOURCE_SHA)])
        for count in range(1, 33):
            partition = connector.partition_starts(count, scan, recurrence)
            self.assertTrue(partition.activated)
            self.assertLessEqual(4 * len(partition.side_ordinals), count)
            self.assertGreaterEqual(4 * len(partition.baseline_ordinals), 3 * count)
            self.assertEqual(
                sorted((*partition.baseline_ordinals, *partition.side_ordinals)),
                list(range(count)),
            )
        held = connector.partition_starts(16, scan, {"recurrence_gate_pass": False})
        self.assertFalse(held.activated)
        self.assertEqual(held.baseline_ordinals, tuple(range(16)))
        self.assertFalse(held.side_ordinals)

    def test_proposal_firewall_and_canonical_authority(self):
        proposal = {
            "status": "DIVIDE_CONCUR_PROPOSAL_ONLY",
            "authority_pass": False,
            "descriptor": None,
            "beta": 1.0,
            "fixed_iterations": 64,
            "canonical_lm_required": True,
            "canonical_source_replay_required": True,
            "truth_used": False,
        }
        self.assertEqual(
            connector.proposal_disposition(proposal),
            "SEND_TO_CANONICAL_LM_AND_REPLAY",
        )
        malformed = dict(proposal, authority_pass=True)
        self.assertEqual(
            connector.proposal_disposition(malformed),
            "FULL_ATTEMPT_BASELINE_FALLBACK",
        )
        authority = {
            "status": "TARGET_AUTHORITY_READY",
            "authority_pass": True,
            "descriptor": {"minimal_polynomial": [1, -1]},
            "canonical_lm_completed": True,
            "canonical_source_replay_exact": True,
            "guard_replay_exact": True,
            "branch_replay_exact": True,
            "raw_target_replay_exact": True,
            "proposal_was_authority": False,
        }
        self.assertTrue(connector.canonical_authority_ready(authority))
        self.assertFalse(connector.canonical_authority_ready(dict(authority, branch_replay_exact=False)))

    def test_replica_factor_weights_sum_to_one(self):
        for arity in range(1, 5):
            self.assertAlmostEqual(sum(connector.replica_weights(arity)), 1.0)


if __name__ == "__main__":
    unittest.main()
