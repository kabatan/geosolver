from typer.testing import CliRunner

from geotarget.cli import app


def test_cli_validate_uses_public_validation_contract() -> None:
    result = CliRunner().invoke(app, ["validate", "examples/problem.json"])
    assert result.exit_code == 0
    assert '"valid": true' in result.stdout


def test_cli_serializes_optimized_options(monkeypatch) -> None:
    captured = {}

    def fake_solve(problem, options):
        del problem
        captured.update(options.model_dump())
        return type(
            "Result",
            (),
            {
                "status": "exact_complete",
                "model_dump": lambda self, **kwargs: {"status": self.status},
            },
        )()

    monkeypatch.setattr("geotarget.cli.solve_problem", fake_solve)
    result = CliRunner().invoke(
        app,
        [
            "solve",
            "examples/problem.json",
            "--engine",
            "optimized",
            "--run-mode",
            "adaptive",
            "--max-time",
            "600",
            "--cores",
            "auto",
        ],
    )

    assert result.exit_code == 0
    assert captured == {
        "engine": "optimized",
        "run_mode": "adaptive",
        "max_time_seconds": 600.0,
        "cores": "auto",
        "seed": 0,
    }


def test_cli_uses_qualified_optimized_default(monkeypatch) -> None:
    captured = {}

    def fake_solve(problem, options):
        del problem
        captured.update(options.model_dump())
        return type(
            "Result",
            (),
            {
                "status": "exact_complete",
                "model_dump": lambda self, **kwargs: {"status": self.status},
            },
        )()

    monkeypatch.setattr("geotarget.cli.solve_problem", fake_solve)
    result = CliRunner().invoke(app, ["solve", "examples/problem.json"])

    assert result.exit_code == 0
    assert captured == {
        "engine": "optimized",
        "run_mode": "adaptive",
        "max_time_seconds": 900.0,
        "cores": "auto",
        "seed": 0,
    }
