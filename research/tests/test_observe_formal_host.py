from __future__ import annotations

import json
import os
import tempfile
import unittest
from argparse import Namespace
from pathlib import Path
from types import SimpleNamespace

from research.harness.observe_formal_host import (
    ContentionTracker,
    Inventory,
    LeaseTracker,
    LeaseView,
    ObservationError,
    ProcessRecord,
    ProcessStartEvent,
    _LineReader,
    descendant_pids,
    extend_formal_identities,
    observation_bindings,
    read_lease,
    remaining_before_deadline,
    validate_formal_metadata,
    validate_pre_ready,
    write_json_exclusive,
)
from research.harness.exclusive_run import FormalRunLease


def inventory(
    tick: int,
    *rows: ProcessRecord,
    events: tuple[ProcessStartEvent, ...] = (),
    idle: int = 0,
    kernel: int = 0,
    user: int = 0,
) -> Inventory:
    return Inventory(
        "2026-07-11T00:00:00.000000Z",
        tick,
        10,
        rows,
        events,
        idle,
        kernel,
        user,
    )


def process(
    pid: int,
    parent: int,
    name: str,
    *,
    start: int | None = None,
    cpu: int = 0,
    memory: int = 1,
) -> ProcessRecord:
    return ProcessRecord(pid, parent, name, start or pid, cpu, memory)


class ProcessObservationTests(unittest.TestCase):
    def test_descendant_tree_is_allowed_but_external_python_is_contention(self) -> None:
        snap = inventory(
            10,
            process(10, 1, "python"),
            process(11, 10, "python"),
            process(12, 11, "julia"),
            process(99, 1, "python"),
        )
        allowed = descendant_pids(snap, 10)
        self.assertEqual(allowed, {10, 11, 12})
        tracker = ContentionTracker(
            own_pids=set(),
            cpu_heavy_cores=0.25,
            memory_heavy_bytes=1000,
            memory_growth_bytes=100,
            max_poll_gap_seconds=2,
            unexplained_cpu_cores=100,
        )
        identities = {row.identity for row in snap.processes if row.pid in allowed}
        tracker.observe(snap, identities)
        self.assertEqual(len(tracker.events), 1)
        self.assertEqual(next(iter(tracker.events.values()))["pid"], 99)

    def test_cpu_memory_and_poll_gap_fail_closed(self) -> None:
        tracker = ContentionTracker(
            own_pids=set(),
            cpu_heavy_cores=0.25,
            memory_heavy_bytes=1000,
            memory_growth_bytes=100,
            max_poll_gap_seconds=2,
            unexplained_cpu_cores=100,
        )
        tracker.observe(inventory(0, process(7, 1, "ordinary", cpu=0, memory=1)), set())
        tracker.observe(
            inventory(30, process(7, 1, "ordinary", cpu=10_000_000, memory=200)),
            set(),
        )
        categories = {event["category"] for event in tracker.events.values()}
        self.assertIn("poll_gap", categories)
        self.assertIn("host_process", categories)

    def test_orphan_descendant_survives_and_pid_reuse_is_not_laundered(self) -> None:
        known: set[tuple[int, int]] = set()
        first = inventory(
            1,
            process(10, 1, "python", start=100),
            process(11, 10, "python", start=110),
            process(12, 11, "julia", start=120),
        )
        extend_formal_identities(first, 10, known)
        second = inventory(
            2,
            process(11, 1, "python", start=999),
            process(12, 1, "julia", start=120),
            process(13, 12, "julia", start=130),
        )
        extend_formal_identities(second, 10, known)
        self.assertIn((12, 120), known)
        self.assertIn((13, 130), known)
        self.assertNotIn((11, 999), known)

    def test_short_process_event_and_unexplained_cpu_fail_closed(self) -> None:
        tracker = ContentionTracker(
            own_pids=set(),
            cpu_heavy_cores=100,
            memory_heavy_bytes=10**12,
            memory_growth_bytes=10**12,
            max_poll_gap_seconds=2,
            unexplained_cpu_cores=1.5,
        )
        tracker.observe(inventory(0, idle=0, kernel=0, user=0), set())
        tracker.observe(
            inventory(
                10,
                events=(ProcessStartEvent(77, 1, "python.exe", 700),),
                idle=0,
                kernel=20_000_000,
                user=0,
            ),
            set(),
        )
        categories = {event["category"] for event in tracker.events.values()}
        self.assertIn("process_start", categories)
        self.assertIn("aggregate_cpu", categories)

    def test_valid_and_lost_lease_transitions(self) -> None:
        tracker = LeaseTracker("formal")
        tracker.observe(LeaseView("formal", 10, "running", True), audit_exists=False)
        tracker.observe(LeaseView("formal", 10, "running", True), audit_exists=False)
        tracker.observe(LeaseView("formal", 10, "released", False), audit_exists=True)
        self.assertEqual(tracker.phase, "released")
        self.assertEqual(tracker.loss_events, [])

        lost = LeaseTracker("formal")
        lost.observe(LeaseView("formal", 10, "running", True), audit_exists=False)
        lost.observe(LeaseView("other", 20, "running", True), audit_exists=False)
        self.assertEqual(len(lost.loss_events), 1)

    def test_real_temporary_lease_reports_owner_and_byte_lock(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "formal.lock"
            lease = FormalRunLease("formal", path).acquire()
            try:
                self.assertEqual(
                    read_lease(path),
                    LeaseView("formal", lease.owner["pid"], "running", True),
                )
            finally:
                lease.release()
            self.assertEqual(read_lease(path).state, "released")
            self.assertFalse(read_lease(path).held)

    def test_reader_stall_and_timeout_are_explicit(self) -> None:
        read_fd, write_fd = os.pipe()
        stream = os.fdopen(read_fd, "rb", buffering=0)
        try:
            reader = _LineReader(stream)
            with self.assertRaisesRegex(ObservationError, "stalled"):
                reader.next(0.01)
            with self.assertRaisesRegex(ObservationError, "timeout"):
                remaining_before_deadline(10, 2, now=10)
        finally:
            os.close(write_fd)
            stream.close()

        read_fd, write_fd = os.pipe()
        os.close(write_fd)
        with os.fdopen(read_fd, "rb", buffering=0) as ended_stream:
            ended_reader = _LineReader(ended_stream)
            with self.assertRaisesRegex(ObservationError, "ended"):
                ended_reader.next(1)


class FinalizationTests(unittest.TestCase):
    def test_pre_ready_rejects_existing_artifact_and_held_lease(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            arguments = Namespace(
                output=root / "output",
                ready=root / "ready",
                outer_audit=root / "outer",
                capture=root / "capture",
                lock=root / "lock",
            )
            validate_pre_ready(arguments)
            arguments.outer_audit.write_text("existing")
            with self.assertRaisesRegex(ObservationError, "path already exists"):
                validate_pre_ready(arguments)
            arguments.outer_audit.unlink()
            lease = FormalRunLease("formal", arguments.lock).acquire()
            try:
                with self.assertRaisesRegex(ObservationError, "lease is held"):
                    validate_pre_ready(arguments)
            finally:
                lease.release()

    def test_settings_paths_and_backend_capabilities_are_bound(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            arguments = Namespace(
                schema_version="host/v1",
                capture_schema="capture/v1",
                segment_count=4,
                label="formal",
                observer="independent",
                poll_seconds=2.0,
                max_poll_gap_seconds=5.0,
                cpu_heavy_cores=0.25,
                memory_heavy_bytes=100,
                memory_growth_bytes=50,
                unexplained_cpu_cores=1.0,
                event_within_seconds=0.1,
                backend_stall_seconds=15.0,
                timeout_seconds=100.0,
                lock=root / "lock",
                outer_audit=root / "outer",
                capture=root / "capture",
                ready=root / "ready",
                output=root / "output",
            )
            worker = SimpleNamespace(
                executable=(root / "pwsh.exe").resolve(),
                executable_sha256="a" * 64,
                version="7.5.8",
                script_template_sha256="c" * 64,
                script_sha256="b" * 64,
            )
            capability = Inventory(
                "2026-07-11T00:00:00.000000Z",
                1,
                10,
                (),
                parent_capability=True,
                event_capability=True,
                event_source="event",
                event_within_seconds=0.1,
                capability_probe_pid=9,
            )
            bound = observation_bindings(arguments, worker, capability)
            self.assertEqual(bound["settings"]["timeout_seconds"], 100.0)
            self.assertEqual(bound["paths"]["output"], str((root / "output").resolve()))
            self.assertTrue(bound["backend"]["event_capability"])

    def test_interval_and_four_pids_are_validated(self) -> None:
        outer = {
            "schema": "geotarget.formal-performance-run/v1",
            "label": "formal",
            "child_pid": 10,
            "started_at_utc": "2026-07-11T00:00:01.000000Z",
            "ended_at_utc": "2026-07-11T00:00:09.000000Z",
        }
        capture = {
            "schema_version": "exp-jac-003-formal-abba-capture/v1",
            "child_pids": [11, 12, 13, 14],
        }
        self.assertEqual(
            validate_formal_metadata(
                label="formal",
                outer=outer,
                capture=capture,
                observation_start="2026-07-11T00:00:00.000000Z",
                observation_end="2026-07-11T00:00:10.000000Z",
            ),
            (10, [11, 12, 13, 14]),
        )
        with self.assertRaisesRegex(ObservationError, "started after"):
            validate_formal_metadata(
                label="formal",
                outer=outer,
                capture=capture,
                observation_start="2026-07-11T00:00:02.000000Z",
                observation_end="2026-07-11T00:00:10.000000Z",
            )
        with self.assertRaisesRegex(ObservationError, "ended before"):
            validate_formal_metadata(
                label="formal",
                outer=outer,
                capture=capture,
                observation_start="2026-07-11T00:00:00.000000Z",
                observation_end="2026-07-11T00:00:08.000000Z",
            )
        capture["child_pids"] = [11, 11, 13, 14]
        with self.assertRaisesRegex(ObservationError, "4 unique"):
            validate_formal_metadata(
                label="formal",
                outer=outer,
                capture=capture,
                observation_start="2026-07-11T00:00:00.000000Z",
                observation_end="2026-07-11T00:00:10.000000Z",
            )

    def test_exclusive_output_never_overwrites(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "receipt.json"
            write_json_exclusive(path, {"first": True})
            with self.assertRaises(FileExistsError):
                write_json_exclusive(path, {"first": False})
            self.assertEqual(json.loads(path.read_text()), {"first": True})


if __name__ == "__main__":
    unittest.main()
