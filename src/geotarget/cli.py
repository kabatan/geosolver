from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated

import typer

from geotarget.api import app as http_app
from geotarget.doctor import diagnose
from geotarget.models import SolveOptions
from geotarget.qualification import (
    DEFAULT_CORES,
    DEFAULT_ENGINE,
    DEFAULT_MAX_TIME_SECONDS,
    DEFAULT_RUN_MODE,
)
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
    engine: Annotated[str, typer.Option("--engine")] = DEFAULT_ENGINE,
    run_mode: Annotated[str, typer.Option("--run-mode")] = DEFAULT_RUN_MODE,
    max_time: Annotated[float, typer.Option("--max-time")] = DEFAULT_MAX_TIME_SECONDS,
    cores: Annotated[str, typer.Option("--cores")] = str(DEFAULT_CORES),
    seed: Annotated[int, typer.Option("--seed")] = 0,
    time_limit: Annotated[
        float | None,
        typer.Option("--time-limit", help="Deprecated alias for --max-time in fixed-time mode"),
    ] = None,
    output: Annotated[Path | None, typer.Option("--output")] = None,
) -> None:
    core_value: str | int = cores
    if cores != "auto":
        try:
            core_value = int(cores)
        except ValueError as error:
            raise typer.BadParameter(
                "must be 'auto' or an integer", param_hint="--cores"
            ) from error
    option_payload: dict[str, object] = {
        "engine": engine,
        "run_mode": run_mode,
        "max_time_seconds": max_time,
        "cores": core_value,
        "seed": seed,
    }
    if time_limit is not None:
        option_payload.pop("max_time_seconds")
        option_payload["time_limit_seconds"] = time_limit
        option_payload["run_mode"] = "fixed_time"
    result = solve_problem(
        _read(problem), SolveOptions.model_validate(option_payload)
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
