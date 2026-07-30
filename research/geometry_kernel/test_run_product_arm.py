from __future__ import annotations

import json

import pytest

from research.geometry_kernel.run_product_arm import _arm_base_commit, _parse_cpus


def test_product_arm_parses_distinct_frozen_cpus() -> None:
    assert _parse_cpus("0,2,15") == (0, 2, 15)
    with pytest.raises(ValueError, match="distinct"):
        _parse_cpus("1,1")
    with pytest.raises(ValueError, match=r"\[0,15\]"):
        _parse_cpus("16")


def test_product_arm_reads_frozen_base_commit(tmp_path) -> None:
    manifest = tmp_path / "arm.json"
    manifest.write_text(json.dumps({"base_commit": "a" * 40}), encoding="utf-8")

    assert _arm_base_commit(manifest) == "a" * 40
