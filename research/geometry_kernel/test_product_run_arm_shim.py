from __future__ import annotations

import json

import pytest

from research.geometry_kernel.product_run_arm_shim import PRODUCT_ROOTS, _argument, _product_root


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
