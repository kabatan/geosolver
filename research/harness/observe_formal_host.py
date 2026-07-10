"""Independent, outcome-blind host observer for formal performance runs.

This process never launches or wraps the formal runner.  On Windows it keeps a
single low-overhead PowerShell snapshot child alive and observes the advisory
lease, its owner process tree, and final audit metadata.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Sequence

try:
    import msvcrt
except ImportError:  # pragma: no cover - exercised only by non-Windows CI
    msvcrt = None  # type: ignore[assignment]


READY_SCHEMA = "geotarget.formal-host-ready/v1"
OUTER_SCHEMA = "geotarget.formal-performance-run/v1"
CAPTURE_SCHEMA = "exp-jac-003-formal-abba-capture/v1"

FORBIDDEN_NAMES = {
    "julia",
    "juliaup",
    "python",
    "pythonw",
    "py",
    "cl",
    "clang",
    "clang++",
    "cc1",
    "cc1plus",
    "gcc",
    "g++",
    "ld",
    "link",
    "lld",
    "rustc",
    "cargo",
    "cmake",
    "ninja",
    "make",
    "msbuild",
    "dotnet",
    "csc",
    "javac",
    "gradle",
    "mvn",
    "hyperfine",
    "benchmark",
    "conda",
    "mamba",
    "micromamba",
    "pip",
    "pip3",
    "uv",
    "poetry",
    "npm",
    "npx",
    "pnpm",
    "yarn",
    "bun",
}

SUSPICIOUS_NEW_NAMES = {"cmd", "node"}

_SNAPSHOT_SCRIPT = r"""
$ErrorActionPreference = 'Stop'
$interval = __INTERVAL_MILLISECONDS__
$frequency = [Diagnostics.Stopwatch]::Frequency
while ($true) {
  $rows = [Collections.Generic.List[object]]::new()
  foreach ($p in [Diagnostics.Process]::GetProcesses()) {
    try {
      $parentId = 0
      $startTicks = 0
      $cpu = 0
      $workingSet = 0
      try {
        $parent = $p.Parent
        if ($null -ne $parent) { $parentId = [int]$parent.Id; $parent.Dispose() }
      } catch {}
      try { $startTicks = [int64]$p.StartTime.ToUniversalTime().Ticks } catch {}
      try { $cpu = [int64]$p.TotalProcessorTime.Ticks } catch {}
      try { $workingSet = [int64]$p.WorkingSet64 } catch {}
      $rows.Add([ordered]@{
        pid = [int]$p.Id
        parent_pid = $parentId
        name = [string]$p.ProcessName
        start_ticks = $startTicks
        cpu_100ns = $cpu
        working_set_bytes = $workingSet
      })
    } catch {} finally { $p.Dispose() }
  }
  $doc = [ordered]@{
    observed_at_utc = [DateTime]::UtcNow.ToString(
      "yyyy-MM-dd'T'HH:mm:ss.ffffff'Z'",
      [Globalization.CultureInfo]::InvariantCulture)
    monotonic_ticks = [Diagnostics.Stopwatch]::GetTimestamp()
    monotonic_frequency = $frequency
    processes = $rows
  }
  [Console]::Out.WriteLine(($doc | ConvertTo-Json -Compress -Depth 3))
  [Console]::Out.Flush()
  Start-Sleep -Milliseconds $interval
}
"""


class ObservationError(RuntimeError):
    """The observer cannot support a valid host claim."""


def _utc_now() -> str:
    return datetime.now(UTC).isoformat(timespec="microseconds").replace("+00:00", "Z")


def _parse_utc(value: object) -> datetime:
    if not isinstance(value, str):
        raise ObservationError("UTC timestamp must be a string")
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ObservationError("UTC timestamp must include a timezone")
    return parsed.astimezone(UTC)


def write_json_exclusive(path: Path, document: dict[str, Any]) -> None:
    """Write one fsynced JSON receipt without replacing an existing path."""

    path = path.expanduser().resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = (json.dumps(document, indent=2, sort_keys=True) + "\n").encode()
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
    except BaseException:
        path.unlink(missing_ok=True)
        raise


@dataclass(frozen=True)
class ProcessRecord:
    pid: int
    parent_pid: int
    name: str
    start_ticks: int
    cpu_100ns: int
    working_set_bytes: int

    @property
    def identity(self) -> tuple[int, int]:
        return self.pid, self.start_ticks


@dataclass(frozen=True)
class Inventory:
    observed_at_utc: str
    monotonic_ticks: int
    monotonic_frequency: int
    processes: tuple[ProcessRecord, ...]

    @classmethod
    def parse(cls, raw: bytes) -> "Inventory":
        value = json.loads(raw)
        rows = tuple(ProcessRecord(**row) for row in value["processes"])
        return cls(
            observed_at_utc=value["observed_at_utc"],
            monotonic_ticks=int(value["monotonic_ticks"]),
            monotonic_frequency=int(value["monotonic_frequency"]),
            processes=rows,
        )

    def by_pid(self) -> dict[int, ProcessRecord]:
        return {row.pid: row for row in self.processes}


def descendant_pids(inventory: Inventory, root_pid: int | None) -> set[int]:
    if root_pid is None:
        return set()
    allowed = {root_pid}
    changed = True
    while changed:
        changed = False
        for row in inventory.processes:
            if row.parent_pid in allowed and row.pid not in allowed:
                allowed.add(row.pid)
                changed = True
    return allowed


@dataclass(frozen=True)
class LeaseView:
    label: str | None
    pid: int | None
    state: str | None
    held: bool | None


def read_lease(path: Path) -> LeaseView:
    if msvcrt is None:
        return LeaseView(None, None, None, None)
    if not path.exists():
        return LeaseView(None, None, None, False)
    try:
        with path.open("rb") as handle:
            handle.seek(1)  # byte zero is the locked lease byte
            payload = handle.read()
        owner = json.loads(payload) if payload else {}
    except (OSError, json.JSONDecodeError):
        return LeaseView(None, None, None, None)
    held: bool | None
    try:
        with path.open("r+b", buffering=0) as handle:
            handle.seek(0)
            try:
                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            except OSError:
                held = True
            else:
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
                held = False
    except OSError:
        held = None
    pid = owner.get("pid")
    return LeaseView(
        owner.get("label"),
        pid if isinstance(pid, int) and not isinstance(pid, bool) else None,
        owner.get("state"),
        held,
    )


class LeaseTracker:
    def __init__(self, label: str) -> None:
        self.label = label
        self.phase = "waiting"
        self.owner_pid: int | None = None
        self.loss_events: list[str] = []

    def _loss(self, reason: str) -> None:
        if not self.loss_events or self.loss_events[-1] != reason:
            self.loss_events.append(reason)

    def observe(self, lease: LeaseView, *, audit_exists: bool) -> None:
        exact = lease.label == self.label and lease.pid is not None
        if self.phase == "waiting":
            if exact and lease.state == "running" and lease.held is True:
                self.owner_pid = lease.pid
                self.phase = "active"
            elif lease.state == "running":
                self._loss("unexpected lease owner before activation")
            return
        if self.phase == "released":
            if lease.state == "running":
                self._loss("lease reacquired after release")
            return
        same = exact and lease.pid == self.owner_pid
        if same and lease.state == "running" and lease.held is True:
            return
        if same and lease.state == "released" and lease.held is False and audit_exists:
            self.phase = "released"
            return
        if same and lease.state == "released" and lease.held is True:
            return  # owner metadata is written immediately before unlock
        self._loss("lease label, PID, state or byte lock was lost")


class ContentionTracker:
    def __init__(
        self,
        *,
        own_pids: set[int],
        cpu_heavy_cores: float,
        memory_heavy_bytes: int,
        memory_growth_bytes: int,
        max_poll_gap_seconds: float,
    ) -> None:
        self.own_pids = own_pids
        self.cpu_heavy_cores = cpu_heavy_cores
        self.memory_heavy_bytes = memory_heavy_bytes
        self.memory_growth_bytes = memory_growth_bytes
        self.max_poll_gap_seconds = max_poll_gap_seconds
        self.previous: Inventory | None = None
        self.events: dict[str, dict[str, Any]] = {}
        self.poll_gap_max_seconds = 0.0

    def _event(self, key: str, **values: Any) -> None:
        self.events.setdefault(key, values)

    def observe(self, inventory: Inventory, allowed_tree: set[int]) -> None:
        previous = self.previous
        gap = 0.0
        old: dict[tuple[int, int], ProcessRecord] = {}
        if previous is not None:
            if inventory.monotonic_frequency != previous.monotonic_frequency:
                self._event("monitor:frequency", category="monitor_failure")
            else:
                gap = (inventory.monotonic_ticks - previous.monotonic_ticks) / float(
                    inventory.monotonic_frequency
                )
                self.poll_gap_max_seconds = max(self.poll_gap_max_seconds, gap)
                if gap <= 0 or gap > self.max_poll_gap_seconds:
                    self._event(
                        "monitor:poll-gap",
                        category="poll_gap",
                        seconds=gap,
                    )
            old = {row.identity: row for row in previous.processes}
        allowed = allowed_tree | self.own_pids
        for row in inventory.processes:
            if row.pid in allowed:
                continue
            name = row.name.lower().removesuffix(".exe")
            reason: str | None = None
            prior = old.get(row.identity)
            if name in FORBIDDEN_NAMES:
                reason = "forbidden process class"
            elif prior is None and previous is not None and name in SUSPICIOUS_NEW_NAMES:
                reason = "new ambiguous build or package-manager host"
            elif row.working_set_bytes >= self.memory_heavy_bytes:
                reason = "memory-heavy process"
            if prior is not None:
                growth = row.working_set_bytes - prior.working_set_bytes
                if growth >= self.memory_growth_bytes:
                    reason = "memory-growth process"
                if gap > 0:
                    cpu = (row.cpu_100ns - prior.cpu_100ns) / 10_000_000 / gap
                    if cpu >= self.cpu_heavy_cores:
                        reason = "CPU-heavy process"
            if reason:
                self._event(
                    f"process:{row.pid}:{row.start_ticks}",
                    category="host_process",
                    name=row.name,
                    pid=row.pid,
                    reason=reason,
                )
        self.previous = inventory


def validate_formal_metadata(
    *,
    label: str,
    outer: dict[str, Any],
    capture: dict[str, Any],
    observation_start: str,
    observation_end: str,
    capture_schema: str = CAPTURE_SCHEMA,
    segment_count: int = 4,
) -> tuple[int, list[int]]:
    if outer.get("schema") != OUTER_SCHEMA or outer.get("label") != label:
        raise ObservationError("outer audit schema or label drift")
    if capture.get("schema_version") != capture_schema:
        raise ObservationError("capture schema drift")
    outer_pid = outer.get("child_pid")
    segment_pids = capture.get("child_pids")
    if not isinstance(outer_pid, int) or isinstance(outer_pid, bool) or outer_pid <= 0:
        raise ObservationError("invalid formal outer PID")
    if (
        not isinstance(segment_pids, list)
        or len(segment_pids) != segment_count
        or len(set(segment_pids)) != segment_count
        or any(not isinstance(pid, int) or isinstance(pid, bool) or pid <= 0 for pid in segment_pids)
    ):
        raise ObservationError(
            f"capture must bind {segment_count} unique segment PIDs"
        )
    if _parse_utc(observation_start) > _parse_utc(outer.get("started_at_utc")):
        raise ObservationError("observation started after outer audit")
    if _parse_utc(observation_end) < _parse_utc(outer.get("ended_at_utc")):
        raise ObservationError("observation ended before outer audit")
    return outer_pid, segment_pids


class PowerShellInventory:
    def __init__(self, executable: str, poll_seconds: float) -> None:
        script = _SNAPSHOT_SCRIPT.replace(
            "__INTERVAL_MILLISECONDS__", str(max(100, round(poll_seconds * 1000)))
        )
        encoded = script.encode("utf-16-le")
        import base64

        command = [
            executable,
            "-NoLogo",
            "-NoProfile",
            "-NonInteractive",
            "-EncodedCommand",
            base64.b64encode(encoded).decode("ascii"),
        ]
        self.process = subprocess.Popen(
            command,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        )

    def next(self) -> tuple[bytes, Inventory]:
        assert self.process.stdout is not None
        raw = self.process.stdout.readline()
        if not raw:
            raise ObservationError("inventory child ended")
        try:
            return raw, Inventory.parse(raw)
        except (KeyError, TypeError, ValueError, json.JSONDecodeError) as error:
            raise ObservationError(f"invalid inventory stream: {error}") from error

    def close(self) -> None:
        if self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait()


def _load_object(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_bytes())
    if not isinstance(value, dict):
        raise ObservationError(f"JSON object required: {path}")
    return value


def run_observer(arguments: argparse.Namespace) -> int:
    output = arguments.output.resolve()
    ready = arguments.ready.resolve()
    if output.exists() or ready.exists():
        raise ObservationError("output and ready receipt must not exist")
    powershell = arguments.powershell or shutil.which("pwsh") or shutil.which("powershell")
    if os.name != "nt" or powershell is None:
        raise ObservationError("the standard host inventory backend requires Windows PowerShell")
    worker = PowerShellInventory(powershell, arguments.poll_seconds)
    digest = hashlib.sha256()
    sample_count = 0
    formal_seen: dict[int, set[int]] = {}
    failures: list[str] = []
    outer: dict[str, Any] | None = None
    capture: dict[str, Any] | None = None
    outer_pid = 0
    segment_pids = [0, 0, 0, 0]
    started = ""
    ended = ""
    all_ended = False
    try:
        raw, first = worker.next()
        digest.update(raw)
        sample_count += 1
        contention = ContentionTracker(
            own_pids={os.getpid(), worker.process.pid},
            cpu_heavy_cores=arguments.cpu_heavy_cores,
            memory_heavy_bytes=arguments.memory_heavy_bytes,
            memory_growth_bytes=arguments.memory_growth_bytes,
            max_poll_gap_seconds=arguments.max_poll_gap_seconds,
        )
        contention.observe(first, set())
        if contention.events:
            raise ObservationError("host baseline contains forbidden or heavy work")
        started = _utc_now()
        write_json_exclusive(
            ready,
            {
                "schema_version": READY_SCHEMA,
                "label": arguments.label,
                "observer_pid": os.getpid(),
                "inventory_child_pid": worker.process.pid,
                "observation_started_at_utc": started,
                "outcomes_inspected": False,
                "ready": True,
            },
        )
        print(f"HOST-OBSERVER READY label={arguments.label} started={started}", flush=True)
        lease_tracker = LeaseTracker(arguments.label)
        raw, inventory = worker.next()
        digest.update(raw)
        sample_count += 1
        deadline = time.monotonic() + arguments.timeout_seconds
        while True:
            lease = read_lease(arguments.lock.resolve())
            lease_tracker.observe(lease, audit_exists=arguments.outer_audit.exists())
            allowed = descendant_pids(inventory, lease_tracker.owner_pid)
            contention.observe(inventory, allowed)
            for row in inventory.processes:
                if row.pid in allowed:
                    formal_seen.setdefault(row.pid, set()).add(row.start_ticks)

            if outer is None and arguments.outer_audit.exists():
                try:
                    outer = _load_object(arguments.outer_audit.resolve())
                except (OSError, json.JSONDecodeError, ObservationError) as error:
                    failures.append(f"outer audit: {error}")
            if capture is None and arguments.capture.exists():
                try:
                    capture = _load_object(arguments.capture.resolve())
                except (OSError, json.JSONDecodeError, ObservationError) as error:
                    failures.append(f"capture metadata: {error}")

            if outer is not None and capture is not None:
                try:
                    tentative_end = _utc_now()
                    outer_pid, segment_pids = validate_formal_metadata(
                        label=arguments.label,
                        outer=outer,
                        capture=capture,
                        observation_start=started,
                        observation_end=tentative_end,
                        capture_schema=arguments.capture_schema,
                        segment_count=arguments.segment_count,
                    )
                    audit_runner = outer.get("runner_pid")
                    if audit_runner != lease_tracker.owner_pid:
                        raise ObservationError("outer audit runner/lease PID mismatch")
                    required = [outer_pid, *segment_pids]
                    if any(pid not in formal_seen for pid in required):
                        raise ObservationError("a formal PID was not observed live")
                    current = inventory.by_pid()
                    identities_live = any(
                        pid in current
                        and current[pid].start_ticks in formal_seen[pid]
                        for pid in required
                    )
                    runner_live = lease_tracker.owner_pid in current
                    if lease_tracker.phase == "released" and not identities_live and not runner_live:
                        ended = tentative_end
                        all_ended = True
                        break
                except ObservationError as error:
                    if str(error) not in failures:
                        failures.append(str(error))
                    if lease_tracker.phase == "released":
                        ended = _utc_now()
                        break
            elif outer is not None and outer.get("outcome") != "completed":
                failures.append("outer runner did not complete; capture unavailable")
                if lease_tracker.phase == "released":
                    ended = _utc_now()
                    break

            if time.monotonic() >= deadline:
                failures.append("observer timeout")
                ended = _utc_now()
                break
            try:
                raw, inventory = worker.next()
            except ObservationError as error:
                failures.append(str(error))
                ended = _utc_now()
                break
            else:
                digest.update(raw)
                sample_count += 1

        for index, reason in enumerate(failures):
            contention._event(
                f"monitor:failure:{index}", category="monitor_failure", reason=reason
            )
        document = {
            "schema_version": arguments.schema_version,
            "label": arguments.label,
            "observer": arguments.observer,
            "observation_started_at_utc": started,
            "observation_ended_at_utc": ended or _utc_now(),
            "formal_outer_pid": outer_pid,
            "formal_segment_pids": segment_pids,
            "host_contention_event_count": len(contention.events),
            "lease_loss_count": len(lease_tracker.loss_events),
            "all_formal_pids_ended": all_ended,
            "excluded_heavy_work": [
                "non-formal Julia and Python processes",
                "non-formal compiler, benchmark and package-manager processes",
                "non-formal CPU-heavy and memory-heavy processes",
            ],
            "method": (
                "Independent standard-library Python observer with one persistent "
                "PowerShell process-inventory child; periodic PID/parent/CPU/memory "
                "snapshots plus advisory-owner and byte-range-lock checks."
            ),
            "outcomes_inspected": False,
            "template_only": False,
            "poll_gap_max_seconds": contention.poll_gap_max_seconds,
            "raw_process_inventory_sha256": digest.hexdigest(),
            "raw_process_inventory_sample_count": sample_count,
            "contention_events": list(contention.events.values()),
            "lease_loss_events": lease_tracker.loss_events,
            "monitor_failures": failures,
            "inventory_child_pid": worker.process.pid,
        }
        write_json_exclusive(output, document)
        return 0 if not failures and not contention.events and not lease_tracker.loss_events else 2
    finally:
        worker.close()


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Observe a formal runner independently; never launches the runner."
    )
    parser.add_argument("--schema-version", required=True)
    parser.add_argument("--capture-schema", required=True)
    parser.add_argument("--segment-count", type=int, default=4)
    parser.add_argument("--label", required=True)
    parser.add_argument("--observer", required=True)
    parser.add_argument("--outer-audit", required=True, type=Path)
    parser.add_argument("--capture", required=True, type=Path)
    parser.add_argument("--lock", required=True, type=Path)
    parser.add_argument("--ready", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--powershell")
    parser.add_argument("--poll-seconds", type=float, default=2.0)
    parser.add_argument("--max-poll-gap-seconds", type=float, default=5.0)
    parser.add_argument("--cpu-heavy-cores", type=float, default=0.25)
    parser.add_argument("--memory-heavy-bytes", type=int, default=2_147_483_648)
    parser.add_argument("--memory-growth-bytes", type=int, default=536_870_912)
    parser.add_argument("--timeout-seconds", type=float, default=86_400.0)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    arguments = _parser().parse_args(argv)
    positive = (
        arguments.poll_seconds,
        arguments.max_poll_gap_seconds,
        arguments.cpu_heavy_cores,
        arguments.memory_heavy_bytes,
        arguments.memory_growth_bytes,
        arguments.timeout_seconds,
        arguments.segment_count,
    )
    if any(not isinstance(value, int | float) or not math.isfinite(value) or value <= 0 for value in positive):
        raise SystemExit("observer intervals and thresholds must be finite and positive")
    try:
        return run_observer(arguments)
    except ObservationError as error:
        print(f"HOST-OBSERVER ERROR: {error}", file=sys.stderr, flush=True)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
