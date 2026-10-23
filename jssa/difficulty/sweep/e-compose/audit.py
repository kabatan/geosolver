"""Verify immutable inputs, schedule receipts, and stitched independent figures."""

from __future__ import annotations

import ast
import json
from collections import Counter

from analyze import coordinate_layout, evaluator_variant, expand_coordinates
from experiment import HERE, RAW, ROOT, SEEDS, SOURCE, digest, read, save, verify_source


def names_in(expr):
    if not isinstance(expr, str):
        return set()
    return {n.id for n in ast.walk(ast.parse(expr, mode="eval")) if isinstance(n, ast.Name)}


def first_accepted(variant, seed):
    raw = read(RAW / "runs" / f"{variant}__s{seed}.json")
    result = raw.get("solver_result") or {}
    candidates = (result.get("diagnostics") or {}).get("candidate_records") or []
    for c in candidates:
        if c.get("accepted"):
            full = expand_coordinates(variant, c["x_hp"])
            return dict(zip(coordinate_layout(variant)[0], full, strict=True))
    return None


def evaluate_joint(variant, mapping):
    from mpmath import mp

    from geosolver.engine.standard.precision.type_guards.high_precision_mode import (
        high_precision_mode,
    )

    ev = evaluator_variant(variant)
    with mp.workdps(80), high_precision_mode():
        x = [mp.mpf(mapping[name]) for name in ev.bundle.var_names]
        res = ev.evaluate_hp_residual(x, precision=80)
        hard = ev.evaluate_hp_hard_feasibility(x, precision=80, include_margins=False)
        ans = ev.evaluate_answer_hp(x, precision=80)
        return {
            "finite": res.is_finite,
            "residual": str(res.residual_norm_hp),
            "hard_feasible": hard.hard_feasible,
            "answer": str(ans.answer_hp),
            "numeric_feasible": bool(
                res.is_finite and res.residual_norm_hp <= mp.mpf("1e-20") and hard.hard_feasible
            ),
        }


def main():
    manifest = read(HERE / "manifest.json")
    summary = read(HERE / "summary.json")
    source = verify_source()
    problems = {v["id"]: read(HERE / "inputs" / f"{v['id']}.json") for v in manifest["variants"]}
    input_ok = all(digest(problems[v["id"]]) == v["input_sha256"] for v in manifest["variants"])
    assert input_ok and summary["source_hash_ok"] and summary["input_hash_ok"]
    assert not summary["missing_receipts"] and summary["summarized_runs"] == 190
    assert not summary["contract_issues"]
    input_sources_unchanged = all(
        digest((ROOT / p).read_bytes()) == sha for p, sha in manifest["source_files_sha256"].items()
    )
    expected = {f"{j['variant']}__s{j['seed']}" for j in manifest["schedule"]}
    actual = {p.stem for p in (RAW / "receipts").glob("*.json")}
    assert actual == expected
    receipts = [read(RAW / "receipts" / f"{k}.json") for k in sorted(expected)]
    events = [(r["started_utc"], 1) for r in receipts] + [(r["finished_utc"], -1) for r in receipts]
    count, max_live = 0, 0
    for _, increment in sorted(events):
        count += increment
        max_live = max(max_live, count)
    assert max_live <= 3
    # Every expression/condition belongs to at most one component namespace.
    crossings = []
    for v in manifest["variants"]:
        if not v["kind"].startswith(("pair_", "quad_")):
            continue
        doc = problems[v["id"]]
        expressions = [c["expression"] for c in doc["constructions"]]
        for c in doc["conditions"]:
            refs = set().union(*(names_in(c.get(k)) for k in ("left", "right", "predicate")))
            groups = {
                name.split("_", 1)[0] for name in refs if name.startswith("q") and "_" in name
            }
            if len(groups) > 1:
                crossings.append((v["id"], c))
        for expr in expressions:
            groups = {
                name.split("_", 1)[0]
                for name in names_in(expr)
                if name.startswith("q") and "_" in name
            }
            if len(groups) > 1:
                crossings.append((v["id"], expr))
    assert not crossings
    split_checks = []
    for i in range(20):
        full = problems[f"single-{i:02d}"]["conditions"]
        parts = [problems[f"half{h}-{i:02d}"]["conditions"] for h in (0, 1)]
        # Equalities are a disjoint partition with multiplicities; all guards occur in both.
        eq_full = Counter(digest(c) for c in full if c.get("operator") == "=")
        eq_parts = Counter(digest(c) for part in parts for c in part if c.get("operator") == "=")
        guard = Counter(digest(c) for c in full if c.get("operator") != "=")
        assert eq_full == eq_parts
        assert all(
            Counter(digest(c) for c in part if c.get("operator") != "=") == guard for part in parts
        )
        split_checks.append(
            {"index": i, "equalities": sum(eq_full.values()), "partition_verified": True}
        )
    stitched = []
    for group, (a, b) in enumerate(manifest["pairs"]):
        for seed in SEEDS:
            left = first_accepted(f"single-{a:02d}", seed)
            right = first_accepted(f"single-{b:02d}", seed)
            if left is None or right is None:
                stitched.append({"pair": group, "seed": seed, "available": False})
                continue
            assert not set(left) & set(right)
            for mode in ("left", "right", "sum"):
                variant = f"pair-{mode}-{group:02d}"
                try:
                    evidence = evaluate_joint(variant, left | right)
                except Exception as error:
                    evidence = {"error": repr(error), "numeric_feasible": False}
                stitched.append(
                    {"pair": group, "seed": seed, "mode": mode, "available": True, **evidence}
                )
    large_repo = [
        str(p.relative_to(HERE))
        for p in HERE.rglob("*")
        if p.is_file() and p.stat().st_size > 5_000_000
    ]
    assert not large_repo
    save(
        HERE / "audit.json",
        {
            "source_after": source,
            "input_hashes_ok": input_ok,
            "source_case_files_unchanged": input_sources_unchanged,
            "max_simultaneous_runs": max_live,
            "scheduled_receipts": len(receipts),
            "source_hash": SOURCE,
            "namespace_crossings": crossings,
            "split_checks": split_checks,
            "stitched_figure_checks": stitched,
            "repo_files_over_5MB": large_repo,
            "summary_sha256": digest((HERE / "summary.json").read_bytes()),
            "sets_sha256": digest((HERE / "sets.json").read_bytes()),
        },
    )
    print(
        json.dumps(
            {
                "audit": "passed",
                "receipts": len(receipts),
                "max_parallel": max_live,
                "stitched_available": sum(r["available"] for r in stitched),
                "stitched_passed": sum(r.get("numeric_feasible", False) for r in stitched),
            }
        )
    )


if __name__ == "__main__":
    main()
