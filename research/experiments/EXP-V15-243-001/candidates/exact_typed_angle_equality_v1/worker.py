#!/usr/bin/env python3
"""Single-request worker for containment and differential D0 only."""

from __future__ import annotations

from dataclasses import asdict
import ctypes
import json
import os
import sys
import time

import sympy as sp

from candidate import (
    ExactLine,
    ExactPoint,
    ReplayLedger,
    TypedAngle,
    prove_typed_angle_equality,
)


PR_GET_PDEATHSIG = 2


def _point(raw: list[str]) -> ExactPoint:
    return ExactPoint.of(*(sp.Rational(item) for item in raw))


def _line(raw: list[str]) -> ExactLine:
    return ExactLine.of(*(sp.Rational(item) for item in raw))


def _angle(raw: dict) -> TypedAngle:
    kind = raw["kind"]
    if kind == "point_unsigned":
        args = tuple(_point(item) for item in raw["args"])
    elif kind == "line_acute":
        args = tuple(_line(item) for item in raw["args"])
    else:
        args = tuple(raw.get("args", ()))
    return TypedAngle(kind, args, raw["unit"], raw["domain"])


def _pdeathsig() -> int:
    value = ctypes.c_int(0)
    libc = ctypes.CDLL(None, use_errno=True)
    if libc.prctl(PR_GET_PDEATHSIG, ctypes.byref(value), 0, 0, 0) != 0:
        return -1
    return value.value


def main() -> int:
    request = json.load(sys.stdin)
    if request.get("test_sleep_ms"):
        time.sleep(float(request["test_sleep_ms"]) / 1000.0)
    ledger = ReplayLedger(**request.get("ledger", {}))
    result = prove_typed_angle_equality(_angle(request["left"]), _angle(request["right"]), ledger)
    json.dump(
        {
            "result": asdict(result),
            "containment": {
                "affinity": sorted(os.sched_getaffinity(0)),
                "pid": os.getpid(),
                "ppid": os.getppid(),
                "pgid": os.getpgid(0),
                "pdeathsig": _pdeathsig(),
            },
        },
        sys.stdout,
        sort_keys=True,
    )
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
