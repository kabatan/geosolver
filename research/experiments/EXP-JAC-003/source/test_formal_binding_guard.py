from __future__ import annotations

import copy
import hashlib
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import formal_binding_guard as guard  # noqa: E402


AMENDMENT = HERE.parent / "formal-binding-amendment.json"


class FormalBindingGuardUnitTests(unittest.TestCase):
    def test_amendment_binds_executing_checker_and_unique_formal_flags(self) -> None:
        amendment = json.loads(AMENDMENT.read_bytes())
        checker_sha = hashlib.sha256(
            (HERE / "formal_binding_guard.py").read_bytes()
        ).hexdigest()
        self.assertEqual(amendment["checker"]["sha256"], checker_sha)
        child = amendment["execution_plan"]["exact_child_command_tokens"]
        for flag in (
            "--repo",
            "--source-lock",
            "--input-manifest",
            "--candidate",
            "--truth",
            "--frozen-k0",
            "--staging",
            "--julia",
        ):
            self.assertEqual(child.count(flag), 1)

    def test_hashing_does_not_interpret_gzip_payload(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            payload = Path(raw) / "opaque-outcome.json.gz"
            payload.write_bytes(b"not a gzip member and not JSON")
            self.assertEqual(
                guard._sha256_file(payload),
                hashlib.sha256(payload.read_bytes()).hexdigest(),
            )

    def test_atomic_audit_write_is_create_once(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            output = Path(raw) / "audit.json"
            guard._write_json_once(output, {"passed": True})
            self.assertEqual(json.loads(output.read_bytes()), {"passed": True})
            with self.assertRaises(guard.BindingError):
                guard._write_json_once(output, {"passed": False})

    def test_symlink_or_reparse_component_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            target = root / "target"
            target.mkdir()
            link = root / "link"
            try:
                os.symlink(target, link, target_is_directory=True)
            except OSError as error:
                self.skipTest(f"symlink creation is unavailable: {error}")
            with self.assertRaises(guard.BindingError):
                guard._absolute_plain_path(link, must_exist=True, kind="test path")

    def test_relative_repo_path_rejects_parent_and_backslash_aliases(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            with self.assertRaises(guard.BindingError):
                guard._relative_repo_path(
                    root, "../escape", must_exist=False, kind="test path"
                )
            with self.assertRaises(guard.BindingError):
                guard._relative_repo_path(
                    root, "alias\\file", must_exist=False, kind="test path"
                )

    def test_iso_time_requires_timezone(self) -> None:
        self.assertLess(
            guard._parse_utc("2026-07-10T00:00:00Z", "start"),
            guard._parse_utc("2026-07-10T00:00:01+00:00", "end"),
        )
        with self.assertRaises(guard.BindingError):
            guard._parse_utc("2026-07-10T00:00:00", "naive")


class FormalBindingGuardPostTests(unittest.TestCase):
    def _fixture(self, root: Path) -> dict[str, object]:
        staging = root / "staging"
        staging.mkdir()
        paths = {
            "repo": root / "repo",
            "staging": staging,
            "partial": root / "partial",
            "official": root / "official",
            "outer_audit": root / "outer.json",
            "host_observation": root / "host.json",
            "source_observation": root / "source.json",
            "pre_binding_audit": root / "pre.json",
            "post_binding_audit": staging / "formal-binding-post-audit.json",
        }
        plan = {
            "child_command_tokens": ["python", "formal_abba.py"],
            "cwd": str(paths["repo"]),
            "exclusive_command_tokens": ["python", "exclusive_run.py"],
            "finalizer_command_tokens": ["python", "finalize_abba.py"],
            "label": "EXP-JAC-003-development-abba",
        }
        authority = {
            "amendment_commit": "a" * 40,
            "amendment_sha256": "a" * 64,
            "checker_commit": "b" * 40,
            "checker_sha256": "b" * 64,
        }
        frozen = {
            "head_commit": "h" * 40,
            "locked_file_count": 58,
            "locked_file_hash_mismatch_count": 0,
            "source_commit": "s" * 40,
            "source_lock_sha256": "l" * 64,
        }
        amendment = {
            "execution_plan": {
                "abba_sequence": [
                    "K0-DENSE-PUBLIC",
                    "K1-CACHED-ROUTED",
                    "K1-CACHED-ROUTED",
                    "K0-DENSE-PUBLIC",
                ]
            },
            "frozen_execution": {
                "head_commit": frozen["head_commit"],
                "julia_manifest_sha256": "j" * 64,
            },
            "official_inputs": {
                "manifest": {"sha256": "m" * 64},
                "candidate": {"uncompressed_sha256": "c" * 64},
            },
        }
        pre = {
            "authority": authority,
            "command_plan": plan,
            "frozen_binding": frozen,
            "outcome_data_inspected": False,
            "outcome_payload_files_opened": False,
            "passed": True,
            "phase": "pre",
            "schema_version": guard.AUDIT_SCHEMA,
        }
        outer = {
            "child_pid": 101,
            "command": plan["child_command_tokens"],
            "cwd": plan["cwd"],
            "ended_at_utc": "2026-07-10T00:10:00Z",
            "error": None,
            "exit_code": 0,
            "label": plan["label"],
            "outcome": "completed",
            "schema": guard.OUTER_AUDIT_SCHEMA,
            "started_at_utc": "2026-07-10T00:00:00Z",
        }
        pids = [201, 202, 203, 204]
        capture = {
            "candidate_input_uncompressed_sha256": "c" * 64,
            "capture_complete": True,
            "child_exit_codes": [0, 0, 0, 0],
            "child_pids": pids,
            "experiment_id": "EXP-JAC-003",
            "fresh_process_count": 4,
            "fresh_writable_depot_count": 4,
            "input_manifest_sha256": "m" * 64,
            "julia_manifest_sha256": "j" * 64,
            "lock_commit": frozen["head_commit"],
            "outcomes_inspected_by_orchestrator": False,
            "schema_version": guard.CAPTURE_SCHEMA,
            "sequence": amendment["execution_plan"]["abba_sequence"],
            "segments": [
                {
                    "child_pid": pids[index],
                    "exit_code": 0,
                    "slot": index,
                    "trace_path": f"segments/{index}.json",
                    "variant": amendment["execution_plan"]["abba_sequence"][index],
                }
                for index in range(4)
            ],
            "source_lock_sha256": frozen["source_lock_sha256"],
        }
        host = {
            "all_formal_pids_ended": True,
            "formal_outer_pid": 101,
            "formal_segment_pids": pids,
            "host_contention_event_count": 0,
            "label": plan["label"],
            "lease_loss_count": 0,
            "observation_ended_at_utc": "2026-07-10T00:10:01Z",
            "observation_started_at_utc": "2026-07-09T23:59:59Z",
            "outcomes_inspected": False,
            "schema_version": guard.HOST_SCHEMA,
            "template_only": False,
        }
        source = {
            "formal_binding_amendment_sha256": authority["amendment_sha256"],
            "formal_binding_checker_sha256": authority["checker_sha256"],
            "formal_binding_pre_audit_sha256": "p" * 64,
            "head_commit": frozen["head_commit"],
            "input_match": True,
            "manifest_match": True,
            "outcomes_inspected": False,
            "schema_version": guard.SOURCE_OBSERVATION_SCHEMA,
            "source_hash_mismatch_count": 0,
            "source_lock_sha256": frozen["source_lock_sha256"],
            "template_only": False,
        }
        documents = {
            "pre-binding audit": pre,
            "outer audit": outer,
            "capture metadata": capture,
            "host observation": host,
            "source observation": source,
        }
        return {
            "amendment": amendment,
            "authority": authority,
            "documents": documents,
            "frozen": frozen,
            "paths": paths,
            "plan": plan,
        }

    def _run_post(
        self, fixture: dict[str, object]
    ) -> tuple[dict[str, object], list[str]]:
        labels: list[str] = []

        def read_json(_path: Path, label: str) -> dict[str, object]:
            labels.append(label)
            return copy.deepcopy(fixture["documents"][label])  # type: ignore[index]

        with (
            mock.patch.object(
                guard,
                "_load_amendment",
                return_value=(Path("amendment.json"), fixture["amendment"], "a" * 64),
            ),
            mock.patch.object(
                guard, "_verify_checker_authority", return_value=fixture["authority"]
            ),
            mock.patch.object(guard, "_expected_paths", return_value=fixture["paths"]),
            mock.patch.object(
                guard, "_verify_frozen_repository", return_value=fixture["frozen"]
            ),
            mock.patch.object(guard, "_command_plan", return_value=fixture["plan"]),
            mock.patch.object(
                guard, "_absolute_plain_path", side_effect=lambda path, **_: Path(path)
            ),
            mock.patch.object(guard, "_sha256_file", return_value="p" * 64),
            mock.patch.object(guard, "_read_json", side_effect=read_json),
        ):
            result = guard.build_post_audit(
                Path("amendment.json"),
                fixture["paths"]["pre_binding_audit"],  # type: ignore[index]
            )
        return result, labels

    def test_post_guard_reads_metadata_but_no_segment_trace(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            result, labels = self._run_post(self._fixture(Path(raw)))
        self.assertTrue(result["passed"])
        self.assertEqual(
            labels,
            [
                "pre-binding audit",
                "outer audit",
                "capture metadata",
                "host observation",
                "source observation",
            ],
        )
        self.assertTrue(result["segment_trace_files_opened"] is False)

    def test_post_guard_requires_explicit_input_and_manifest_match(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            fixture = self._fixture(Path(raw))
            fixture["documents"]["source observation"]["input_match"] = False  # type: ignore[index]
            with self.assertRaises(guard.BindingError):
                self._run_post(fixture)

    def test_post_guard_rejects_duplicate_or_changed_child_tokens(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            fixture = self._fixture(Path(raw))
            fixture["documents"]["outer audit"]["command"] = [  # type: ignore[index]
                *fixture["plan"]["child_command_tokens"],  # type: ignore[index]
                "--truth",
                "replacement.gz",
            ]
            with self.assertRaises(guard.BindingError):
                self._run_post(fixture)


if __name__ == "__main__":
    unittest.main()
