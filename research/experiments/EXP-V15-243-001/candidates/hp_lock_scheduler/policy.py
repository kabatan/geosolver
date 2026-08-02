"""Candidate-private HP resource scheduling policy.

The frozen HP endpoint bridge serializes every case in the repository behind
one blocking flock.  That makes a case's 180-second wall budget depend on
unrelated cases running on other physical cores.  This module replaces that
cross-core mutex with:

* one short-wait lease per pinned physical core;
* the existing crash-safe aggregate RSS token reservation as the host-wide
  concurrency bound; and
* explicit accounting for the nested wrapper/HP-child reservations.

It does not inspect source contents, case identity, target values, or truth.
"""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import asdict, dataclass
import fcntl
import math
import os
from pathlib import Path
import time
from typing import Iterator


MIB = 1024**2
GIB = 1024**3
PHYSICAL_CPU_COUNT = 16
DEFAULT_MAX_JOBS = 7
DEFAULT_TOP_LEVEL_RSS_BYTES = 256 * MIB
DEFAULT_BRIDGE_RSS_BYTES = 128 * MIB
DEFAULT_HP_CHILD_RSS_BYTES = 480 * MIB
DEFAULT_SEARCH_RSS_BYTES = 768 * MIB
DEFAULT_RESTORATION_RSS_BYTES = 768 * MIB
DEFAULT_GLOBAL_RESERVATION_BYTES = 8 * GIB
DEFAULT_RESERVATION_TOKEN_BYTES = 256 * MIB
LOCK_ROOT = Path(f"/tmp/geotarget-hp-per-core-v1-{os.getuid()}")
MAX_JOBS_ENV = "GEOTARGET_HP_MAX_JOBS"
GLOBAL_RESERVATION_ENV = "GEOTARGET_GLOBAL_RSS_RESERVATION_BYTES"
RESERVATION_TOKEN_ENV = "GEOTARGET_MEMORY_RESERVATION_TOKEN_BYTES"


class LeaseUnavailable(RuntimeError):
    """The pinned core was already running an HP child."""


@dataclass(frozen=True)
class ResourcePolicy:
    """Resource-only policy; no problem-dependent signal is accepted."""

    max_jobs: int = DEFAULT_MAX_JOBS
    top_level_rss_bytes: int = DEFAULT_TOP_LEVEL_RSS_BYTES
    bridge_rss_bytes: int = DEFAULT_BRIDGE_RSS_BYTES
    hp_child_rss_bytes: int = DEFAULT_HP_CHILD_RSS_BYTES
    search_rss_bytes: int = DEFAULT_SEARCH_RSS_BYTES
    restoration_rss_bytes: int = DEFAULT_RESTORATION_RSS_BYTES
    global_reservation_bytes: int = DEFAULT_GLOBAL_RESERVATION_BYTES
    reservation_token_bytes: int = DEFAULT_RESERVATION_TOKEN_BYTES
    maximum_core_lease_wait_seconds: float = 0.25

    def validate(self) -> None:
        if not 1 <= self.max_jobs <= PHYSICAL_CPU_COUNT:
            raise ValueError("max_jobs must fit the physical-core set")
        for name in (
            "top_level_rss_bytes",
            "bridge_rss_bytes",
            "hp_child_rss_bytes",
            "search_rss_bytes",
            "restoration_rss_bytes",
            "global_reservation_bytes",
            "reservation_token_bytes",
        ):
            if getattr(self, name) <= 0:
                raise ValueError(f"{name} must be positive")
        if not math.isfinite(self.maximum_core_lease_wait_seconds):
            raise ValueError("core lease wait must be finite")
        if not 0.0 <= self.maximum_core_lease_wait_seconds <= 1.0:
            raise ValueError("core lease wait must lie in [0, 1]")
        if self.reservation_token_bytes > self.global_reservation_bytes:
            raise ValueError("reservation token cannot exceed global allowance")
        if (
            self.worst_case_token_reserved_bytes
            > self.global_reservation_bytes
        ):
            raise ValueError(
                "nested reservations exceed the aggregate RSS allowance"
            )

    @property
    def primary_nested_request_bytes(self) -> int:
        return (
            self.top_level_rss_bytes
            + self.bridge_rss_bytes
            + self.hp_child_rss_bytes
        )

    @property
    def restoration_nested_request_bytes(self) -> int:
        return self.top_level_rss_bytes + self.restoration_rss_bytes

    @property
    def search_nested_request_bytes(self) -> int:
        return self.top_level_rss_bytes + self.search_rss_bytes

    @property
    def formal_process_group_rss_bytes(self) -> int:
        """Maximum declared root-plus-one-nested-lane RSS per case."""

        return max(
            self.primary_nested_request_bytes,
            self.search_nested_request_bytes,
            self.restoration_nested_request_bytes,
        )

    def tokens_for(self, requested_bytes: int) -> int:
        return math.ceil(requested_bytes / self.reservation_token_bytes)

    @property
    def primary_tokens_per_job(self) -> int:
        # Reservations are acquired independently and therefore rounded
        # independently: top worker (1) + wrapper (1) + HP child (2).
        return (
            self.tokens_for(self.top_level_rss_bytes)
            + self.tokens_for(self.bridge_rss_bytes)
            + self.tokens_for(self.hp_child_rss_bytes)
        )

    @property
    def restoration_tokens_per_job(self) -> int:
        return (
            self.tokens_for(self.top_level_rss_bytes)
            + self.tokens_for(self.restoration_rss_bytes)
        )

    @property
    def search_tokens_per_job(self) -> int:
        return (
            self.tokens_for(self.top_level_rss_bytes)
            + self.tokens_for(self.search_rss_bytes)
        )

    @property
    def maximum_tokens_per_job(self) -> int:
        return max(
            self.primary_tokens_per_job,
            self.search_tokens_per_job,
            self.restoration_tokens_per_job,
        )

    @property
    def total_token_count(self) -> int:
        return self.global_reservation_bytes // self.reservation_token_bytes

    @property
    def worst_case_token_count(self) -> int:
        return self.max_jobs * self.maximum_tokens_per_job

    @property
    def worst_case_token_reserved_bytes(self) -> int:
        return self.worst_case_token_count * self.reservation_token_bytes

    @property
    def reservation_headroom_bytes(self) -> int:
        return (
            self.global_reservation_bytes
            - self.worst_case_token_reserved_bytes
        )

    def to_dict(self) -> dict[str, int | float]:
        document = asdict(self)
        document.update(
            {
                "primary_nested_request_bytes": (
                    self.primary_nested_request_bytes
                ),
                "restoration_nested_request_bytes": (
                    self.restoration_nested_request_bytes
                ),
                "search_nested_request_bytes": (
                    self.search_nested_request_bytes
                ),
                "formal_process_group_rss_bytes": (
                    self.formal_process_group_rss_bytes
                ),
                "primary_tokens_per_job": self.primary_tokens_per_job,
                "restoration_tokens_per_job": (
                    self.restoration_tokens_per_job
                ),
                "search_tokens_per_job": self.search_tokens_per_job,
                "maximum_tokens_per_job": self.maximum_tokens_per_job,
                "total_token_count": self.total_token_count,
                "worst_case_token_count": self.worst_case_token_count,
                "worst_case_token_reserved_bytes": (
                    self.worst_case_token_reserved_bytes
                ),
                "reservation_headroom_bytes": self.reservation_headroom_bytes,
                "host_wide_concurrency_authority": (
                    "safe_subprocess aggregate RSS token reservation"
                ),
                "cross_core_hp_mutex": False,
            }
        )
        return document


def _positive_environment_integer(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None:
        return default
    try:
        value = int(raw)
    except ValueError as error:
        raise ValueError(f"{name} must be an integer") from error
    if value <= 0:
        raise ValueError(f"{name} must be positive")
    return value


DEFAULT_POLICY = ResourcePolicy(
    max_jobs=_positive_environment_integer(
        MAX_JOBS_ENV,
        DEFAULT_MAX_JOBS,
    ),
    global_reservation_bytes=_positive_environment_integer(
        GLOBAL_RESERVATION_ENV,
        DEFAULT_GLOBAL_RESERVATION_BYTES,
    ),
    reservation_token_bytes=_positive_environment_integer(
        RESERVATION_TOKEN_ENV,
        DEFAULT_RESERVATION_TOKEN_BYTES,
    ),
)
DEFAULT_POLICY.validate()


def core_lock_path(cpu: int, *, root: Path = LOCK_ROOT) -> Path:
    if not 0 <= cpu < PHYSICAL_CPU_COUNT:
        raise ValueError("CPU must be a first-sibling physical core in [0,15]")
    return root / f"cpu-{cpu:02d}.lock"


def lease_wait_budget(
    *,
    deadline_seconds: float,
    process_timeout_seconds: float,
    policy: ResourcePolicy = DEFAULT_POLICY,
) -> float:
    """Reserve the frozen bridge's 0.25-second child/outer shutdown margin.

    The old blocking flock could consume the complete outer timeout and then
    start an HP child with its original full deadline.  Here a lease either
    arrives quickly or the endpoint fails closed before a child is launched.
    """

    if (
        not math.isfinite(deadline_seconds)
        or not math.isfinite(process_timeout_seconds)
        or deadline_seconds <= 0.0
        or process_timeout_seconds <= deadline_seconds
    ):
        raise ValueError("invalid HP deadline/process timeout")
    available_margin = max(
        0.0,
        process_timeout_seconds - deadline_seconds - 0.25,
    )
    return min(policy.maximum_core_lease_wait_seconds, available_margin)


@contextmanager
def per_core_lease(
    cpu: int,
    *,
    wait_seconds: float,
    root: Path = LOCK_ROOT,
    clock=time.monotonic,
    poll_seconds: float = 0.01,
) -> Iterator[Path]:
    """Acquire one crash-safe HP lease for the pinned physical core.

    Different physical cores never block one another.  A duplicate launch on
    the same core is rejected within the explicit wait allowance.
    """

    if not math.isfinite(wait_seconds) or wait_seconds < 0.0:
        raise ValueError("wait_seconds must be finite and nonnegative")
    if not math.isfinite(poll_seconds) or not 0.001 <= poll_seconds <= 0.1:
        raise ValueError("poll_seconds must lie in [0.001, 0.1]")
    path = core_lock_path(cpu, root=root)
    path.parent.mkdir(parents=True, exist_ok=True)
    deadline = clock() + wait_seconds
    with path.open("a+b") as handle:
        while True:
            try:
                fcntl.flock(
                    handle.fileno(),
                    fcntl.LOCK_EX | fcntl.LOCK_NB,
                )
                break
            except BlockingIOError:
                now = clock()
                if now >= deadline:
                    raise LeaseUnavailable(
                        f"HP core lease unavailable for cpu={cpu}"
                    )
                time.sleep(min(poll_seconds, max(0.0, deadline - now)))
        try:
            yield path
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
