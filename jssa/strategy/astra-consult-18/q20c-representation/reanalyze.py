"""Read-only reanalysis of old representation comparisons; write here only."""
from __future__ import annotations

import ast
import csv
import hashlib
import json
import statistics
from collections import Counter
from pathlib import Path

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[3]
SOURCES = {}


def read(path):
    p = ROOT / path
    raw = p.read_bytes()
    SOURCES[str(path)] = {"sha256": hashlib.sha256(raw).hexdigest(), "bytes": len(raw)}
    return raw.decode()


def csv_rows(path):
    return list(csv.DictReader(read(path).splitlines()))


def graph(dsl):
    expressions = {c["name"]: c["expression"] for c in dsl.get("constructions", [])}
    names = set(expressions)
    dependencies = {}
    for name, expression in expressions.items():
        tree = ast.parse(expression, mode="eval")
        dependencies[name] = {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)} & names
    depth, ancestors = {}, {}
    def visit(name, trail):
        if name in depth:
            return
        if name in trail:
            raise ValueError(f"cyclic construction {name}")
        for other in dependencies[name]:
            visit(other, trail | {name})
        depth[name] = 1 + max((depth[x] for x in dependencies[name]), default=0)
        ancestors[name] = set(dependencies[name])
        for other in dependencies[name]:
            ancestors[name] |= ancestors[other]
    for name in names:
        visit(name, set())
    return depth, ancestors


def save_csv(name, rows):
    with (OUT / name).open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)


def main():
    cases = [json.loads(line) for line in read("benchmarks/cases.jsonl").splitlines() if line]
    by_id = {c["id"]: c for c in cases}
    human = {r["case_id"]: r for r in csv_rows("jssa/difficulty/ghost-1023/human_feat.csv")}
    basins = {r["id"]: r for r in csv_rows("jssa/difficulty/minima/basins-323.csv")}
    corpus = []
    for c in cases:
        d, _ = graph(c["dsl"])
        h = human.get(c["id"], {}).get("human", "")
        br = basins.get(c["id"], {})
        corpus.append({"id": c["id"], "n_vars": len(c["dsl"].get("variables", [])),
                       "n_constructions": len(d), "named_construction_depth": max(d.values(), default=0),
                       "human": h, "baseline_p": br.get("p", ""),
                       "baseline_n_starts": br.get("n_starts", "")})
    save_csv("corpus-context.csv", corpus)
    manifest = json.loads(read("benchmarks/extra-variables/manifest.json"))
    variants = []
    checks = []
    for m in manifest:
        ident = m["id"]
        dsl0 = json.loads(read(f"benchmarks/extra-variables/dsl/{ident}.k0.json"))
        _, ancestors = graph(dsl0)
        selected = m["eligible"][:3]
        exprs = {c["name"]: c["expression"] for c in dsl0["constructions"]}
        ancestor_pairs = [(a, b) for a in selected for b in selected if a != b and a in ancestors[b]]
        for k in range(4):
            dsl = json.loads(read(f"benchmarks/extra-variables/dsl/{ident}.k{k}.json"))
            checks.append(len(dsl["variables"]) == len(dsl0["variables"]) + 2*k)
            checks.append(len(dsl["conditions"]) == len(dsl0["conditions"]) + 2*k)
        base = dict(by_id[ident]["dsl"])
        zero = dict(dsl0)
        base.pop("id", None)
        zero.pop("id", None)
        checks.append(base == zero)
        variants.append({"id": ident, "n_base": m["n_vars"],
                         "first_three": " ".join(selected),
                         "k3_ancestor_pairs": len(ancestor_pairs),
                         "pair_names": ";".join(f"{a}->{b}" for a,b in ancestor_pairs),
                         "primitive_types": ";".join(exprs[s].split("(", 1)[0] for s in selected),
                         "human": human.get(ident, {}).get("human", "")})
    save_csv("expansion-audit.csv", variants)
    pairs = []
    for r in csv_rows("jssa/difficulty/common-start/summary.csv"):
        pe, py, pz = (float(r[f"p{m}"]) for m in ["E", "Y", "Z"])
        pairs.append({"id": r["case_id"], "source": "common-start-k3", "N": int(r["n_x"]),
                      "pE": pe, "pY": py, "pZ": pz,
                      "Y_minus_E": py-pe, "range_EYZ": max(pe,py,pz)-min(pe,py,pz),
                      "human": human.get(r["case_id"], {}).get("human", "")})
    summary_mismatches = []
    for p in sorted((ROOT / "jssa/difficulty/holdout-1023/out").glob("*.json")):
        data = json.loads(read(p.relative_to(ROOT)))
        counts = {m: sum(r[m]["cls"] == "hit" for r in data["rows"]) for m in ["E","Y","Z"]}
        count = len(data["rows"])
        rates = {m: counts[m]/count for m in counts}
        for m in counts:
            if abs(rates[m] - data["summary"][m]["p"]) > 1e-12:
                summary_mismatches.append([data["case_id"], m])
        pe,py,pz = (rates[m] for m in ["E","Y","Z"])
        pairs.append({"id": data["case_id"], "source": "holdout-k2", "N": count,
                      "pE": pe, "pY": py, "pZ": pz,
                      "Y_minus_E": py-pe, "range_EYZ": max(pe,py,pz)-min(pe,py,pz),
                      "human": human.get(data["case_id"], {}).get("human", "")})
    save_csv("existing-paired-effects.csv", pairs)
    groups = {}
    for source in sorted({r["source"] for r in pairs}):
        rs = [r for r in pairs if r["source"] == source]
        groups[source] = {
            "problems": len(rs), "starts_per_representation": sum(r["N"] for r in rs),
            "human_labels": sum(bool(r["human"]) for r in rs),
            "median_pE": statistics.median(r["pE"] for r in rs),
            "median_pY": statistics.median(r["pY"] for r in rs),
            "median_pZ": statistics.median(r["pZ"] for r in rs),
            "Y_decrease_at_least_0p2": sum(r["Y_minus_E"] <= -.2+1e-12 for r in rs),
            "Y_increase_at_least_0p1": sum(r["Y_minus_E"] >= .1-1e-12 for r in rs),
            "max_representation_range": max(r["range_EYZ"] for r in rs),
        }
    summary = {
        "corpus_problems": len(corpus),
        "with_variables": sum(r["n_vars"] > 0 for r in corpus),
        "human_labels": sum(bool(r["human"]) for r in corpus),
        "max_named_construction_depth": max(r["named_construction_depth"] for r in corpus),
        "median_named_construction_depth": statistics.median(r["named_construction_depth"] for r in corpus),
        "depth_max_ids": [r["id"] for r in corpus if r["named_construction_depth"] == max(s["named_construction_depth"] for s in corpus)],
        "depth_definition": "longest path of named constructions, counting root as depth 1; nested calls are not separate nodes",
        "extra_variable_problems": len(variants), "variant_inputs": 4*len(variants),
        "all_variant_count_and_k0_identity_checks_passed": all(checks),
        "k3_no_ancestor_pair_among_selected": sum(r["k3_ancestor_pairs"] == 0 for r in variants),
        "paired_groups": groups,
        "paired_unique_problems": len({r["id"] for r in pairs}),
        "holdout_raw_summary_mismatches": summary_mismatches,
        "interpretation": "Old descriptive data, not independent confirmation of the new linear-chain mechanism; no correlations calculated.",
    }
    (OUT / "existing-summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2)+"\n")
    (OUT / "source-hashes.json").write_text(json.dumps(SOURCES, ensure_ascii=False, indent=2)+"\n")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
