#!/usr/bin/env python3.12
"""Generated fail-closed mutation D0 for the candidate-private repair."""

from __future__ import annotations

import argparse
import copy
import json
import os
from pathlib import Path
import stat
import tempfile

import exact_worker_guard as child_guard
import execution_guard as guard
import run_real_gate as real_gate


def _rejected(callback) -> bool:
    try:
        callback()
    except Exception:
        return True
    return False


def _descriptor_fixture():
    isolator = {
        "left": "1",
        "right": "2",
        "multiplicity": 1,
        "real_root_index": 1,
    }
    exact = {
        "exact_target_descriptor": {
            "coefficients_high_to_low": [1, 0, -2],
            "isolating_interval": dict(isolator),
        },
        "target_root_attestation": {
            "claimed_real_root_index": 1,
            "attested_real_root_index": 1,
            "real_root_count": 2,
            "multiplicity": 1,
            "interval_unique": True,
            "index_match": True,
        },
    }
    descriptor = {
        "minimal_polynomial_high_to_low": [1, 0, -2],
        "selected_real_root_index": 1,
        "isolating_interval": dict(isolator),
        "proposal_relation_low_to_high": [-2, 0, 1],
        "confirmation_relation_low_to_high": [-2, 0, 1],
        "target_512": "1.414",
        "target_768": "1.4142",
        "target_1024": "1.41421",
    }
    return descriptor, exact


def _fork_handoff_check(
    lease: guard.FormalRunLease, payload: bytes, *, forge: bool
) -> bool:
    environment, descriptors = lease.child_handoff(payload)
    if forge:
        environment[guard.HANDOFF_KEY] = "0" * 64
    pid = os.fork()
    if pid == 0:
        try:
            os.environ.clear()
            os.environ.update(environment)
            guard.verify_inherited_handoff(payload)
        except Exception:
            os._exit(0 if forge else 11)
        os._exit(12 if forge else 0)
    lease.close_child_token_fd(descriptors)
    _pid, status = os.waitpid(pid, 0)
    return os.waitstatus_to_exitcode(status) == 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    arguments = parser.parse_args()
    checks: dict[str, bool] = {}

    descriptor, exact = _descriptor_fixture()
    checks["valid_minpoly_descriptor_accepts"] = real_gate._strict_descriptor_ready(
        descriptor, exact
    )
    mutations = []
    for name in (
        "reducible",
        "nonsquarefree",
        "nonprimitive",
        "isolator_nonunique",
        "wrong_ordinal",
        "relation_mismatch",
        "exact_descriptor_mismatch",
        "nonfinite_target_lane",
        "boolean_attestation",
        "boolean_exact_isolator",
    ):
        changed_descriptor = copy.deepcopy(descriptor)
        changed_exact = copy.deepcopy(exact)
        if name == "reducible":
            changed_descriptor["minimal_polynomial_high_to_low"] = [1, 0, -1]
        elif name == "nonsquarefree":
            changed_descriptor["minimal_polynomial_high_to_low"] = [1, -2, 1]
        elif name == "nonprimitive":
            changed_descriptor["minimal_polynomial_high_to_low"] = [2, 0, -4]
        elif name == "isolator_nonunique":
            changed_descriptor["isolating_interval"]["left"] = "-2"
        elif name == "wrong_ordinal":
            changed_descriptor["selected_real_root_index"] = 0
        elif name == "relation_mismatch":
            changed_descriptor["proposal_relation_low_to_high"] = [-3, 0, 1]
        elif name == "exact_descriptor_mismatch":
            changed_exact["target_root_attestation"]["attested_real_root_index"] = 0
        elif name == "nonfinite_target_lane":
            changed_descriptor["target_1024"] = "NaN"
        elif name == "boolean_attestation":
            changed_exact["target_root_attestation"]["real_root_count"] = True
        else:
            changed_exact["exact_target_descriptor"]["isolating_interval"][
                "real_root_index"
            ] = True
        mutations.append(
            not real_gate._strict_descriptor_ready(changed_descriptor, changed_exact)
        )
    checks["descriptor_mutations_rejected"] = all(mutations)
    checks["descriptor_mutation_count_is_10"] = len(mutations) == 10

    closure_sha, _worker, closure = real_gate._runtime_closure(
        real_gate.APPROVED_RUNTIME_ROOT
    )
    closure_manifest = {
        "runtime_closure_sha256": closure_sha,
        "runtime_closure": closure,
    }
    checks["runtime_closure_accepts"] = (
        child_guard.verify_runtime_closure(closure_manifest) == closure
    )
    changed_closure = copy.deepcopy(closure_manifest)
    changed_closure["runtime_closure"]["exact_worker"]["sha256"] = "0" * 64
    checks["runtime_closure_mutation_rejected"] = _rejected(
        lambda: child_guard.verify_runtime_closure(changed_closure)
    )

    with tempfile.TemporaryDirectory(prefix="edm-exec-mutation-") as directory:
        root = Path(directory).resolve()
        root.chmod(0o700)
        source = root / "source.bin"
        proposal = root / "proposal.bin"
        guard.atomic_write_0600(root, source, b"source\x00all-bytes\n")
        guard.atomic_write_0600(root, proposal, b"proposal\x00all-bytes\n")
        byte_manifest = {
            "source": {"path": str(source), "sha256": guard.sha256_bytes(source.read_bytes())},
            "ordinary_proposal": {
                "path": str(proposal),
                "sha256": guard.sha256_bytes(proposal.read_bytes()),
            },
        }
        child_guard.verify_attempt_byte_bindings(byte_manifest, root)
        checks["source_proposal_all_bytes_accept"] = True
        with source.open("ab") as stream:
            stream.write(b"X")
        checks["source_one_byte_mutation_rejected"] = _rejected(
            lambda: child_guard.verify_attempt_byte_bindings(byte_manifest, root)
        )
        byte_manifest["source"]["sha256"] = guard.sha256_bytes(source.read_bytes())
        with proposal.open("ab") as stream:
            stream.write(b"Y")
        checks["proposal_one_byte_mutation_rejected"] = _rejected(
            lambda: child_guard.verify_attempt_byte_bindings(byte_manifest, root)
        )

        artifact = root / "artifact.json"
        guard.atomic_write_0600(root, artifact, b"{}\n")
        checks["atomic_artifact_mode_0600"] = (
            stat.S_IMODE(artifact.stat().st_mode) == 0o600
        )
        checks["artifact_parent_escape_rejected"] = _rejected(
            lambda: guard.atomic_write_0600(root, root.parent / "escape", b"bad")
        )
        symlink = root / "symlink.json"
        symlink.symlink_to(artifact)
        checks["artifact_symlink_rejected"] = _rejected(
            lambda: guard.atomic_write_0600(root, symlink, b"bad")
        )
        linked_root = root.parent / (root.name + "-link")
        linked_root.symlink_to(root, target_is_directory=True)
        checks["artifact_symlink_root_rejected"] = _rejected(
            lambda: guard.atomic_write_0600(
                linked_root, linked_root / "escaped.json", b"bad"
            )
        )
        linked_root.unlink()

        old_lock = guard.FORMAL_LOCK_PATH
        private_lock = root / "formal.lock"
        guard.FORMAL_LOCK_PATH = private_lock
        try:
            with guard.FormalRunLease("generated-mutation", private_lock) as lease:
                checks["inherited_lease_proof_accepts"] = _fork_handoff_check(
                    lease, b"authorized-attempt\n", forge=False
                )
                checks["forged_lease_proof_rejected"] = _fork_handoff_check(
                    lease, b"authorized-attempt\n", forge=True
                )
        finally:
            guard.FORMAL_LOCK_PATH = old_lock

        missing_pid = os.fork()
        if missing_pid == 0:
            os.environ.clear()
            try:
                guard.verify_inherited_handoff(b"unauthorized\n")
            except Exception:
                os._exit(0)
            os._exit(1)
        _pid, missing_status = os.waitpid(missing_pid, 0)
        checks["direct_worker_without_proof_rejected"] = (
            os.waitstatus_to_exitcode(missing_status) == 0
        )

        python = str(real_gate.APPROVED_PYTHON)
        def contained(label: str, code: str, timeout: float, rss: int, cap: int):
            return guard.run_contained(
                [python, "-c", code],
                cwd=root,
                environment={"PATH": "/usr/bin:/bin", "LANG": "C.UTF-8"},
                pass_fds=(),
                timeout_seconds=timeout,
                rss_cap_bytes=rss,
                stdout_path=root / f"{label}.stdout",
                stderr_path=root / f"{label}.stderr",
                output_cap_bytes=cap,
            )

        timeout_result = contained(
            "timeout",
            "import subprocess,time; subprocess.Popen(['/bin/sleep','5']); time.sleep(5)",
            0.08,
            1024**3,
            1024**2,
        )
        checks["deadline_terminates_process_group"] = (
            timeout_result.classification == "HARD_DEADLINE_TERMINATED"
        )
        rss_result = contained(
            "rss", "import time; time.sleep(5)", 2.0, 1, 1024**2
        )
        checks["rss_cap_terminates_process_group"] = (
            rss_result.classification == "RSS_CAP_TERMINATED"
        )
        output_result = contained(
            "output", "import os; os.write(1,b'x'*65536)", 2.0, 1024**3, 1024
        )
        checks["output_cap_rejects"] = output_result.classification in {
            "OUTPUT_CAP_TERMINATED",
            "OUTPUT_CAP_POSTEXIT_REJECTED",
        }

    result = {
        "schema_version": "geotarget.edm-exact-execution-mutation-d0/v1",
        "completed": True,
        "passed": all(checks.values()),
        "check_count": len(checks),
        "failed_checks": sorted(name for name, passed in checks.items() if not passed),
        "checks": checks,
        "private_or_truth_rows_read": False,
        "global_formal_lock_acquired": False,
        "authority_pass": False,
        "target_release": False,
    }
    output_root = arguments.output.absolute().parent
    guard.atomic_write_0600(output_root, arguments.output, guard.canonical_json(result))
    print(json.dumps(result, sort_keys=True, separators=(",", ":")))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
