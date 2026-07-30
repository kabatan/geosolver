from __future__ import annotations

import types
import unittest

from champion_overlay import install, merge_block_proposals


FORMULATION = {
    "task": "solve",
    "variables": {"names": ["x", "y"]},
    "construction": [],
    "constraints": [
        {"def": "x", "value": 1},
        {"def": "y - x", "value": 1},
    ],
    "guards": [],
}


class ChampionOverlayTests(unittest.TestCase):
    def test_block_proposals_are_additive_and_bounded(self):
        endpoints = ({"point": [0.0, 0.0]}, {"point": [2.0, 2.0]})

        def factory(_document, plan, starts, _deadline):
            self.assertTrue(plan.applicable)
            self.assertEqual(starts, ((0.0, 0.0), (2.0, 2.0)))
            return ((1.0, 2.0), (3.0, 4.0), (5.0, 6.0))

        merged, audit = merge_block_proposals(
            FORMULATION,
            endpoints,
            hard_deadline=10.0,
            proposal_factory=factory,
            maximum_block_proposals=2,
        )
        self.assertEqual(merged[:2], endpoints)
        self.assertEqual(merged[2:], ({"point": [1.0, 2.0]}, {"point": [3.0, 4.0]}))
        self.assertEqual(audit["baseline_endpoints_removed"], 0)
        self.assertEqual(audit["block_proposals_presented_to_source_replay"], 2)

    def test_installed_seam_calls_original_source_replay(self):
        replayed = []

        def original_fresh(document, endpoints, *, hard_deadline):
            replayed.extend(endpoints)
            # Fake the champion's source replay: only the generated exact root
            # survives. The overlay itself has no acceptance authority.
            return tuple(
                endpoint
                for endpoint in endpoints
                if endpoint.get("point") == [1.0, 2.0]
            )

        def original_plan(**kwargs):
            return {"base": True, **kwargs}

        base = types.SimpleNamespace(
            _fresh_replay_candidates=original_fresh,
            _plan=original_plan,
        )
        champion = types.SimpleNamespace(BASE=base)
        audit = install(
            champion,
            proposal_factory=lambda *_args: ((1.0, 2.0),),
            mechanism_hash="sha256:test",
        )
        accepted = base._fresh_replay_candidates(
            FORMULATION,
            ({"point": [0.0, 0.0]},),
            hard_deadline=10.0,
        )
        self.assertEqual(accepted, ({"point": [1.0, 2.0]},))
        self.assertEqual(len(replayed), 2)
        self.assertFalse(audit()["source_replay_bypassed"])
        self.assertFalse(audit()["canonical_verifier_bypassed"])

    def test_inapplicable_merge_is_object_order_preserving(self):
        document = {
            "task": "solve",
            "variables": {"names": ["x", "y"]},
            "construction": [],
            "constraints": [{"def": "x + y", "value": 0}],
            "guards": [],
        }
        endpoints = ({"point": [0.0, 0.0]},)
        merged, audit = merge_block_proposals(
            document,
            endpoints,
            hard_deadline=10.0,
            proposal_factory=lambda *_args: self.fail("factory must not run"),
        )
        self.assertEqual(merged, endpoints)
        self.assertFalse(audit["applicable"])

    def test_proposal_failure_falls_back_to_original_endpoints(self):
        endpoints = ({"point": [0.0, 0.0]},)

        def broken_factory(*_args):
            raise RuntimeError("generated counterexample")

        merged, audit = merge_block_proposals(
            FORMULATION,
            endpoints,
            hard_deadline=10.0,
            proposal_factory=broken_factory,
        )
        self.assertEqual(merged, endpoints)
        self.assertEqual(
            audit["proposal_skip_reason"],
            "PROPOSAL_FACTORY_FAILED:RuntimeError",
        )

    def test_invalid_proposal_shape_falls_back(self):
        endpoints = ({"point": [0.0, 0.0]},)
        merged, audit = merge_block_proposals(
            FORMULATION,
            endpoints,
            hard_deadline=10.0,
            proposal_factory=lambda *_args: ((float("nan"), 2.0), (1.0,), (0.0, 0.0)),
        )
        self.assertEqual(merged, endpoints)
        self.assertEqual(
            audit["proposal_skip_reason"],
            "NO_FINITE_SHAPE_VALID_BLOCK_PROPOSAL",
        )


if __name__ == "__main__":
    unittest.main()
