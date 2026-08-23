from __future__ import annotations

import importlib
import shutil
import subprocess
from importlib.resources import files
from pathlib import Path
from typing import Any

from geosolver import GeometryProblem, SolveOptions
from geosolver.application.service import solve
from geosolver.runtime.integrity import load_engine_lock, verify_engine_lock


def julia_project_path() -> Path:
    return Path(str(files("geosolver").joinpath("julia")))


def diagnose(*, smoke: bool = True) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    for module in (
        "geosolver",
        "geosolver.application.cli",
        "geosolver.application.http",
        "geosolver.runtime.worker",
    ):
        try:
            importlib.import_module(module)
            checks.append({"name": f"import:{module}", "ok": True})
        except Exception as error:
            checks.append({"name": f"import:{module}", "ok": False, "detail": str(error)})

    julia = shutil.which("julia")
    project = julia_project_path()
    if julia is None:
        checks.append({"name": "julia", "ok": False, "detail": "julia was not found"})
    elif not (project / "Project.toml").is_file():
        checks.append({"name": "julia", "ok": False, "detail": f"missing Julia project: {project}"})
    else:
        try:
            completed = subprocess.run(
                [
                    julia,
                    f"--project={project}",
                    "--startup-file=no",
                    "-e",
                    'using Nemo; print("Nemo ", pkgversion(Nemo))',
                ],
                capture_output=True,
                text=True,
                timeout=60,
                check=False,
            )
            checks.append(
                {
                    "name": "julia",
                    "ok": completed.returncode == 0,
                    "detail": (completed.stdout or completed.stderr).strip(),
                }
            )
        except (OSError, subprocess.SubprocessError) as error:
            checks.append({"name": "julia", "ok": False, "detail": str(error)})

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
