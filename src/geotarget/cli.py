from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated

import typer

from geotarget.api import app as http_app
from geotarget.doctor import diagnose
from geotarget.models import SolveOptions
from geotarget.service import solve as solve_problem
from geotarget.validation import validate as validate_problem

app = typer.Typer(no_args_is_help=True, help="GeoTarget frozen-champion geometry solver")


def _read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


@app.command()
def validate(problem: Path) -> None:
    report = validate_problem(_read(problem))
    typer.echo(json.dumps(report.model_dump(mode="json"), ensure_ascii=False, indent=2))
    if not report.valid:
        raise typer.Exit(2)


@app.command()
def solve(
    problem: Path,
    time_limit: Annotated[float, typer.Option("--time-limit")] = 180,
    cores: Annotated[int, typer.Option("--cores")] = 1,
    seed: Annotated[int, typer.Option("--seed")] = 0,
    output: Annotated[Path | None, typer.Option("--output")] = None,
) -> None:
    result = solve_problem(
        _read(problem), SolveOptions(time_limit_seconds=time_limit, cores=cores, seed=seed)
    )
    payload = json.dumps(result.model_dump(mode="json"), ensure_ascii=False, indent=2) + "\n"
    if output:
        output.write_text(payload, encoding="utf-8")
    else:
        typer.echo(payload, nl=False)
    if result.status in {"invalid_problem", "resource_error", "engine_error"}:
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

    uvicorn.run(http_app, host=host, port=port, log_level="info")


if __name__ == "__main__":
    app()
