"""Independent, outcome-blind host observer for formal performance runs.

This process never launches or wraps the formal runner.  On Windows it keeps a
single low-overhead PowerShell snapshot child alive and observes the advisory
lease, its owner process tree, and final audit metadata.
"""

from __future__ import annotations

import argparse
import base64
import ctypes
import hashlib
import json
import math
import os
import queue
import shutil
import subprocess
import sys
import threading
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import IO, Any, Sequence

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
OBSERVER_INFRA_NAMES = {"wmiprvse"}


class _FileTime(ctypes.Structure):
    _fields_ = [("low", ctypes.c_uint32), ("high", ctypes.c_uint32)]


def _filetime_value(value: _FileTime) -> int:
    return (value.high << 32) | value.low


def _system_cpu_times() -> tuple[int, int, int]:
    if os.name != "nt":
        raise ObservationError("GetSystemTimes requires Windows")
    idle, kernel, user = _FileTime(), _FileTime(), _FileTime()
    function = ctypes.WinDLL("kernel32", use_last_error=True).GetSystemTimes
    if not function(ctypes.byref(idle), ctypes.byref(kernel), ctypes.byref(user)):
        raise ObservationError(f"GetSystemTimes failed: {ctypes.get_last_error()}")
    return _filetime_value(idle), _filetime_value(kernel), _filetime_value(user)


_SNAPSHOT_SCRIPT = r"""
$ErrorActionPreference = 'Stop'
$interval = __INTERVAL_MILLISECONDS__
$eventWithin = __EVENT_WITHIN_SECONDS__
$observerPid = __OBSERVER_PID__
$frequency = [Diagnostics.Stopwatch]::Frequency
$source = "geotarget-process-start-$PID"
$selfProcess = Get-Process -Id $PID
$parentCapability = ($null -ne $selfProcess.Parent -and $selfProcess.Parent.Id -eq $observerPid)
Add-Type -AssemblyName System.Management
$eventQuery = "SELECT * FROM __InstanceCreationEvent WITHIN $eventWithin " +
  "WHERE TargetInstance ISA 'Win32_Process'"
$watcher = [System.Management.ManagementEventWatcher]::new($eventQuery)
$subscription = Register-ObjectEvent -InputObject $watcher `
  -EventName EventArrived -SourceIdentifier $source
$watcher.Start()

function Read-StartEvents {
  $rows = [Collections.Generic.List[object]]::new()
  foreach ($event in @(Get-Event -SourceIdentifier $source -ErrorAction SilentlyContinue)) {
    try {
      $target = $event.SourceEventArgs.NewEvent['TargetInstance']
      $created = 0
      try {
        $created = [System.Management.ManagementDateTimeConverter]::ToDateTime(
          [string]$target.CreationDate).ToUniversalTime().Ticks
      } catch {}
      $rows.Add([ordered]@{
        pid = [int]$target.ProcessId
        parent_pid = [int]$target.ParentProcessId
        name = [string]$target.Name
        start_ticks = [int64]$created
      })
    } finally {
      Remove-Event -EventIdentifier $event.EventIdentifier -ErrorAction SilentlyContinue
    }
  }
  return $rows
}

$probe = Start-Process -FilePath (Join-Path $PSHOME 'pwsh.exe') `
  -ArgumentList @('-NoLogo','-NoProfile','-NonInteractive','-Command',
    'Start-Sleep -Milliseconds 750') -WindowStyle Hidden -PassThru
$probePid = $probe.Id
$probe.WaitForExit()
Start-Sleep -Milliseconds ([math]::Ceiling($eventWithin * 1000) + 250)
$pendingEvents = @(Read-StartEvents)
$eventCapability = @($pendingEvents | Where-Object {
  $_.pid -eq $probePid -and $_.start_ticks -gt 0 }).Count -eq 1
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
  $events = @($pendingEvents) + @(Read-StartEvents)
  $pendingEvents = @()
  $doc = [ordered]@{
    observed_at_utc = [DateTime]::UtcNow.ToString(
      "yyyy-MM-dd'T'HH:mm:ss.ffffff'Z'",
      [Globalization.CultureInfo]::InvariantCulture)
    monotonic_ticks = [Diagnostics.Stopwatch]::GetTimestamp()
    monotonic_frequency = $frequency
    parent_capability = $parentCapability
    event_capability = $eventCapability
    event_source = "System.Management __InstanceCreationEvent"
    event_within_seconds = $eventWithin
    capability_probe_pid = $probePid
    start_events = $events
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
class ProcessStartEvent:
    pid: int
    parent_pid: int
    name: str
    start_ticks: int

    @property
    def identity(self) -> tuple[int, int]:
        return self.pid, self.start_ticks


@dataclass(frozen=True)
class Inventory:
    observed_at_utc: str
    monotonic_ticks: int
    monotonic_frequency: int
    processes: tuple[ProcessRecord, ...]
    start_events: tuple[ProcessStartEvent, ...] = ()
    system_idle_100ns: int = 0
    system_kernel_100ns: int = 0
    system_user_100ns: int = 0
    parent_capability: bool = False
    event_capability: bool = False
    event_source: str = ""
    event_within_seconds: float = 0.0
    capability_probe_pid: int = 0

    @classmethod
    def parse(cls, raw: bytes) -> "Inventory":
        value = json.loads(raw)
        rows = tuple(ProcessRecord(**row) for row in value["processes"])
        events = tuple(ProcessStartEvent(**row) for row in value["start_events"])
        idle, kernel, user = _system_cpu_times()
        return cls(
            observed_at_utc=value["observed_at_utc"],
            monotonic_ticks=int(value["monotonic_ticks"]),
            monotonic_frequency=int(value["monotonic_frequency"]),
            processes=rows,
            start_events=events,
            system_idle_100ns=idle,
            system_kernel_100ns=kernel,
            system_user_100ns=user,
            parent_capability=value.get("parent_capability") is True,
            event_capability=value.get("event_capability") is True,
            event_source=str(value.get("event_source", "")),
            event_within_seconds=float(value.get("event_within_seconds", 0.0)),
            capability_probe_pid=int(value.get("capability_probe_pid", 0)),
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


def extend_formal_identities(
    inventory: Inventory,
    root_pid: int | None,
    known: set[tuple[int, int]],
) -> set[tuple[int, int]]:
    """Extend a formal tree without laundering PID reuse or orphaning."""

    current = inventory.by_pid()
    formal_pids = {
        pid
        for pid, start in known
        if pid in current and current[pid].start_ticks == start
    }
    if root_pid is not None and root_pid in current:
        formal_pids.add(root_pid)
    changed = True
    while changed:
        changed = False
        for row in inventory.processes:
            if row.parent_pid in formal_pids and row.pid not in formal_pids:
                formal_pids.add(row.pid)
                changed = True
    known.update(row.identity for row in inventory.processes if row.pid in formal_pids)
    pending = list(inventory.start_events)
    while pending:
        next_pending: list[ProcessStartEvent] = []
        changed = False
        formal_event_pids = set(formal_pids)
        for event in pending:
            if event.start_ticks > 0 and (
                event.pid == root_pid or event.parent_pid in formal_event_pids
            ):
                known.add(event.identity)
                formal_pids.add(event.pid)
                changed = True
            else:
                next_pending.append(event)
        if not changed:
            break
        pending = next_pending
    return known


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
        unexplained_cpu_cores: float,
        capability_probe_pid: int = 0,
    ) -> None:
        self.own_pids = own_pids
        self.cpu_heavy_cores = cpu_heavy_cores
        self.memory_heavy_bytes = memory_heavy_bytes
        self.memory_growth_bytes = memory_growth_bytes
        self.max_poll_gap_seconds = max_poll_gap_seconds
        self.unexplained_cpu_cores = unexplained_cpu_cores
        self.capability_probe_pid = capability_probe_pid
        self.previous: Inventory | None = None
        self.events: dict[str, dict[str, Any]] = {}
        self.poll_gap_max_seconds = 0.0
        self.unexplained_cpu_cores_max = 0.0

    def _event(self, key: str, **values: Any) -> None:
        self.events.setdefault(key, values)

    def observe(
        self,
        inventory: Inventory,
        formal_identities: set[tuple[int, int]],
    ) -> None:
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
        allowed_identities = formal_identities
        for row in inventory.processes:
            name = row.name.lower().removesuffix(".exe")
            if (
                row.identity in allowed_identities
                or row.pid in self.own_pids
                or name in OBSERVER_INFRA_NAMES
            ):
                continue
            reason: str | None = None
            prior = old.get(row.identity)
            if name in FORBIDDEN_NAMES:
                reason = "forbidden process class"
            elif (
                prior is None and previous is not None and name in SUSPICIOUS_NEW_NAMES
            ):
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
        formal_pids = {pid for pid, _start in formal_identities}
        for event in inventory.start_events:
            if (
                event.identity in formal_identities
                or event.pid in self.own_pids
                or event.pid == self.capability_probe_pid
                or event.parent_pid in formal_pids
            ):
                continue
            name = event.name.lower().removesuffix(".exe")
            if name in FORBIDDEN_NAMES or name in SUSPICIOUS_NEW_NAMES:
                self._event(
                    f"start:{event.pid}:{event.start_ticks}",
                    category="process_start",
                    name=event.name,
                    pid=event.pid,
                    reason="forbidden or suspicious process-start event",
                )
        if previous is not None and gap > 0:
            system_busy = (
                inventory.system_kernel_100ns
                - previous.system_kernel_100ns
                + inventory.system_user_100ns
                - previous.system_user_100ns
                - inventory.system_idle_100ns
                + previous.system_idle_100ns
            )
            accounted = 0
            for row in inventory.processes:
                prior = old.get(row.identity)
                if prior is None:
                    continue
                name = row.name.lower().removesuffix(".exe")
                if (
                    row.identity in formal_identities
                    or row.pid in self.own_pids
                    or name in OBSERVER_INFRA_NAMES
                ):
                    accounted += max(0, row.cpu_100ns - prior.cpu_100ns)
            unexplained = max(0, system_busy - accounted) / 10_000_000 / gap
            self.unexplained_cpu_cores_max = max(
                self.unexplained_cpu_cores_max, unexplained
            )
            if unexplained >= self.unexplained_cpu_cores:
                self._event(
                    f"aggregate-cpu:{inventory.monotonic_ticks}",
                    category="aggregate_cpu",
                    unexplained_cpu_cores=unexplained,
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
        or any(
            not isinstance(pid, int) or isinstance(pid, bool) or pid <= 0
            for pid in segment_pids
        )
    ):
        raise ObservationError(f"capture must bind {segment_count} unique segment PIDs")
    if _parse_utc(observation_start) > _parse_utc(outer.get("started_at_utc")):
        raise ObservationError("observation started after outer audit")
    if _parse_utc(observation_end) < _parse_utc(outer.get("ended_at_utc")):
        raise ObservationError("observation ended before outer audit")
    return outer_pid, segment_pids


class _LineReader:
    def __init__(self, stream: IO[bytes]) -> None:
        self.items: queue.Queue[bytes | BaseException | None] = queue.Queue()
        self.thread = threading.Thread(target=self._read, args=(stream,), daemon=True)
        self.thread.start()

    def _read(self, stream: IO[bytes]) -> None:
        try:
            while raw := stream.readline():
                self.items.put(raw)
        except BaseException as error:
            self.items.put(error)
        finally:
            self.items.put(None)

    def next(self, timeout: float) -> bytes:
        try:
            item = self.items.get(timeout=timeout)
        except queue.Empty as error:
            raise ObservationError("inventory backend stalled") from error
        if item is None:
            raise ObservationError("inventory backend ended")
        if isinstance(item, BaseException):
            raise ObservationError(f"inventory reader failed: {item}")
        return item


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while block := handle.read(1024 * 1024):
            digest.update(block)
    return digest.hexdigest()


class PowerShellInventory:
    def __init__(
        self,
        executable: str,
        poll_seconds: float,
        event_within_seconds: float,
    ) -> None:
        self.executable = Path(executable).resolve(strict=True)
        version = subprocess.run(
            [
                str(self.executable),
                "-NoLogo",
                "-NoProfile",
                "-NonInteractive",
                "-Command",
                "$PSVersionTable.PSVersion.ToString()",
            ],
            check=True,
            capture_output=True,
            text=True,
            timeout=10,
        ).stdout.strip()
        try:
            major = int(version.split(".", 1)[0])
        except ValueError as error:
            raise ObservationError(f"invalid PowerShell version: {version}") from error
        if major < 7:
            raise ObservationError("PowerShell 7 or newer is required")
        self.version = version
        script = (
            _SNAPSHOT_SCRIPT.replace(
                "__INTERVAL_MILLISECONDS__",
                str(max(100, round(poll_seconds * 1000))),
            )
            .replace("__EVENT_WITHIN_SECONDS__", repr(event_within_seconds))
            .replace("__OBSERVER_PID__", str(os.getpid()))
        )
        self.script_template_sha256 = hashlib.sha256(
            _SNAPSHOT_SCRIPT.encode()
        ).hexdigest()
        self.script_sha256 = hashlib.sha256(script.encode()).hexdigest()
        encoded = script.encode("utf-16-le")
        command = [
            str(self.executable),
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
        assert self.process.stdout is not None
        self.reader = _LineReader(self.process.stdout)
        self.executable_sha256 = _file_sha256(self.executable)

    def next(self, timeout: float) -> tuple[bytes, Inventory]:
        raw = self.reader.next(timeout)
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


def observation_bindings(
    arguments: argparse.Namespace,
    worker: PowerShellInventory,
    capability: Inventory,
) -> dict[str, Any]:
    return {
        "settings": {
            "schema_version": arguments.schema_version,
            "capture_schema": arguments.capture_schema,
            "segment_count": arguments.segment_count,
            "label": arguments.label,
            "observer": arguments.observer,
            "poll_seconds": arguments.poll_seconds,
            "max_poll_gap_seconds": arguments.max_poll_gap_seconds,
            "cpu_heavy_cores": arguments.cpu_heavy_cores,
            "memory_heavy_bytes": arguments.memory_heavy_bytes,
            "memory_growth_bytes": arguments.memory_growth_bytes,
            "unexplained_cpu_cores": arguments.unexplained_cpu_cores,
            "event_within_seconds": arguments.event_within_seconds,
            "backend_stall_seconds": arguments.backend_stall_seconds,
            "timeout_seconds": arguments.timeout_seconds,
        },
        "paths": {
            "lock": str(arguments.lock.resolve()),
            "outer_audit": str(arguments.outer_audit.resolve()),
            "capture": str(arguments.capture.resolve()),
            "ready": str(arguments.ready.resolve()),
            "output": str(arguments.output.resolve()),
        },
        "backend": {
            "executable": str(worker.executable),
            "executable_sha256": worker.executable_sha256,
            "version": worker.version,
            "script_template_sha256": worker.script_template_sha256,
            "script_sha256": worker.script_sha256,
            "parent_capability": capability.parent_capability,
            "event_capability": capability.event_capability,
            "event_source": capability.event_source,
            "event_within_seconds": capability.event_within_seconds,
            "capability_probe_pid": capability.capability_probe_pid,
            "shared_infrastructure_process_names": sorted(OBSERVER_INFRA_NAMES),
        },
    }


def _load_object(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_bytes())
    if not isinstance(value, dict):
        raise ObservationError(f"JSON object required: {path}")
    return value


def remaining_before_deadline(
    deadline: float, stall_seconds: float, *, now: float | None = None
) -> float:
    remaining = deadline - (time.monotonic() if now is None else now)
    if remaining <= 0:
        raise ObservationError("observer timeout")
    return min(stall_seconds, remaining)


def next_before_deadline(
    worker: PowerShellInventory, deadline: float, stall_seconds: float
) -> tuple[bytes, Inventory]:
    timeout = remaining_before_deadline(deadline, stall_seconds)
    try:
        return worker.next(timeout)
    except ObservationError as error:
        if time.monotonic() >= deadline:
            raise ObservationError("observer timeout") from error
        raise


def validate_pre_ready(arguments: argparse.Namespace) -> None:
    paths = (
        arguments.output.resolve(),
        arguments.ready.resolve(),
        arguments.outer_audit.resolve(),
        arguments.capture.resolve(),
    )
    existing = [path for path in paths if os.path.lexists(path)]
    if existing:
        raise ObservationError(f"pre-READY path already exists: {existing}")
    lease = read_lease(arguments.lock.resolve())
    if lease.held is not False or lease.state == "running":
        raise ObservationError("pre-READY lease is held, unreadable or active")


def run_observer(arguments: argparse.Namespace) -> int:
    output = arguments.output.resolve()
    ready = arguments.ready.resolve()
    validate_pre_ready(arguments)
    powershell = arguments.powershell or shutil.which("pwsh")
    if os.name != "nt" or powershell is None:
        raise ObservationError(
            "the host inventory backend requires PowerShell 7 on Windows"
        )
    worker = PowerShellInventory(
        powershell, arguments.poll_seconds, arguments.event_within_seconds
    )
    digest = hashlib.sha256()
    sample_count = 0
    formal_identities: set[tuple[int, int]] = set()
    failures: list[str] = []
    outer: dict[str, Any] | None = None
    capture: dict[str, Any] | None = None
    outer_sha256: str | None = None
    capture_sha256: str | None = None
    outer_pid = 0
    segment_pids = [0] * arguments.segment_count
    started = ""
    ended = ""
    all_ended = False
    try:
        raw, first = worker.next(arguments.backend_stall_seconds)
        digest.update(raw)
        sample_count += 1
        if not first.parent_capability or not first.event_capability:
            raise ObservationError(
                "PowerShell parent or process-start capability failed"
            )
        if not math.isclose(
            first.event_within_seconds,
            arguments.event_within_seconds,
            rel_tol=0,
            abs_tol=1e-12,
        ):
            raise ObservationError("process-start event interval drift")
        contention = ContentionTracker(
            own_pids={os.getpid(), worker.process.pid},
            cpu_heavy_cores=arguments.cpu_heavy_cores,
            memory_heavy_bytes=arguments.memory_heavy_bytes,
            memory_growth_bytes=arguments.memory_growth_bytes,
            max_poll_gap_seconds=arguments.max_poll_gap_seconds,
            unexplained_cpu_cores=arguments.unexplained_cpu_cores,
            capability_probe_pid=first.capability_probe_pid,
        )
        contention.observe(first, set())
        if contention.events:
            raise ObservationError("host baseline contains forbidden or heavy work")
        bindings = observation_bindings(arguments, worker, first)
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
                "bindings": bindings,
            },
        )
        ready_sha256 = _file_sha256(ready)
        print(
            f"HOST-OBSERVER READY label={arguments.label} started={started}", flush=True
        )
        lease_tracker = LeaseTracker(arguments.label)
        deadline = time.monotonic() + arguments.timeout_seconds
        try:
            raw, inventory = next_before_deadline(
                worker, deadline, arguments.backend_stall_seconds
            )
        except ObservationError as error:
            failures.append(str(error))
            ended = _utc_now()
            inventory = first
        else:
            digest.update(raw)
            sample_count += 1
        while not failures:
            try:
                remaining_before_deadline(deadline, arguments.backend_stall_seconds)
            except ObservationError as error:
                failures.append(str(error))
                ended = _utc_now()
                break
            if worker.process.poll() is not None:
                failures.append("inventory backend exited")
                ended = _utc_now()
                break

            lease = read_lease(arguments.lock.resolve())
            lease_tracker.observe(lease, audit_exists=arguments.outer_audit.exists())
            extend_formal_identities(
                inventory, lease_tracker.owner_pid, formal_identities
            )
            contention.observe(inventory, formal_identities)

            if outer is None and arguments.outer_audit.exists():
                try:
                    outer = _load_object(arguments.outer_audit.resolve())
                    outer_sha256 = _file_sha256(arguments.outer_audit.resolve())
                except (OSError, json.JSONDecodeError, ObservationError) as error:
                    failures.append(f"outer audit: {error}")
            if capture is None and arguments.capture.exists():
                try:
                    capture = _load_object(arguments.capture.resolve())
                    capture_sha256 = _file_sha256(arguments.capture.resolve())
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
                    formal_pids = {pid for pid, _start in formal_identities}
                    if any(pid not in formal_pids for pid in required):
                        raise ObservationError("a formal PID was not observed live")
                    current_identities = {row.identity for row in inventory.processes}
                    formal_live = bool(formal_identities & current_identities)
                    if lease_tracker.phase == "released" and not formal_live:
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

            try:
                raw, inventory = next_before_deadline(
                    worker, deadline, arguments.backend_stall_seconds
                )
            except ObservationError as error:
                failures.append(str(error))
                ended = _utc_now()
                break
            else:
                digest.update(raw)
                sample_count += 1

        for path, prior, label in (
            (arguments.outer_audit.resolve(), outer_sha256, "outer audit"),
            (arguments.capture.resolve(), capture_sha256, "capture metadata"),
        ):
            if path.exists():
                final_hash = _file_sha256(path)
                if prior is not None and final_hash != prior:
                    failures.append(f"{label} changed after observation")
                if label == "outer audit":
                    outer_sha256 = final_hash
                else:
                    capture_sha256 = final_hash
        for index, reason in enumerate(failures):
            contention._event(
                f"monitor:failure:{index}", category="monitor_failure", reason=reason
            )
        identities_document = [
            {"pid": pid, "start_ticks": start}
            for pid, start in sorted(formal_identities)
        ]
        identities_payload = json.dumps(
            identities_document, sort_keys=True, separators=(",", ":")
        ).encode()
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
            "unexplained_cpu_cores_max": contention.unexplained_cpu_cores_max,
            "contention_events": list(contention.events.values()),
            "lease_loss_events": lease_tracker.loss_events,
            "monitor_failures": failures,
            "inventory_child_pid": worker.process.pid,
            "formal_process_identity_count": len(identities_document),
            "formal_process_identities": identities_document,
            "formal_process_identities_sha256": hashlib.sha256(
                identities_payload
            ).hexdigest(),
            "bindings": bindings,
            "ready_receipt_sha256": ready_sha256,
            "outer_audit_sha256": outer_sha256,
            "capture_metadata_sha256": capture_sha256,
        }
        write_json_exclusive(output, document)
        return (
            0
            if not failures and not contention.events and not lease_tracker.loss_events
            else 2
        )
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
    parser.add_argument("--unexplained-cpu-cores", type=float, default=1.0)
    parser.add_argument("--event-within-seconds", type=float, default=0.1)
    parser.add_argument("--backend-stall-seconds", type=float, default=15.0)
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
        arguments.unexplained_cpu_cores,
        arguments.event_within_seconds,
        arguments.backend_stall_seconds,
        arguments.timeout_seconds,
        arguments.segment_count,
    )
    if any(
        not isinstance(value, int | float) or not math.isfinite(value) or value <= 0
        for value in positive
    ):
        raise SystemExit(
            "observer intervals and thresholds must be finite and positive"
        )
    try:
        return run_observer(arguments)
    except ObservationError as error:
        print(f"HOST-OBSERVER ERROR: {error}", file=sys.stderr, flush=True)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
