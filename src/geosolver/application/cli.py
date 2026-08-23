from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated, Any

import typer

from geosolver.application.service import solve as solve_problem
from geosolver.doctor import diagnose
from geosolver.problem.models import SolveOptions
from geosolver.problem.validation import validate as validate_problem

app = typer.Typer(no_args_is_help=True, help="GeoSolver geometry solver")


def _read(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise typer.BadParameter("problem JSON must be an object")
    return value


def _cores(value: str) -> str | int:
    if value == "auto":
        return value
    try:
        parsed = int(value)
    except ValueError as error:
        raise typer.BadParameter("must be 'auto' or a positive integer") from error
    if parsed < 1:
        raise typer.BadParameter("must be 'auto' or a positive integer")
    return parsed


@app.command()
def validate(problem: Path) -> None:
    report = validate_problem(_read(problem))
    typer.echo(json.dumps(report.model_dump(mode="json"), ensure_ascii=False, indent=2))
    if not report.valid:
        raise typer.Exit(2)


@app.command()
def solve(
    problem: Path,
    engine: Annotated[str, typer.Option("--engine")] = "standard",
    time_limit_seconds: Annotated[float | None, typer.Option("--time-limit-seconds")] = None,
    cores: Annotated[str, typer.Option("--cores")] = "auto",
    seed: Annotated[int, typer.Option("--seed")] = 0,
    output: Annotated[Path | None, typer.Option("--output")] = None,
) -> None:
    options = SolveOptions(
        engine=engine,
        time_limit_seconds=time_limit_seconds,
        cores=_cores(cores),
        seed=seed,
    )
    result = solve_problem(_read(problem), options)
    payload = result.model_dump_json(indent=2) + "\n"
    if output is None:
        typer.echo(payload, nl=False)
    else:
        output.write_text(payload, encoding="utf-8", newline="\n")
    if result.status not in {"solved", "no_answer_found", "cancelled"}:
        raise typer.Exit(2)


@app.command()
def doctor() -> None:
    report = diagnose()
    typer.echo(json.dumps(report, ensure_ascii=False, indent=2))
    if not report["ok"]:
        raise typer.Exit(2)


@app.command()
def ui(
    host: Annotated[str, typer.Option(hidden=True)] = "127.0.0.1",
    port: Annotated[int, typer.Option()] = 8765,
) -> None:
    import uvicorn

    uvicorn.run("geosolver.application.http:app", host=host, port=port, log_level="info")


if __name__ == "__main__":
    app()
