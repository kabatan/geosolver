from __future__ import annotations

import json
import os
import subprocess
import tempfile
import venv
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BANNED = (
    "geo" + "target",
    "V" + "15",
    "EXP" + "-",
    "champion" + "_v",
    "finalist" + "_",
    "research" + "/experiments",
    ".venv/",
    "qa-screenshot",
)


def run(command: list[str], *, cwd: Path, env: dict[str, str] | None = None) -> None:
    subprocess.run(command, cwd=cwd, env=env, check=True)


def main() -> int:
    wheels = sorted((ROOT / "dist").glob("geosolver-*.whl"))
    if len(wheels) != 1:
        raise RuntimeError(f"expected one GeoSolver wheel, found {len(wheels)}")
    wheel = wheels[0]
    with zipfile.ZipFile(wheel) as archive:
        names = archive.namelist()
        searchable = ["\n".join(names)]
        for name in names:
            if Path(name).suffix.lower() in {".jl", ".json", ".md", ".py", ".toml", ".txt"}:
                searchable.append(archive.read(name).decode("utf-8", errors="replace"))
    lowered = "\n".join(searchable).lower()
    found = [value for value in BANNED if value.lower() in lowered]
    if found:
        raise RuntimeError(f"wheel contains retired product artifacts: {found}")
    required = {
        "geosolver/engine-lock.json",
        "geosolver/schemas/geometry-problem.schema.json",
        "geosolver/schemas/solve-result.schema.json",
    }
    missing = sorted(required.difference(names))
    if missing:
        raise RuntimeError(f"wheel is missing product files: {missing}")

    with tempfile.TemporaryDirectory(prefix="geosolver-wheel-") as temporary:
        directory = Path(temporary)
        environment = os.environ.copy()
        environment.pop("PYTHONPATH", None)
        # Preserve the interpreter installation layout on POSIX (notably macOS).
        venv.create(directory / "venv", with_pip=True, symlinks=os.name != "nt")
        if os.name == "nt":
            python = directory / "venv" / "Scripts" / "python.exe"
            cli = directory / "venv" / "Scripts" / "geosolver.exe"
        else:
            python = directory / "venv" / "bin" / "python"
            cli = directory / "venv" / "bin" / "geosolver"
        run([str(python), "-m", "pip", "install", str(wheel)], cwd=directory, env=environment)

        problem = {
            "id": "wheel-integer",
            "variables": ["x"],
            "constructions": [],
            "conditions": [{"left": "x", "operator": "=", "right": 1}],
            "target": "x",
        }
        problem_path = directory / "問題 with spaces.json"
        problem_path.write_text(json.dumps(problem, ensure_ascii=False), encoding="utf-8")
        run([str(cli), "validate", str(problem_path)], cwd=directory, env=environment)
        run([str(cli), "doctor"], cwd=directory, env=environment)

        smoke = """
from geosolver import GeometryProblem, SolveOptions, solve

def solved(target, constructions):
    problem = GeometryProblem(
        id='wheel-smoke', variables=[], constructions=constructions,
        conditions=[], target=target,
    )
    result = solve(problem, SolveOptions(time_limit_seconds=180, cores=1))
    assert result.status == 'solved', result
    return result.answers[0]

angle = solved('Angle(B, A, C)', [
    {'name': 'A', 'expression': 'Point(0, 0)'},
    {'name': 'B', 'expression': 'Point(1, 0)'},
    {'name': 'C', 'expression': 'Point(0, 1)'},
])
assert angle.kind == 'affine_pi', angle
assert angle.pi_coefficient.minimal_polynomial == ['2', '-1'], angle
degrees = solved('Degrees(Angle(B, A, C))', [
    {'name': 'A', 'expression': 'Point(0, 0)'},
    {'name': 'B', 'expression': 'Point(1, 0)'},
    {'name': 'C', 'expression': 'Point(0, 1)'},
])
assert degrees.kind == 'algebraic' and degrees.decimal.startswith('90'), degrees

branches = solve(
    GeometryProblem(
        id='wheel-scalar-branches', variables=['x'], constructions=[],
        conditions=[
            {'left': '0', 'operator': '=', 'right': 0},
            {'left': '(x-2)*(x+3)', 'operator': '=', 'right': 0},
        ],
        target='x',
    ),
    SolveOptions(time_limit_seconds=180, cores=1, seed=0),
)
assert branches.status == 'solved', branches
assert all(answer.kind == 'algebraic' for answer in branches.answers), branches
assert {tuple(answer.minimal_polynomial) for answer in branches.answers} == {
    ('1', '-2'), ('1', '3'),
}, branches
"""
        run([str(python), "-c", smoke], cwd=directory, env=environment)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
