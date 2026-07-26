from typer.testing import CliRunner

from geotarget.cli import app


def test_cli_validate_uses_public_validation_contract() -> None:
    result = CliRunner().invoke(app, ["validate", "examples/problem.json"])
    assert result.exit_code == 0
    assert '"valid": true' in result.stdout
