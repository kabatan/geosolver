"""CPU-only paired reanalysis of frozen numeric-transfer score ledgers.

Writes only paired-evidence.json beside this script. No training or inference.
Clusters are construction IDs, with two inference draws per construction.
Resampling and sign symmetry are exploratory sensitivity calculations, not
confirmatory tests: the problems and recipes were selected during development.
"""
from __future__ import annotations

from collections import Counter
import hashlib
import itertools
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
OLD = ROOT / "qwen/.runtime/transfer_followup_20260926/numeric-extended-score.json"
NEW = ROOT / "qwen/.runtime/numeric_sft_dose_control_20260928/transfer-scores.json"


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def score(row):
    return int(row["finish_reason"] == "stop" and row["numeric_correct"] is True)


def paired(left, right):
    a = {r["job_id"]: r for r in left}
    b = {r["job_id"]: r for r in right}
    assert a.keys() == b.keys()
    differences = Counter()
    sample_counts = Counter()
    wins = losses = 0
    for ident in sorted(a):
        assert a[ident]["source_id"] == b[ident]["source_id"]
        delta = score(b[ident]) - score(a[ident])
        differences[a[ident]["source_id"]] += delta
        sample_counts[a[ident]["source_id"]] += 1
        wins += delta > 0
        losses += delta < 0
    assert set(sample_counts.values()) == {2}
    deltas = list(differences.values())
    nonzero = [d for d in deltas if d]
    null_sums = [sum(d * s for d, s in zip(nonzero, signs))
                 for signs in itertools.product((-1, 1), repeat=len(nonzero))]
    tail = sum(abs(x) >= abs(sum(deltas)) for x in null_sums) / len(null_sums)
    # Exact empirical cluster bootstrap distribution; no random seed is needed.
    support = Counter(deltas)
    sums = Counter({0: 1})
    for _ in deltas:
        nxt = Counter()
        for total, count in sums.items():
            for delta, multiplicity in support.items():
                nxt[total + delta] += count * multiplicity
        sums = nxt
    denominator = sum(sums.values())
    def quantile(probability):
        cumulative = 0
        for total, count in sorted(sums.items()):
            cumulative += count
            if cumulative / denominator >= probability:
                return total / len(a)
        raise AssertionError("Quantile unavailable")
    return {
        "left_correct": sum(map(score, left)),
        "right_correct": sum(map(score, right)),
        "jobs": len(a), "construction_count": len(deltas),
        "right_job_wins": wins, "right_job_losses": losses,
        "construction_deltas": dict(sorted(differences.items())),
        "improved_constructions": sum(x > 0 for x in deltas),
        "worsened_constructions": sum(x < 0 for x in deltas),
        "absolute_accuracy_difference": sum(deltas) / len(a),
        "exploratory_cluster_bootstrap_percentile_95": [quantile(.025), quantile(.975)],
        "exploratory_two_sided_cluster_sign_symmetry_tail": tail,
        "unresolved_left": sum(r["finish_reason"] != "stop" for r in left),
        "unresolved_right": sum(r["finish_reason"] != "stop" for r in right),
    }


def main():
    old = json.loads(OLD.read_text())
    new = json.loads(NEW.read_text())
    old_rows = {k: v["jobs"] for k, v in old["extended_budget_24_job_summary"]["conditions"].items()}
    new_rows = {arm: [r for r in new["numeric"] if r["arm"] == arm
                     and r["split"] == "untrained_configuration"]
                for arm in ("base", "correct128", "correct512", "shuffled512")}
    inspected = {}
    for arm in ("base", "numeric128"):
        for row in old_rows[arm]:
            path = row["source_file"]
            assert digest(path) == row["raw_file_sha256"]
            raw = json.loads(Path(path).read_text())
            assert raw["finish_reason"] == row["finish_reason"]
            inspected[path] = digest(path)
    for rows in new_rows.values():
        for row in rows:
            path = row["file"]
            assert digest(path) == row["file_sha256"]
            raw = json.loads(Path(path).read_text())
            assert raw["finish_reason"] == row["finish_reason"]
            inspected[path] = digest(path)
    out = {
        "scope": "Exploratory reanalysis of saved scores, not new model trials or regrading",
        "limitations": [
            "One trained checkpoint per arm; uncertainty across training seeds is not estimated.",
            "Related development constructions are not a random sample of all geometry problems.",
            "Recipe selection and previous reuse are not corrected by these calculations.",
            "Unfinished outputs are not counted as observed successes; they remain explicitly unresolved.",
            "Bootstrap intervals and sign-symmetry tails are descriptive sensitivity analyses only.",
        ],
        "input_sha256": {str(p): digest(p) for p in (OLD, NEW)},
        "raw_files_verified": len(inspected),
        "old_numeric128_vs_base": paired(old_rows["base"], old_rows["numeric128"]),
        "new_correct512_vs_base": paired(new_rows["base"], new_rows["correct512"]),
        "new_correct512_vs_shuffled512": paired(new_rows["shuffled512"], new_rows["correct512"]),
    }
    assert out["old_numeric128_vs_base"]["left_correct"] == 11
    assert out["old_numeric128_vs_base"]["right_correct"] == 16
    assert out["new_correct512_vs_shuffled512"]["left_correct"] == 9
    assert out["new_correct512_vs_shuffled512"]["right_correct"] == 8
    (HERE / "paired-evidence.json").write_text(json.dumps(out, indent=2) + "\n")
    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()
