"""CPU-only protocol regressions for the staged study's frozen inputs."""

import json
import random
import sys

import pytest

from qwen.common import file_hash
from qwen.grpo_evaluate import main as evaluate_main
from qwen.grpo_evaluate import resolve_evaluation_config
from qwen.grpo_run import evaluation_source_paths, order_training_rows, prepare


def training_rows():
    return [
        {
            "id": f"C{i:02}",
            "variant": f"v{v}",
            "problem": f"{i} plus {v}",
            "answer_exact": str(i + v),
        }
        for i in range(37)
        for v in range(4)
    ]


def protocol():
    return {
        "evaluation_suites": {"numeric": "data/dev.jsonl", "proof": "data/proof.jsonl"},
        "evaluation_stages": {
            "base0": {"numeric": {"samples": 2, "seed": 12}, "proof": {"samples": 4, "seed": 20}},
            "base1": {"proof": {"samples": 4, "seed": 21}},
            "interim": {"numeric": {"samples": 2, "seed": 12}},
            "final0": {"numeric": {"samples": 2, "seed": 12}, "proof": {"samples": 4, "seed": 20}},
            "final1": {"proof": {"samples": 4, "seed": 21}},
        },
    }


def test_representatives_cover_all_37_before_the_first_40_and_preserve_all_rows():
    rows = training_rows()
    unchanged = list(rows)
    config = {"training_order": "representatives_first", "seed": 15}
    ordered = order_training_rows(rows, config)
    assert len(ordered) == 148 and rows == unchanged
    assert {r["id"] for r in ordered[:37]} == {r["id"] for r in rows}
    assert all(r["variant"] == "v0" for r in ordered[:37])
    assert all(r["variant"] != "v0" for r in ordered[37:])
    assert sorted((r["id"], r["variant"]) for r in ordered) == sorted(
        (r["id"], r["variant"]) for r in rows
    )
    assert ordered == order_training_rows(rows, config)
    assert ordered != order_training_rows(rows, {**config, "seed": 16})


def test_legacy_order_is_unchanged_and_missing_representatives_are_rejected():
    rows = training_rows()
    expected = list(rows)
    random.Random(15).shuffle(expected)
    assert order_training_rows(rows, {"seed": 15}) == expected
    with pytest.raises(ValueError, match="exactly one v0"):
        order_training_rows(rows[1:], {"seed": 15, "training_order": "representatives_first"})
    with pytest.raises(ValueError, match="Unknown training_order"):
        order_training_rows(rows, {"seed": 15, "training_order": "unknown"})


def test_stage_blocks_resolve_paired_seeds_and_disjoint_sample_blocks():
    config = protocol()
    for start, final in [("base0", "final0"), ("base1", "final1")]:
        a = resolve_evaluation_config(config, "proof", stage_name=start)
        b = resolve_evaluation_config(config, "proof", stage_name=final)
        assert a["samples"] == b["samples"] == 4 and a["seed"] == b["seed"]
    assert (
        resolve_evaluation_config(config, "proof", stage_name="base0")["seed"]
        != resolve_evaluation_config(config, "proof", stage_name="base1")["seed"]
    )
    assert resolve_evaluation_config(config, "numeric", stage_name="interim")["samples"] == 2
    with pytest.raises(ValueError, match="sample count"):
        resolve_evaluation_config(config, "proof", stage_name="base0", samples=8)
    with pytest.raises(ValueError, match="seed"):
        resolve_evaluation_config(config, "proof", stage_name="base0", seed=21)
    with pytest.raises(ValueError, match="not enabled"):
        resolve_evaluation_config(config, "proof", stage_name="interim")
    with pytest.raises(ValueError, match="stage name"):
        resolve_evaluation_config(config, "proof")


def test_legacy_evaluation_and_snapshot_paths():
    assert resolve_evaluation_config({}, "proof")["samples"] == 8
    assert resolve_evaluation_config({}, "proof")["seed"] == 20261001
    assert (
        resolve_evaluation_config({"evaluation_samples": {"proof": 4}}, "proof", samples=4)[
            "samples"
        ]
        == 4
    )
    config = protocol()
    config["evaluation_files"] = ["data/dev.jsonl"]
    assert evaluation_source_paths(config) == ["data/dev.jsonl", "data/proof.jsonl"]
    with pytest.raises(ValueError, match="relative"):
        evaluation_source_paths({"evaluation_suites": {"proof": "../external.jsonl"}})
    with pytest.raises(ValueError, match="nonnegative integer"):
        resolve_evaluation_config({}, "proof", seed=-1)


@pytest.fixture
def frozen_run(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "qwen").mkdir()
    (tmp_path / "qwen/models.json").write_text("{}")
    (tmp_path / "qwen/source.py").write_text("# fixture\n")
    (tmp_path / "data").mkdir()
    (tmp_path / "data/train.jsonl").write_text("\n".join(json.dumps(r) for r in training_rows()))
    (tmp_path / "data/dev.jsonl").write_text(
        json.dumps({"id": "C00", "problem": "dev", "answer_exact": "1"})
    )
    (tmp_path / "data/proof.jsonl").write_text(
        json.dumps({"id": "P01", "prompt": "Prove original."})
    )
    monkeypatch.setattr(
        "qwen.grpo_run.locked_models", lambda **_: {"qwen3_4b": {"revision": "fixture"}}
    )
    monkeypatch.setattr("qwen.grpo_run.importlib.metadata.distributions", lambda: [])
    config = {
        **protocol(),
        "data": "data/train.jsonl",
        "seed": 15,
        "training_order": "representatives_first",
        "samples": 4,
        "prompts_per_round": 4,
        "max_completion": 32512,
        "lr": 1e-6,
        "kv_cache_dtype": "auto",
    }
    root = tmp_path / "run"
    prepare(config, root)
    return config, root


def test_prepare_freezes_suite_sources_and_rejects_modified_training_inputs(frozen_run):
    config, root = frozen_run
    manifest = json.loads((root / "manifest.json").read_text())
    assert set(manifest["evaluation_sha256"]) == {"data/dev.jsonl", "data/proof.jsonl"}
    assert manifest["evaluation_sha256"]["data/proof.jsonl"] == file_hash(
        root / "source/data/proof.jsonl"
    )
    assert len(prepare(config, root)) == 37
    (root / "input.jsonl").write_text("{}\n")
    with pytest.raises(ValueError, match="training inputs changed"):
        prepare(config, root)


def test_evaluation_uses_frozen_source_and_enforces_hash(frozen_run, monkeypatch, capsys, tmp_path):
    _, root = frozen_run
    (tmp_path / "data/proof.jsonl").write_text("original source changed after freeze")
    output = tmp_path / "eval"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "grpo_evaluate",
            "--suite",
            "proof",
            "--stage-name",
            "base1",
            "--experiment",
            str(root),
            "--output",
            str(output),
            "--dry",
        ],
    )
    evaluate_main()
    result = json.loads(capsys.readouterr().out)
    assert result["responses"] == 4
    assert result["command"][result["command"].index("--seed") + 1] == "21"
    assert json.loads((output / "jobs.json").read_text())[0]["problem"] == "Prove original."
    (root / "source/data/proof.jsonl").write_text("tampered frozen source")
    with pytest.raises(ValueError, match="inputs were modified"):
        evaluate_main()


def test_evaluation_rejects_missing_frozen_hash(frozen_run, monkeypatch, tmp_path):
    _, root = frozen_run
    manifest = json.loads((root / "manifest.json").read_text())
    manifest["evaluation_sha256"].pop("data/proof.jsonl")
    (root / "manifest.json").write_text(json.dumps(manifest))
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "grpo_evaluate",
            "--suite",
            "proof",
            "--stage-name",
            "base0",
            "--experiment",
            str(root),
            "--output",
            str(tmp_path / "eval"),
            "--dry",
        ],
    )
    with pytest.raises(ValueError, match="no frozen hash"):
        evaluate_main()
