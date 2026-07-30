from __future__ import annotations

import json
from pathlib import Path

import pytest

from research.geometry_kernel import product_run_arm_shim
from research.geometry_kernel.product_run_arm_shim import (
    PRODUCT_ROOTS,
    VENV_PYTHON,
    _argument,
    _product_root,
    _venv_reexec_command,
)


def test_shim_selects_product_root_only_from_frozen_arm_base(tmp_path) -> None:
    commit = next(iter(PRODUCT_ROOTS))
    arm = tmp_path / "arm.json"
    arm.write_text(json.dumps({"base_commit": commit}), encoding="utf-8")

    assert _product_root(["--arm", str(arm)]) == PRODUCT_ROOTS[commit]


def test_shim_fails_closed_for_unknown_arm_base(tmp_path) -> None:
    arm = tmp_path / "arm.json"
    arm.write_text(json.dumps({"base_commit": "f" * 40}), encoding="utf-8")

    with pytest.raises(ValueError, match="no product root"):
        _product_root(["--arm", str(arm)])


def test_shim_requires_explicit_campaign_arguments() -> None:
    with pytest.raises(ValueError, match="--cpus"):
        _argument(["--jobs", "1"], "--cpus")


def test_shim_reexecs_fixed_venv_when_frozen_driver_resolves_launcher(monkeypatch) -> None:
    monkeypatch.setattr(product_run_arm_shim.sys, "prefix", "/opt/base-python")

    assert _venv_reexec_command(["--seed", "3"]) == [
        str(VENV_PYTHON),
        str(Path(product_run_arm_shim.__file__).resolve()),
        "--seed",
        "3",
    ]


def test_shim_does_not_reexec_inside_fixed_venv(monkeypatch) -> None:
    monkeypatch.setattr(product_run_arm_shim.sys, "prefix", str(VENV_PYTHON.parents[1]))

    assert _venv_reexec_command(["--seed", "3"]) is None
