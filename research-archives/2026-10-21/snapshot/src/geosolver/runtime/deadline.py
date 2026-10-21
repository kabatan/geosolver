"""A solve-local deadline shared by nested numerical algorithms."""

import time
from contextlib import contextmanager
from contextvars import ContextVar
from functools import wraps

_deadline = ContextVar("solve_deadline", default=None)
_timings = ContextVar("solve_timings", default=None)
_counters = ContextVar("solve_counters", default=None)
_progress = ContextVar("solve_progress", default=None)


class RuntimeTimings(dict):
    """Telemetry survives context cleanup, including an exceptional exit."""

    def __init__(self):
        super().__init__()
        self.counters = {}
        self.candidates = {}
        self.exact_records = {}
        self.verification_records = []


def retain_candidates(candidates):
    state = _progress.get()
    if state is None:
        return
    for candidate in candidates:
        key = candidate.candidate_key
        previous = state.candidates.get(key)
        if previous is None or candidate.revision >= previous.revision:
            state.candidates[key] = candidate


def retain_exact_record(record):
    """Only atomically completed, independently checked records can survive."""
    state = _progress.get()
    if state is not None and record.exact_identified:
        candidate = record.candidate
        state.exact_records[candidate.candidate_key] = record
        retain_candidates((candidate,))


def retain_verifications(records):
    state = _progress.get()
    if state is not None:
        state.verification_records.extend(records)


def current_deadline():
    return _deadline.get()


def expired(deadline=None):
    active = _deadline.get()
    limits = [value for value in (active, deadline) if value is not None]
    return bool(limits) and time.monotonic() >= min(limits)


def check_deadline(deadline=None):
    if expired(deadline):
        raise TimeoutError("solve deadline reached")


@contextmanager
def deadline_scope(deadline):
    """Temporarily shorten the current deadline without extending its parent."""
    limits = [value for value in (_deadline.get(), deadline) if value is not None]
    token = _deadline.set(min(limits) if limits else None)
    try:
        yield
    finally:
        _deadline.reset(token)


def uses_deadline(function):
    @wraps(function)
    def scoped(*args, **kwargs):
        with deadline_scope(kwargs.get("deadline_monotonic")):
            return function(*args, **kwargs)

    return scoped


@contextmanager
def runtime_session(deadline):
    from geosolver.runtime.symbolic import SymbolicClient, _client

    client = SymbolicClient(deadline)
    client_token = _client.set(client)
    token = _deadline.set(deadline)
    timings = RuntimeTimings()
    timing_token = _timings.set(timings)
    counter_token = _counters.set(timings.counters)
    progress_token = _progress.set(timings)
    try:
        yield timings
    finally:
        try:
            client.close()
        finally:
            _client.reset(client_token)
            _deadline.reset(token)
            _timings.reset(timing_token)
            _counters.reset(counter_token)
            _progress.reset(progress_token)


def counters_snapshot():
    return dict(_counters.get() or {})


def count_event(name, amount=1):
    """Record actual work separately from public evaluator request counts."""
    counters = _counters.get()
    if counters is not None:
        counters[name] = counters.get(name, 0) + amount


def counted(function):
    @wraps(function)
    def measured(*args, **kwargs):
        counters = _counters.get()
        if counters is not None:
            counters[function.__name__] = counters.get(function.__name__, 0) + 1
        return function(*args, **kwargs)

    return measured


def timed_phase(name):
    def decorate(function):
        @wraps(function)
        def measured(*args, **kwargs):
            if _timings.get() is None:
                return function(*args, **kwargs)
            started = time.monotonic()
            try:
                return function(*args, **kwargs)
            finally:
                timings = _timings.get()
                if timings is not None:
                    timings[name] = timings.get(name, 0.0) + time.monotonic() - started

        return measured

    return decorate
