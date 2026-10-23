"""Independent integer counts and joins; no solver execution."""
import csv
import hashlib
import json
import math
import re
from collections import Counter
from pathlib import Path

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[2]


def rows(path):
    assert path.stat().st_size < 5_000_000
    with path.open(newline="") as handle:
        return list(csv.DictReader(handle))


def true(value):
    assert value in {"True", "False"}, value
    return value == "True"


def main():
    f = rows(ROOT / "jssa/strategy/astra-consult-18/Q27f/selected-case-validation.csv")
    f = {r["id"] for r in f if true(r["p2_qualifies"])}
    census = rows(ROOT / "jssa/strategy/astra-consult-18/Q27d/census-both-seeds.csv")
    d = {r["id"] for r in census if int(r["d"]) in {6, 7}}
    ids = f | d
    assert (len(f), len(d), len(f & d), len(ids)) == (21, 29, 7, 43)
    p = rows(OUT / "per-problem.csv")
    assert len(p) == len({r["problem_id"] for r in p}) == 43
    assert {r["problem_id"] for r in p} == ids
    assert sum(int(r["local_starts0"]) + int(r["local_starts1"]) for r in p if r["problem_id"] in f) == 6971
    assert sum(int(r["local_hits0"]) + int(r["local_hits1"]) for r in p if r["problem_id"] in f) == 0
    assert sum(int(r["local_starts0"]) + int(r["local_starts1"]) for r in p if r["problem_id"] in d) == 9653
    assert sum(int(r["local_hits0"]) + int(r["local_hits1"]) for r in p if r["problem_id"] in d) == 1859
    assert all(int(r["full_correct"]) == int(r["full_runs"]) == 3 for r in p)

    original = rows(ROOT / "jssa/results/mechanism-attribution/attribution.csv")
    orig = {(r["case_id"], r["seed"]): r for r in original}
    assert len(orig) == 969 and sum(true(r["matched"]) for r in original) == 953
    run = rows(OUT / "per-run.csv")
    assert len(run) == len({(r["case_id"], r["seed"]) for r in run}) == 129
    assert {(r["case_id"], r["seed"]) for r in run} == {(cid, str(s)) for cid in ids for s in range(3)}
    for r in run:
        assert all(r[k] == v for k, v in orig[r["case_id"], r["seed"]].items())
        assert true(r["matched"])
    f_sources = Counter(r["answer_source_uid_prefix"] for r in run if r["case_id"] in f)
    assert f_sources == {"search/nomad": 49, "search/scipy": 7, "rescue/nomad": 7}
    assert sum(r["second_attempt_selected"] == "fallback" for r in run) == 17
    assert sum(int(r["stage_candidates_rejected_false"]) > 0 for r in run) == 94

    modes = rows(ROOT / "jssa/results/search-mode-ablation/per-run.csv")
    mode = {(r["case_id"], r["search_mode"]): r for r in modes}
    mode_correct = {m: sum(true(mode[c, m]["solved"]) for c in ids) for m in ("disco_mads", "mads", "scipy_multistart")}
    assert mode_correct == {"disco_mads": 38, "mads": 38, "scipy_multistart": 42}
    lost = {c for c in ids if not true(mode[c, "disco_mads"]["solved"])}
    assert lost == {"AIME-2014-I-13", "HMMT-2008-FEB-GEO-05", "HMMT-2022-FEB-GEO-10", "HMMT-2025-FEB-GEO-01", "JMO-2023-PRE-06"}
    assert all(orig[c, "0"]["second_attempt_selected"] == "fallback" for c in lost)
    replacement_loss = {c for c in ids if true(mode[c, "disco_mads"]["solved"]) and not true(mode[c, "scipy_multistart"]["solved"])}
    assert replacement_loss == {"AIME-2019-II-15"}
    for r in p:
        for m in mode_correct:
            assert true(r[f"second_off_{m}_correct_seed0"]) == true(mode[r["problem_id"], m]["solved"])

    components = rows(OUT / "per-component.csv")
    assert len(components) == len({(r["problem_id"], r["component"]) for r in components}) == 301
    assert Counter(r["problem_id"] for r in components) == {c: 7 for c in ids}
    assert set(Counter(r["component"] for r in components).values()) == {43}
    coverage = Counter(r["measurement_status"] for r in components)
    assert coverage["原票未取得（未測定かは断定不可）"] == 172
    assert coverage["未測定（保存された12問に対象なし）"] == 39
    assert coverage["精密化のみ測定"] == 4

    tangency = rows(ROOT / "jssa/results/tangency-signed/per-case.csv")
    candidates_path = ROOT / "jssa/results/tangency-signed/per-candidate.csv"
    candidates = rows(candidates_path)
    checked_groups = 0
    for r in tangency:
        if r["case_id"] not in ids:
            continue
        candidates_group = [c for c in candidates if (c["case_id"], c["order"]) == (r["case_id"], r["order"])]
        assert len(candidates_group) == int(r["common_candidates"]) == int(r["n_candidates"])
        for side in ("with", "without"):
            values = [float(c[side + "_digits"]) for c in candidates_group if c[side + "_digits"]]
            assert math.isclose(max(values), float(r[side + "_best_digits"]), abs_tol=1e-12)
        checked_groups += 1
    assert checked_groups == 8

    sources = json.loads((OUT / "sources.json").read_text())
    for path, record in sources.items():
        source = ROOT / path
        digest = hashlib.sha256()
        with source.open("rb") as handle:
            for block in iter(lambda: handle.read(65536), b""):
                digest.update(block)
        assert digest.hexdigest() == record["sha256"], path
        assert source.stat().st_size == record["bytes"], path
    audit = json.loads((OUT / "access-audit.json").read_text())
    assert not audit["requested_ref_available"], "Source availability changed: revisit the missing-data classification"
    broken = []
    for link in re.findall(r"\[[^\]]+\]\(([^)]+)\)", (OUT / "answer.md").read_text()):
        if "://" not in link and link != "verification.json" and not (OUT / link).exists():
            broken.append(link)
    assert not broken, broken
    sizes = {p.name: p.stat().st_size for p in OUT.iterdir() if p.is_file()}
    assert max(sizes.values()) < 5_000_000
    verification = {
        "status": "pass",
        "cohort_sizes_Q27f_Q27d_overlap_union": [21, 29, 7, 43],
        "unique_selected_runs": 129, "component_rows": 301,
        "all_969_correctness_and_stage_labels_checked_by_analyzer": True,
        "source_hashes_unchanged": len(sources),
        "tangency_candidate_groups_checked": checked_groups,
        "tangency_candidate_source_sha256": hashlib.sha256(candidates_path.read_bytes()).hexdigest(),
        "measurement_status_counts": dict(coverage),
        "search_mode_correct": mode_correct,
        "second_search_cross_campaign_loss_ids": sorted(lost),
        "broken_report_links": broken, "output_sizes_bytes": sizes,
        "new_solver_runs": 0, "network_calls": 0,
        "limitation": "Requested 1/3-seed ablation raw files unavailable; these checks do not substitute for them.",
    }
    (OUT / "verification.json").write_text(json.dumps(verification, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps({k: v for k, v in verification.items() if k != "output_sizes_bytes"}, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
