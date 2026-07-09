from geotarget import __version__
from geotarget.cli import main


def test_version() -> None:
    assert __version__ == "0.1.0.dev0"


def test_empty_cli() -> None:
    assert main([]) == 0
