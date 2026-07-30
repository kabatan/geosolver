from __future__ import annotations

import unittest

from candidate import ConfirmedIdentityCache
import worker


def _descriptor(polynomial: list[int], ordinal: int) -> dict[str, object]:
    return {
        "minimal_polynomial_high_to_low": polynomial,
        "selected_real_root_index": ordinal,
        "isolating_interval": {
            "left": "0",
            "right": "2",
            "multiplicity": 1,
            "real_root_index": ordinal,
        },
        "proposal_relation_low_to_high": list(reversed(polynomial)),
        "confirmation_relation_low_to_high": list(reversed(polynomial)),
        "target_768": "1.0",
        "target_1024": "1.0",
    }


def _ordinary(
    descriptor: dict[str, object],
    *,
    raw_target: str,
    branch: str,
) -> dict[str, object]:
    return {
        "status": "TARGET_AUTHORITY_READY",
        "authority_pass": True,
        "descriptor": descriptor,
        "raw_target_fixture": raw_target,
        "branch_fixture": branch,
    }


class _Candidate:
    endpoint_sha256 = "endpoint"
    residual_inf = 0.0
    provisional_target = 1.0
    cluster_ordinal = 0
    cluster_rank = 0


class CacheTests(unittest.TestCase):
    def test_only_success_is_cached(self) -> None:
        cache = ConfirmedIdentityCache()
        identity = ((1, 0, -2), 1)
        self.assertFalse(cache.already_confirmed(identity))
        cache.confirm(None)
        self.assertFalse(cache.already_confirmed(identity))
        cache.confirm(identity)
        self.assertTrue(cache.already_confirmed(identity))
        self.assertEqual(cache.count(), 1)

    def test_distinct_root_ordinal_is_not_collapsed(self) -> None:
        cache = ConfirmedIdentityCache()
        cache.confirm(((1, 0, -2), 0))
        self.assertFalse(cache.already_confirmed(((1, 0, -2), 1)))


class WorkerAdversarialTests(unittest.TestCase):
    def setUp(self) -> None:
        self.saved = (
            worker._ORIGINAL_ORDINARY,
            worker._ORIGINAL_EXACT_OUTER,
            worker.OUTER._ORDINARY_HP,
            worker._CACHE,
        )
        worker._CACHE = ConfirmedIdentityCache()

    def tearDown(self) -> None:
        (
            worker._ORIGINAL_ORDINARY,
            worker._ORIGINAL_EXACT_OUTER,
            worker.OUTER._ORDINARY_HP,
            worker._CACHE,
        ) = self.saved

    def _install(
        self,
        proposals: list[dict[str, object]],
        exact_passes: list[bool],
    ) -> list[dict[str, object]]:
        remaining = list(proposals)
        exact_remaining = list(exact_passes)
        exact_inputs: list[dict[str, object]] = []

        def ordinary(**_kwargs):
            return remaining.pop(0)

        def exact(**_kwargs):
            proposal = worker.OUTER._ORDINARY_HP()
            exact_inputs.append(proposal)
            passed = exact_remaining.pop(0)
            return {
                "status": "TARGET_AUTHORITY_READY" if passed else "REJECTED",
                "authority_pass": passed,
                "descriptor": proposal["descriptor"] if passed else None,
            }

        worker._ORIGINAL_ORDINARY = ordinary
        worker._ORIGINAL_EXACT_OUTER = exact
        return exact_inputs

    def test_cache_cannot_hit_before_exact_acceptance(self) -> None:
        descriptor = _descriptor([1, 0, -2], 1)
        proposals = [
            _ordinary(descriptor, raw_target="target-a", branch="left"),
            _ordinary(descriptor, raw_target="target-a", branch="left"),
        ]
        exact_inputs = self._install(proposals, [True])

        first = worker._run_cached(candidate=_Candidate())
        second = worker._run_cached(candidate=_Candidate())

        self.assertTrue(first["authority_pass"])
        self.assertEqual(len(exact_inputs), 1)
        self.assertFalse(second["authority_pass"])
        self.assertIsNone(second["descriptor"])
        self.assertTrue(second["confirmed_identity_cache_hit"])

    def test_failed_exact_replay_never_enables_skip(self) -> None:
        descriptor = _descriptor([1, -3], 0)
        proposals = [
            _ordinary(descriptor, raw_target="target-a", branch="left"),
            _ordinary(descriptor, raw_target="target-a", branch="left"),
        ]
        exact_inputs = self._install(proposals, [False, True])

        first = worker._run_cached(candidate=_Candidate())
        second = worker._run_cached(candidate=_Candidate())

        self.assertFalse(first["authority_pass"])
        self.assertTrue(second["authority_pass"])
        self.assertEqual(len(exact_inputs), 2)

    def test_alternate_witness_is_not_promoted_to_authority(self) -> None:
        descriptor = _descriptor([1, 0, -2], 1)
        proposals = [
            _ordinary(descriptor, raw_target="target-a", branch="left"),
            _ordinary(descriptor, raw_target="target-b", branch="right"),
        ]
        exact_inputs = self._install(proposals, [True])

        accepted = worker._run_cached(candidate=_Candidate())
        alternate = worker._run_cached(candidate=_Candidate())

        self.assertTrue(accepted["authority_pass"])
        self.assertEqual(len(exact_inputs), 1)
        self.assertEqual(
            alternate["ordinary_hp_proposal"]["raw_target_fixture"],
            "target-b",
        )
        self.assertEqual(
            alternate["ordinary_hp_proposal"]["branch_fixture"],
            "right",
        )
        self.assertFalse(alternate["authority_pass"])
        self.assertIsNone(alternate["descriptor"])

    def test_multi_target_set_survives_duplicate_skip(self) -> None:
        descriptor_a = _descriptor([1, -1], 0)
        descriptor_b = _descriptor([1, -2], 0)
        proposals = [
            _ordinary(descriptor_a, raw_target="target-a", branch="left"),
            _ordinary(descriptor_b, raw_target="target-b", branch="right"),
            _ordinary(descriptor_a, raw_target="target-a-alt", branch="right"),
        ]
        exact_inputs = self._install(proposals, [True, True])

        results = [worker._run_cached(candidate=_Candidate()) for _ in range(3)]
        emitted = {
            worker._identity(result)
            for result in results
            if result.get("authority_pass") is True
        }

        self.assertEqual(
            emitted,
            {worker._identity({"descriptor": descriptor_a}),
             worker._identity({"descriptor": descriptor_b})},
        )
        self.assertEqual(len(exact_inputs), 2)
        self.assertTrue(results[2]["confirmed_identity_cache_hit"])


if __name__ == "__main__":
    unittest.main()
