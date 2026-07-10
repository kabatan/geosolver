from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from research.harness.observe_formal_host import (
    ContentionTracker,
    Inventory,
    LeaseTracker,
    LeaseView,
    ObservationError,
    ProcessRecord,
    descendant_pids,
    read_lease,
    validate_formal_metadata,
    write_json_exclusive,
)
from research.harness.exclusive_run import FormalRunLease


def inventory(tick: int, *rows: ProcessRecord) -> Inventory:
    return Inventory("2026-07-11T00:00:00.000000Z", tick, 10, rows)


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
        )
        tracker.observe(snap, allowed)
        self.assertEqual(len(tracker.events), 1)
        self.assertEqual(next(iter(tracker.events.values()))["pid"], 99)

    def test_cpu_memory_and_poll_gap_fail_closed(self) -> None:
        tracker = ContentionTracker(
            own_pids=set(),
            cpu_heavy_cores=0.25,
            memory_heavy_bytes=1000,
            memory_growth_bytes=100,
            max_poll_gap_seconds=2,
        )
        tracker.observe(inventory(0, process(7, 1, "ordinary", cpu=0, memory=1)), set())
        tracker.observe(
            inventory(30, process(7, 1, "ordinary", cpu=10_000_000, memory=200)),
            set(),
        )
        categories = {event["category"] for event in tracker.events.values()}
        self.assertIn("poll_gap", categories)
        self.assertIn("host_process", categories)

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
                self.assertEqual(read_lease(path), LeaseView("formal", lease.owner["pid"], "running", True))
            finally:
                lease.release()
            self.assertEqual(read_lease(path).state, "released")
            self.assertFalse(read_lease(path).held)


class FinalizationTests(unittest.TestCase):
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
