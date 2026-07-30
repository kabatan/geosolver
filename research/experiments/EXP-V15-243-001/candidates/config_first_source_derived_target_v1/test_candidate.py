from __future__ import annotations

import copy
import hashlib
import json
import os
import unittest

import sympy as sp

from candidate import (
    activation_ready,
    configuration_contract,
    consume_repair,
    derive_descriptor,
    exact_value_commitment,
    repair_or_exact_outer_fallback,
)


ORIGINAL = b'{ "status": "EXACT_COORDINATE_FALLBACK_REJECTED", "authority_pass": false }\n'


def gate(count=12, clusters=2):
    return {
        "aggregate_only": True,
        "individual_rows_shared": False,
        "complete_coordinate_witness_attempt_count": count,
        "anonymous_structure_cluster_hashes": [
            hashlib.sha256(f"cluster-{index}".encode()).hexdigest()
            for index in range(clusters)
        ],
    }


def coordinate_proposal(value):
    descriptor = derive_descriptor(value)
    return {
        "status": "ALGEBRAIC_PROPOSAL",
        "coefficients_high_to_low": descriptor["minimal_polynomial_high_to_low"],
        "polynomial_metadata": {
            "square_free": True,
            "irreducible_over_Q": True,
            "isolating_interval": descriptor["isolating_interval"],
        },
        "numeric_lanes_used_only_for_proposal": True,
    }


def refinement(coordinates=(sp.Integer(1), sp.sqrt(2)), answer=1 + sp.sqrt(2)):
    values = [str(sp.N(item, 160)) for item in coordinates]
    answer_text = str(sp.N(answer, 160))
    replay = {
        key: {
            "guard_ok": True,
            "hard_feasible": True,
            "residual_reached": True,
            "answer_defined": True,
        }
        for key in ("155", "232", "320")
    }
    return {
        "status": "NUMERIC_ONLY",
        "independent_precision_lanes": True,
        "numeric_gate_1e_100": True,
        "configuration_fully_recognized": True,
        "configuration_algebraic_proposals": [coordinate_proposal(item) for item in coordinates],
        "coordinates_768bit_minimum": values,
        "coordinates_1024bit_minimum": values,
        "answer_768bit_minimum": answer_text,
        "answer_1024bit_minimum": answer_text,
        "float_source_replay": {
            "evaluation_defined": True,
            "guard_ok": True,
            "hard_feasible": True,
            "residual_is_authority": False,
        },
        "lane_source_replay": replay,
        # These deliberately malformed fields prove target PSLQ is not read.
        "pslq_coefficients_high_to_low": [999, -1],
        "pslq_1024_lane_residual": "nan",
        "polynomial_metadata": {"square_free": False},
    }


def exact_replay(proposal, raw):
    _descriptors, commitment = configuration_contract(proposal)
    source_sha = hashlib.sha256(b"generated-untouched-source").hexdigest()
    return {
        "status": "CONFIGURATION_EXACT_REPLAY_ACCEPTED",
        "backend": "FLINT_QQBAR_VIA_NEMO",
        "truth_used": False,
        "routing_used": False,
        "target_completeness_claim": False,
        "numeric_target_used_only_for_consistency": True,
        "coordinate_witness_sha256": commitment,
        "source_sha256": source_sha,
        "replayed_source_sha256": source_sha,
        "source_bytes_unchanged": True,
        "source_sha_matches": True,
        "coordinate_descriptors_exact": True,
        "coordinate_ordinals_attested": True,
        "constraints_exact": True,
        "guards_exact": True,
        "bounds_exact": True,
        "branches_selectors_phases_exact": True,
        "raw_answer_from_canonical_dag": True,
        "raw_answer_defined": True,
        "raw_answer_scalar": True,
        "post_process_absent": True,
        "raw_answer_exact": raw,
        "raw_answer_exact_sha256": exact_value_commitment(raw),
    }


def run(proposal, replay, aggregate=None):
    return repair_or_exact_outer_fallback(
        ORIGINAL,
        aggregate_gate=aggregate or gate(),
        refinement_proposal=proposal,
        exact_source_replay=replay,
    )


class ConfigFirstTests(unittest.TestCase):
    def test_aggregate_gate_is_anonymous_and_requires_count_and_clusters(self):
        self.assertTrue(activation_ready(gate()))
        self.assertFalse(activation_ready(gate(count=9)))
        self.assertFalse(activation_ready(gate(clusters=1)))
        exposed = gate()
        exposed["individual_rows_shared"] = True
        self.assertFalse(activation_ready(exposed))

    def test_positive_rational_quadratic_cubic_and_quartic(self):
        values = [
            sp.Rational(7, 3),
            1 + sp.sqrt(2),
            sp.real_root(2, 3),
            sp.sqrt(2) + sp.sqrt(3),
        ]
        for raw in values:
            proposal = refinement(answer=raw)
            payload = run(proposal, exact_replay(proposal, raw))
            self.assertNotEqual(payload, ORIGINAL)
            self.assertTrue(consume_repair(payload))

    def test_target_pslq_is_ignored_not_a_polynomial_selector(self):
        raw = 1 + sp.sqrt(2)
        first = refinement(answer=raw)
        second = copy.deepcopy(first)
        second["pslq_coefficients_high_to_low"] = [1, 0, 0, 0, 123456789]
        second["pslq_1024_lane_residual"] = None
        second["polynomial_metadata"] = None
        self.assertEqual(
            run(first, exact_replay(first, raw)),
            run(second, exact_replay(second, raw)),
        )

    def test_wrong_numeric_target_falls_back_byte_identically(self):
        raw = sp.sqrt(2)
        proposal = refinement(answer=raw)
        proposal["answer_1024bit_minimum"] = "99"
        payload = run(proposal, exact_replay(proposal, raw))
        self.assertIs(payload, ORIGINAL)

    def test_mutated_exact_answer_falls_back_byte_identically(self):
        raw = sp.sqrt(2)
        proposal = refinement(answer=raw)
        replay = exact_replay(proposal, raw)
        replay["raw_answer_exact"] = sp.sqrt(3)
        payload = run(proposal, replay)
        self.assertIs(payload, ORIGINAL)

    def test_undefined_and_non_scalar_answers_fall_back(self):
        proposal = refinement()
        for raw in (None, sp.Matrix([1, 2]), sp.Symbol("unknown"), sp.pi):
            replay = exact_replay(proposal, sp.Integer(1))
            replay["raw_answer_exact"] = raw
            if isinstance(raw, sp.Expr):
                replay["raw_answer_exact_sha256"] = exact_value_commitment(raw)
            self.assertIs(run(proposal, replay), ORIGINAL)

    def test_coordinate_descriptor_mutation_falls_back(self):
        raw = 1 + sp.sqrt(2)
        proposal = refinement(answer=raw)
        replay = exact_replay(proposal, raw)
        proposal["configuration_algebraic_proposals"][0]["coefficients_high_to_low"] = [1, -2]
        self.assertIs(run(proposal, replay), ORIGINAL)

    def test_source_guard_branch_and_hash_obligations_fail_closed(self):
        raw = sp.sqrt(2)
        proposal = refinement(answer=raw)
        for key in ("constraints_exact", "guards_exact", "branches_selectors_phases_exact"):
            replay = exact_replay(proposal, raw)
            replay[key] = False
            self.assertIs(run(proposal, replay), ORIGINAL)
        replay = exact_replay(proposal, raw)
        replay["replayed_source_sha256"] = hashlib.sha256(b"mutated").hexdigest()
        self.assertIs(run(proposal, replay), ORIGINAL)

    def test_wrong_root_swapped_ordinal_and_descriptor_mutation_rejected_at_consumer(self):
        raw = sp.sqrt(2)
        proposal = refinement(answer=raw)
        valid = json.loads(run(proposal, exact_replay(proposal, raw)))

        wrong_root = copy.deepcopy(valid)
        wrong_root["target_descriptor"]["isolating_interval"]["left"] = "-2"
        wrong_root["target_descriptor"]["isolating_interval"]["right"] = "-1"
        self.assertFalse(consume_repair(json.dumps(wrong_root).encode()))

        swapped = copy.deepcopy(valid)
        swapped["target_descriptor"]["selected_real_root_index"] = 0
        self.assertFalse(consume_repair(json.dumps(swapped).encode()))

        mutated = copy.deepcopy(valid)
        mutated["target_descriptor"]["minimal_polynomial_high_to_low"][0] += 1
        self.assertFalse(consume_repair(json.dumps(mutated).encode()))

    def test_nonmatching_status_and_incomplete_gate_preserve_fallback(self):
        raw = sp.sqrt(2)
        proposal = refinement(answer=raw)
        proposal["status"] = "PSLQ_PROPOSAL"
        self.assertIs(run(proposal, exact_replay(refinement(answer=raw), raw)), ORIGINAL)
        good = refinement(answer=raw)
        self.assertIs(run(good, exact_replay(good, raw), gate(count=9)), ORIGINAL)

    def test_cpu15_only(self):
        self.assertEqual(os.sched_getaffinity(0), {15})


if __name__ == "__main__":
    unittest.main()
