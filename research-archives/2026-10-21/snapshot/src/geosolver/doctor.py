from __future__ import annotations

import importlib
from typing import Any

from geosolver import GeometryProblem, SolveOptions
from geosolver.application.service import solve
from geosolver.runtime.integrity import load_engine_lock, verify_engine_lock


def diagnose(*, smoke: bool = True) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    for module in (
        "geosolver",
        "geosolver.application.cli",
        "geosolver.runtime.worker",
    ):
        try:
            importlib.import_module(module)
            checks.append({"name": f"import:{module}", "ok": True})
        except Exception as error:
            checks.append({"name": f"import:{module}", "ok": False, "detail": str(error)})

    try:
        load_engine_lock()
        lock_ok, lock_detail = verify_engine_lock()
        checks.append({"name": "engine-lock", "ok": lock_ok, "detail": lock_detail})
    except (OSError, ValueError) as error:
        checks.append({"name": "engine-lock", "ok": False, "detail": str(error)})

    if smoke:
        problem = GeometryProblem(
            id="doctor-positive-dimensional",
            variables=["x"],
            constructions=[],
            conditions=[{"left": "x", "operator": "=", "right": 1}],
            target="x",
        )
        result = solve(problem, SolveOptions(time_limit_seconds=180, cores=1))
        checks.append(
            {
                "name": "positive-dimensional-smoke",
                "ok": result.status == "solved",
                "detail": result.status,
            }
        )
    return {"ok": all(check["ok"] for check in checks), "checks": checks}
