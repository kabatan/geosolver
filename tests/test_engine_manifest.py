import os
from pathlib import Path

from geotarget.doctor import diagnose
from geotarget.engine import ENGINE_HASH, engine_root, extract_answers, verify_engine


def test_frozen_product_manifest_matches_every_engine_file() -> None:
    assert verify_engine() == []


def test_doctor_reports_locked_runtime() -> None:
    report = diagnose()
    assert report["ok"]
    assert report["engine_hash"] == ENGINE_HASH
    assert report["nemo_locked"] is True


def test_frozen_subprocess_python_launcher_is_executable() -> None:
    launcher = engine_root() / "runtime/solver/python/.venv/bin/python"
    assert launcher.is_file()
    assert os.access(Path(launcher), os.X_OK)


def test_exact_descriptor_mapping_is_exposed_without_losing_its_interval() -> None:
    answers = extract_answers(
        {
            "descriptor": {
                "minimal_polynomial_high_to_low": [1, -40],
                "selected_real_root_index": 0,
                "isolating_interval": {"left": "39.9", "right": "40.1"},
                "target_1024": "40.000",
                "authority_kind": "MINPOLY_REAL_ROOT_ISOLATOR",
            }
        }
    )

    assert answers[0].isolating_interval == ["39.9", "40.1"]
    assert answers[0].exact_authority_kind == "MINPOLY_REAL_ROOT_ISOLATOR"


def test_exact_rational_root_is_a_display_decimal_fallback() -> None:
    answers = extract_answers(
        {
            "minimal_polynomial_high_to_low": [1, -5],
            "selected_real_root_index": 0,
            "isolating_interval": {
                "left": "4.9",
                "right": "5.1",
                "exact_rational_root": "5",
            },
        }
    )

    assert answers[0].decimal == "5"
