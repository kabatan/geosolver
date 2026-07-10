from __future__ import annotations

import copy
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

import verify_terminal_closure as verifier


REPO = Path(__file__).resolve().parents[4]


def _metadata(relative: str) -> dict[str, object]:
    return json.loads(REPO.joinpath(*relative.split("/")).read_bytes())


class TerminalClosureTests(unittest.TestCase):
    def test_repository_closure_passes(self) -> None:
        report = verifier.verify(REPO)
        self.assertEqual(report["status"], "passed")
        self.assertEqual(report["artifact_count"], 22)
        self.assertEqual(report["frozen_blob_count"], 11)
        self.assertEqual(report["no_retry_authority_count"], 2)
        self.assertIs(report["numerical_payloads_parsed"], False)

    def test_checksum_covers_exact_terminal_artifact_set(self) -> None:
        checksum = _metadata(verifier.CHECKSUM_PATH)
        artifacts = checksum["artifacts"]
        self.assertIsInstance(artifacts, list)
        paths = {row["path"] for row in artifacts}
        self.assertEqual(len(paths), 22)
        self.assertNotIn(verifier.CHECKSUM_PATH, paths)
        self.assertEqual(
            sum(row["role"] == "raw-partial" for row in artifacts),
            14,
        )

    def test_terminal_state_rejects_efficacy_claim(self) -> None:
        closure = _metadata(verifier.CLOSURE_PATH)
        summary = _metadata(verifier.SUMMARY_PATH)
        changed_closure = copy.deepcopy(closure)
        changed_summary = copy.deepcopy(summary)
        changed_closure["decision"]["efficacy_conclusion"] = "positive"
        changed_summary["decision"]["efficacy_conclusion"] = "positive"
        with self.assertRaisesRegex(
            verifier.ClosureVerificationError, "decision drift"
        ):
            verifier._verify_terminal_state(changed_closure, changed_summary)

    def test_terminal_state_rejects_retry_authorization(self) -> None:
        closure = _metadata(verifier.CLOSURE_PATH)
        summary = _metadata(verifier.SUMMARY_PATH)
        changed_closure = copy.deepcopy(closure)
        changed_summary = copy.deepcopy(summary)
        changed_closure["formal_run"]["formal_retry_authorized"] = True
        changed_summary["formal_run"]["formal_retry_authorized"] = True
        with self.assertRaisesRegex(
            verifier.ClosureVerificationError, "formal state drift"
        ):
            verifier._verify_terminal_state(changed_closure, changed_summary)

    def test_artifact_hashing_does_not_decode_payloads(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory).resolve()
            roles = {
                **verifier.EXPECTED_BINDING_ROLES,
                **{
                    f"{verifier.RAW_ROOT}/{relative}": "raw-partial"
                    for relative in verifier.EXPECTED_RAW_RELATIVE_PATHS
                },
                verifier.CLOSURE_PATH: "failure-closure",
                verifier.SUMMARY_PATH: "terminal-summary",
            }
            rows: list[dict[str, object]] = []
            bindings: dict[str, tuple[str, int]] = {}
            for path, role in sorted(roles.items()):
                payload = f"definitely-not-json::{path}".encode()
                target = repo.joinpath(*path.split("/"))
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(payload)
                digest = hashlib.sha256(payload).hexdigest()
                rows.append(
                    {
                        "path": path,
                        "role": role,
                        "sha256": digest,
                        "size": len(payload),
                    }
                )
                if path not in {verifier.CLOSURE_PATH, verifier.SUMMARY_PATH}:
                    bindings[path] = (digest, len(payload))
            absent = sorted(verifier.EXPECTED_ABSENT_PATHS)
            checksum = {
                "experiment_id": "EXP-JAC-003",
                "hash_algorithm": "sha256",
                "self_included": False,
                "required_absent_paths": absent,
                "artifact_count": len(rows),
                "artifacts": rows,
            }
            count = verifier._verify_artifact_index(repo, checksum, bindings, absent)
            self.assertEqual(count, 22)

    def test_required_absence_fails_on_opaque_existing_file(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory).resolve()
            relative = f"{verifier.RAW_ROOT}/capture.json"
            target = repo.joinpath(*relative.split("/"))
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(b"not-json-and-must-not-be-decoded")
            absent = [relative]
            absent.extend(sorted(verifier.EXPECTED_ABSENT_PATHS - {relative}))
            with self.assertRaisesRegex(
                verifier.ClosureVerificationError, "required-absent path exists"
            ):
                verifier._verify_absence(repo, absent)

    def test_repository_escape_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(
                verifier.ClosureVerificationError, "escaping artifact path"
            ):
                verifier._relative_file(Path(directory).resolve(), "../escape")


if __name__ == "__main__":
    unittest.main()
