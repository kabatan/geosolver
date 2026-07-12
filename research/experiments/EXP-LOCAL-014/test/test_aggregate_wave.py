from __future__ import annotations

import copy
import json
import sys
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path


EXPERIMENT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(EXPERIMENT))
import aggregate_wave as aggregate


PAIRS = (
    (aggregate.E3, f"{aggregate.E3}-SHADOW"),
    (aggregate.E4, f"{aggregate.E4}-SHADOW"),
)
VARIANTS = (
    aggregate.PRIMARY_CONTROL,
    aggregate.WORK_COMPARATOR,
    *(name for pair in PAIRS for name in pair),
)
CASES = (
    {
        "family_id": aggregate.NEAR_RANK,
        "instance_id": "near",
        "local_case_index": 1,
        "replay_checksum": "near-replay",
        "saved_starts_checksum": "near-starts",
        "saved_starts_shape": [2, 32],
        "source_case_index": 13,
        "targets": 1,
    },
    {
        "family_id": aggregate.STRICT_GUARD,
        "instance_id": "guard",
        "local_case_index": 2,
        "replay_checksum": "guard-replay",
        "saved_starts_checksum": "guard-starts",
        "saved_starts_shape": [2, 32],
        "source_case_index": 37,
        "targets": 1,
    },
)


def spec(*, pairs=PAIRS, variants=VARIANTS) -> aggregate.StageSpec:
    return aggregate.StageSpec(
        stage="g0",
        expected_cases=CASES,
        variants=variants,
        candidate_shadow_pairs=pairs,
        maximum_starts=32,
        registration_sha256="registration-hash",
        frozen_inputs={"frozen": "hash"},
        strict_target_requirement=1,
        near_rank_shadow_unsafe_minimum=1,
        support_family_minimum=1,
    )


def attempt(variant: str, problem: dict, start_index: int) -> dict:
    near = problem["family_id"] == aggregate.NEAR_RANK
    shadow = variant.endswith("-SHADOW")
    filtered = variant in (aggregate.WORK_COMPARATOR, aggregate.E3, aggregate.E4)
    unsafe = near and start_index == 1 and (variant == aggregate.PRIMARY_CONTROL or shadow)
    dropped = near and start_index == 1 and filtered
    qualified = not dropped
    safe = qualified and not unsafe
    candidate_name = variant.removesuffix("-SHADOW")
    diagnostic = f"mechanism={candidate_name};proofs=1;shadow={'true' if shadow else 'false'}"
    return {
        "assessor_gold_matched": safe,
        "assessor_matched_target_id": "target-001" if safe else None,
        "assessor_qualified": qualified,
        "assessor_target_ambiguous": False,
        "budget_exhausted": False,
        "diagnostic": diagnostic,
        "endpoint": None if dropped else ([9.0] if unsafe else [0.0]),
        "evaluation_count_mismatch": False,
        "exception": None,
        "instance_id": problem["instance_id"],
        "iterations": 1,
        "observed_evaluations": 600,
        "reported_accepted": safe,
        "reported_evaluations": 600,
        "start": [float(start_index)],
        "start_index": start_index,
        "variant": variant,
    }


def document(problem: dict, variants=VARIANTS) -> dict:
    attempts = [
        attempt(variant, problem, index)
        for variant in variants
        for index in range(1, 9)
    ]
    snapshots = []
    terminals = []
    for variant in variants:
        rows = [row for row in attempts if row["variant"] == variant]
        snapshots.extend(
            aggregate._expected_snapshots(
                rows,
                problem["targets"],
                variant=variant,
                instance=problem["instance_id"],
                family=problem["family_id"],
            )
        )
        suffix = aggregate._suffix_work(rows, problem["targets"])
        censored = suffix if suffix is not None and suffix <= 4_800 else 4_800
        terminals.append(
            {
                "attempt_count": len(rows),
                "callback_work": 4_800,
                "right_censored_suffix_stable_work": censored,
                "suffix_stable_work": suffix,
                "variant": variant,
            }
        )
    index = problem["local_case_index"]
    return {
        "attempts": attempts,
        "authorization": {
            "frozen_inputs": {"frozen": "hash"},
            "registration_sha256": "registration-hash",
        },
        "callback_thresholds": [600, 1_200, 2_400, 4_800],
        "case_callback_stop": 4_800,
        "case_count": 2,
        "case_index": index,
        "environment": {
            "blas_threads": 1,
            "julia_threads": 1,
            "mkl_num_threads": "1",
            "omp_num_threads": "1",
            "openblas_num_threads": "1",
        },
        "host_execution": {
            "assigned_cpu": index - 1,
            "case_process_limit": 16,
            "cpus_allowed_list": str(index - 1),
            "solver_worker_count": 1,
        },
        "maximum_starts": 32,
        "problem_manifest": [copy.deepcopy(problem)],
        "revision": {"git_dirty": False, "git_head": "revision"},
        "schema": aggregate.SHARD_SCHEMA,
        "stage": "g0",
        "terminals": terminals,
        "threshold_snapshots": snapshots,
        "variant_manifest": [{"name": variant} for variant in variants],
    }


class AggregateWaveTests(unittest.TestCase):
    def write_documents(self, root: Path, documents: list[dict]) -> list[Path]:
        paths = []
        for document_value in documents:
            path = root / f"case-{document_value['case_index']}.json"
            path.write_text(json.dumps(document_value), encoding="utf-8")
            paths.append(path)
        return paths

    def test_valid_two_pair_campaign_passes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            paths = self.write_documents(Path(directory), [document(case) for case in CASES])
            result = aggregate.aggregate(paths, spec())
        self.assertFalse(any(result["accounting"].values()))
        self.assertEqual(result["survivors"], [aggregate.E3, aggregate.E4])
        for candidate in result["survivors"]:
            gate = result["candidate_gates"][candidate]
            self.assertTrue(gate["passes_stage"])
            self.assertEqual(gate["callback_mismatches"], 0)
            self.assertEqual(gate["trajectory_mismatches"], 0)
            self.assertEqual(gate["strict_targets_found"], 1)
            self.assertEqual(gate["near_rank_candidate_unsafe"], 0)
            self.assertEqual(gate["near_rank_shadow_unsafe"], 1)
            self.assertEqual(gate["right_censored_work_ratio_vs_e1"], 1.0)

    def test_one_candidate_pair_is_not_hard_coded(self) -> None:
        pair = (PAIRS[0],)
        variants = (aggregate.PRIMARY_CONTROL, aggregate.WORK_COMPARATOR, *PAIRS[0])
        with tempfile.TemporaryDirectory() as directory:
            paths = self.write_documents(
                Path(directory), [document(case, variants) for case in CASES]
            )
            result = aggregate.aggregate(paths, spec(pairs=pair, variants=variants))
        self.assertEqual(result["survivors"], [aggregate.E3])

    def test_r1_exact_tie_selects_narrower_e3(self) -> None:
        r1_spec = replace(spec(), stage="r1")
        documents = [document(case) for case in CASES]
        for value in documents:
            value["stage"] = "r1"
        with tempfile.TemporaryDirectory() as directory:
            paths = self.write_documents(Path(directory), documents)
            result = aggregate.aggregate(paths, r1_spec)
        self.assertEqual(result["selected_finalist"], aggregate.E3)

    def test_missing_or_duplicate_shard_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            one = self.write_documents(root, [document(CASES[0])])
            with self.assertRaisesRegex(ValueError, "expected 2 shards"):
                aggregate.aggregate(one, spec())
            duplicate = [document(CASES[0]), document(CASES[0])]
            paths = []
            for index, value in enumerate(duplicate):
                path = root / f"duplicate-{index}.json"
                path.write_text(json.dumps(value), encoding="utf-8")
                paths.append(path)
            with self.assertRaisesRegex(ValueError, "missing or duplicated"):
                aggregate.aggregate(paths, spec())

    def test_trajectory_mismatch_fails_only_the_affected_candidate(self) -> None:
        documents = [document(case) for case in CASES]
        row = next(
            item for item in documents[0]["attempts"]
            if item["variant"] == f"{aggregate.E4}-SHADOW"
        )
        row["diagnostic"] = "mechanism=changed;proofs=1;shadow=true"
        with tempfile.TemporaryDirectory() as directory:
            paths = self.write_documents(Path(directory), documents)
            result = aggregate.aggregate(paths, spec())
        self.assertTrue(result["candidate_gates"][aggregate.E3]["passes_stage"])
        self.assertFalse(result["candidate_gates"][aggregate.E4]["passes_stage"])
        self.assertEqual(result["candidate_gates"][aggregate.E4]["trajectory_mismatches"], 1)

    def test_callback_cap_and_report_mismatch_are_recomputed(self) -> None:
        documents = [document(case) for case in CASES]
        row = documents[0]["attempts"][0]
        row["observed_evaluations"] = 601
        row["evaluation_count_mismatch"] = True
        with tempfile.TemporaryDirectory() as directory:
            paths = self.write_documents(Path(directory), documents)
            result = aggregate.aggregate(paths, spec())
        self.assertGreater(result["accounting"]["attempt_callback_cap_violations"], 0)
        self.assertGreater(result["accounting"]["evaluation_count_mismatches"], 0)
        self.assertFalse(any(
            gate["passes_stage"] for gate in result["candidate_gates"].values()
        ))


if __name__ == "__main__":
    unittest.main()
