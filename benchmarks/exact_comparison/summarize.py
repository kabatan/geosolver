"""Collect screen, exact and GeoSolver runs into one table (JSON + Markdown)."""

import json
import statistics
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from run_exact import load_case, reference_values, same_set  # noqa: E402


def load_dir(d):
    out = {}
    if d and Path(d).exists():
        for f in Path(d).glob("*.json"):
            try:
                rec = json.loads(f.read_text())
            except json.JSONDecodeError:
                continue
            out[rec["id"]] = rec
    return out


def decimal_of(value):
    if isinstance(value, dict):
        if "decimal" in value:
            return float(value["decimal"])
        for v in value.values():
            r = decimal_of(v)
            if r is not None:
                return r
    return None


def geosolver_runs(d, cid):
    runs = []
    for seed in (0, 1, 2):
        f = Path(d) / f"{cid}.{seed}.json"
        if not f.exists():
            continue
        r = json.loads(f.read_text())
        answers = sorted(decimal_of(a.get("value", a)) for a in r.get("answers", []) if decimal_of(a.get("value", a)) is not None)
        runs.append({"seed": seed, "status": r["status"], "seconds": r["elapsed_seconds"],
                     "answers": answers})
    return runs


def classify(rec):
    if rec is None:
        return "not_run"
    if rec.get("status") == "unsupported":
        return "unsupported"
    if not rec.get("nvars"):
        return "no_unknowns"
    st = rec.get("solve_status", "")
    if "timeout" in st:
        return "timeout"
    if st.startswith("error"):
        return "error"
    if st == "ok":
        if rec.get("answer_set_matches"):
            return "answer_set_matches"
        return "free_parameter" if rec.get("free_dsl_vars") else "answer_set_differs"
    return st


def main():
    screen, sample_file, exact_dirs, gs_dir, out = sys.argv[1:6]
    screen = load_dir(screen)
    exact = {name: load_dir(path) for name, path in
             (p.split("=") for p in exact_dirs.split(","))}
    ids = [line.strip() for line in open(sample_file) if line.strip()]
    rows = []
    for cid in ids:
        case = load_case(cid)
        ref = reference_values(case)
        row = {"id": cid, "dsl_vars": len(case["dsl"]["variables"]), "reference": ref,
               "screen": classify(screen.get(cid))}
        for name, recs in exact.items():
            rec = recs.get(cid)
            row[name] = {"class": classify(rec), **({k: rec.get(k) for k in (
                "nvars", "neqs", "degrees", "bezout", "translate_seconds", "solve_seconds",
                "filter_seconds", "real_solutions", "verified_configurations", "answers",
                "free_dsl_vars", "candidate_values", "reference_among_candidates",
                "solve_status", "reason")} if rec else {})}
        runs = geosolver_runs(gs_dir, cid)
        row["geosolver"] = runs
        row["geosolver_matches"] = [same_set(r["answers"], ref) for r in runs]
        rows.append(row)
    Path(out).write_text(json.dumps(rows, indent=1, default=str))


if __name__ == "__main__":
    main()
