#!/usr/bin/env python3
"""Input-only S9B properties; never run search or read S8 outcomes.

Run with a Python environment containing the project's compilation dependencies.
--check recomputes everything and compares the saved artifacts without writing.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import importlib.metadata
import io
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
from collections import Counter

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[4]
BASE = "jssa/difficulty/mechanism-1024"
ASSIGNMENT = f"{BASE}/stage/S8/assignment.json"
S8 = (ROOT / BASE / "stage/S8").resolve()
FROZEN = "60db4b679b04167175c51c479c87c22fa663fda0"
P0 = "jssa/difficulty/start-feasibility-1023/per-problem.csv"
P1 = "jssa/difficulty/start-feasibility-1023/per-problem-seed1.csv"
BASINS = "jssa/difficulty/minima/basins-323.csv"
SYMMETRY = "jssa/difficulty/symmetry-break/per-problem.csv"
KINDS = ("guard", "line_distinct", "triangle_nondegenerate",
         "intersection_exclude_distinct", "intersection_selection_trace")
READS: dict[str, str] = {}
THREADS = ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS",
           "NUMEXPR_NUM_THREADS", "VECLIB_MAXIMUM_THREADS", "BLIS_NUM_THREADS")
for key in THREADS:
    os.environ[key] = "1"
sys.dont_write_bytecode = True


def guard_s8(event, args):
    """Deny every S8 open/traversal except the explicitly authorized roster."""
    if event not in {"open", "os.listdir", "os.scandir"} or not args:
        return
    value = args[0]
    if not isinstance(value, (str, bytes, os.PathLike)):
        return
    path = Path(os.fsdecode(value)).resolve()
    if path == S8 or S8 in path.parents:
        if event != "open" or path != ROOT / ASSIGNMENT:
            raise PermissionError(f"S9B prohibits access to {path}")
        mode = args[1]
        flags = args[2]
        if (isinstance(mode, str) and any(c in mode for c in "wax+")) or (
            isinstance(flags, int) and flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT)
        ):
            raise PermissionError("The S8 roster is read-only")


sys.addaudithook(guard_s8)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def read(relative):
    path = ROOT / relative
    raw = path.read_bytes()
    READS[relative] = sha(raw)
    return raw


def js(raw):
    return json.loads(raw)


def json_bytes(value):
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode()


def table(relative):
    rows = list(csv.DictReader(io.StringIO(read(relative).decode())))
    result = {r["id"]: (index + 2, r) for index, r in enumerate(rows)}
    assert len(result) == len(rows), f"Duplicate IDs: {relative}"
    return result


def fraction(row):
    starts = int(row["starts"])
    assert starts == int(row["n_feas"]) + int(row["n_infeas"]) > 0
    hits = int(row["hit_feas"]) + int(row["hit_infeas"])
    p = float(row["p"])
    assert 0 <= hits <= starts and p == hits / starts
    return hits, starts, p


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()

    # Check the compiler path against the frozen version before importing it.
    critical = [
        "src/geosolver/problem/models.py", "src/geosolver/problem/adapter.py",
        "src/geosolver/problem/compiler.py", "src/geosolver/problem/domain_bounds.py",
        "src/geosolver/problem/construction_contracts.py",
        "src/geosolver/problem/incidence_residuals.py",
        "src/geosolver/problem/logical_equalities.py",
        "src/geosolver/engine/standard/problem/load_problem_bundle.py",
        "src/geosolver/engine/standard/problem/compile_problem_hard_feasibility.py",
        "src/geosolver/engine/standard/evaluation/_hard_feasibility_core.py",
        "src/geosolver/engine/standard/search/scipy_multistart_backend.py",
    ]
    frozen_match = {}
    for relative in critical:
        current = read(relative)
        frozen = subprocess.run(["git", "show", f"{FROZEN}:{relative}"],
                                cwd=ROOT, check=True, capture_output=True).stdout
        assert current == frozen, f"Compiler changed from frozen version: {relative}"
        frozen_match[relative] = sha(frozen)

    sys.path.insert(0, str(ROOT / "src"))
    from geosolver.problem.models import GeometryProblem
    from geosolver.engine.standard.problem.load_problem_bundle import load_problem_bundle

    # Project the roster immediately; ignore machine, rankings and other metadata.
    roster = [{k: r[k] for k in ("case_id", "cohort", "dsl_path", "input_sha256")}
              for r in js(read(ASSIGNMENT))["problems"]]
    roster.sort(key=lambda r: r["case_id"])
    assert len(roster) == len({r["case_id"] for r in roster}) == 106
    assert Counter(r["cohort"] for r in roster) == {"mechanism72": 72, "unseen34": 34}
    # Independent membership sources. Neither contains S8 outcomes.
    mechanism = js(read(f"{BASE}/problem-set/problem-set.json"))
    mechanism_ids = {cid for key in ("hard", "fast_algebraic", "fast_search", "multivalued")
                     for cid in mechanism[key]}
    assert mechanism_ids == {r["case_id"] for r in roster if r["cohort"] == "mechanism72"}
    cases = {c["id"]: c for c in map(json.loads, read("benchmarks/cases.jsonl").splitlines())}
    p0, p1, basins, symmetry = map(table, (P0, P1, BASINS, SYMMETRY))

    rows, details, p_sources = [], [], []
    for item in roster:
        cid = item["case_id"]
        raw = read(item["dsl_path"])
        assert sha(raw) == item["input_sha256"], f"Input hash changed: {cid}"
        dsl = js(raw)
        assert dsl["id"] == cid
        bundle = load_problem_bundle(GeometryProblem.model_validate(dsl).engine_document())
        conditions = dsl["conditions"]
        n_eq = sum(c.get("operator") == "=" for c in conditions)
        n_rel = sum(c.get("operator") in {"!=", "<", "<=", ">", ">="} for c in conditions)
        n_pred = sum("predicate" in c for c in conditions)
        ng = n_rel + n_pred
        assert n_eq + ng == len(conditions)
        kinds = Counter(c.kind for c in bundle.hard_feasibility_checks)
        assert set(kinds) <= set(KINDS)
        row = dict(case_id=cid, cohort=item["cohort"], dsl_path=item["dsl_path"],
                   input_sha256=item["input_sha256"], n_search_variables=len(bundle.var_names),
                   n_dsl_variables=len(dsl["variables"]), n_constraints=len(conditions),
                   n_equalities=n_eq, n_relation_inequalities=n_rel, n_predicate_guards=n_pred,
                   n_inequality_guards=ng,
                   inequality_guard_fraction=repr(ng / len(conditions)) if conditions else "NA",
                   n_compiled_guards=len(bundle.spec.guards),
                   n_compiled_equalities=len(bundle.spec.constraints),
                   n_wall_conditions=len(bundle.hard_feasibility_checks),
                   **{f"n_wall_{kind}": kinds[kind] for kind in KINDS},
                   n_constructions=len(dsl["constructions"]),
                   wall_evaluation_status_gate="global_not_in_n_wall_conditions",
                   p="NA", p_seed=0, p_hits="NA", p_starts="NA", p_source="NA",
                   p_source_row="NA", p_source_column="NA", p_na_reason="no_existing_record",
                   p_seed1="NA", p_seed1_hits="NA", p_seed1_starts="NA",
                   p_seed1_source="NA", p_seed1_source_row="NA", p_symmetry_original="NA")
        if cid in p0:
            line, old = p0[cid]
            assert cases[cid]["dsl"] == dsl, f"p measured for different input: {cid}"
            assert read(str(Path("benchmarks") / cases[cid]["dsl_path"])) == raw
            hits, starts, p = fraction(old)
            assert int(old["n_vars"]) == len(bundle.var_names)
            assert int(old["n_checks"]) == len(bundle.hard_feasibility_checks)
            # S4.1's original local-search summary and S5.1 agree exactly here.
            bline, b = basins[cid]
            assert b["status"] == "ok" and float(b["p"]) == p and int(b["n_starts"]) == starts
            row.update(p=repr(p), p_hits=hits, p_starts=starts, p_source=P0,
                       p_source_row=line, p_source_column="p", p_na_reason="NA")
            p_sources.append(dict(case_id=cid, source=P0, row=line, column="p", role="primary",
                                  hits=hits, starts=starts, value=p))
            p_sources.append(dict(case_id=cid, source=BASINS, row=bline, column="p", role="cross_check",
                                  hits=hits, starts=starts, value=p))
        if cid in p1:
            assert cid in p0
            line, old = p1[cid]
            hits, starts, p = fraction(old)
            row.update(p_seed1=repr(p), p_seed1_hits=hits, p_seed1_starts=starts,
                       p_seed1_source=P1, p_seed1_source_row=line)
            p_sources.append(dict(case_id=cid, source=P1, row=line, column="p", role="seed1_supplement",
                                  hits=hits, starts=starts, value=p))
        if cid in symmetry:
            line, old = symmetry[cid]
            row["p_symmetry_original"] = old["p_original"]
            p_sources.append(dict(case_id=cid, source=SYMMETRY, row=line, column="p_original",
                                  role="different_protocol_supplement", value=float(old["p_original"])))
        details.append(dict(case_id=cid, input_sha256=item["input_sha256"],
                            dsl_variables=dsl["variables"], search_variables=list(bundle.var_names),
                            conditions=conditions, compiled_guards=list(bundle.spec.guards),
                            compiled_constructions=[dict(name=c.name, expression=c.expr)
                                                    for c in bundle.spec.construction],
                            wall_checks=[dict(check_id=c.check_id, kind=c.kind,
                                              symbol_names=list(c.symbol_names),
                                              reference_symbol=c.reference_symbol)
                                         for c in bundle.hard_feasibility_checks]))
        rows.append(row)

    # Provenance is limited to inputs, designated old local-search records, code and definitions.
    documents = [f"{BASE}/stage/S3/preregistration-15.md", f"{BASE}/stage/S3/preregistration-16.md",
                 "jssa/draft/supplement-v14.md", "jssa/difficulty/start-feasibility-1023/README.md",
                 "jssa/difficulty/start_feasibility.py", "jssa/difficulty/probe_basins.py",
                 "jssa/difficulty/symmetry-break/local_stage2.py",
                 "jssa/strategy/astra-consult-17/G/census.py",
                 str(OUT.relative_to(ROOT) / "build_properties.py"),
                 str(OUT.relative_to(ROOT) / "README.md")]
    for relative in documents:
        read(relative)
    for name, module in sorted(sys.modules.items()):
        path = getattr(module, "__file__", None)
        if name.startswith("geosolver") and path:
            path = Path(path).resolve()
            if path.suffix == ".py":
                read(str(path.relative_to(ROOT)))
    assert [p for p in READS if "/stage/S8/" in p] == [ASSIGNMENT]
    assert all(r["p"] != "NA" for r in rows if r["cohort"] == "mechanism72")
    assert all(r["p"] == "NA" for r in rows if r["cohort"] == "unseen34")
    output = io.StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=list(rows[0]), lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    validation = dict(n_problems=len(rows), cohorts=dict(Counter(r["cohort"] for r in rows)),
                      p_available=sum(r["p"] != "NA" for r in rows),
                      p_na=sum(r["p"] == "NA" for r in rows),
                      p_seed1_available=sum(r["p_seed1"] != "NA" for r in rows),
                      p_symmetry_original_available=sum(r["p_symmetry_original"] != "NA" for r in rows),
                      zero_search_variables=sum(r["n_search_variables"] == 0 for r in rows),
                      zero_constraint_rows=sum(r["n_constraints"] == 0 for r in rows),
                      compiled_guard_count_differs_from_dsl=sum(r["n_compiled_guards"] != r["n_inequality_guards"] for r in rows),
                      primary_p_matches_basins=72, wall_counts_match_existing_S5_1=72,
                      search_variables_match_dsl=all(r["n_search_variables"] == r["n_dsl_variables"] for r in rows),
                      s8_read_allowlist=[ASSIGNMENT], s8_outcomes_read=False,
                      result_groups_created=False, solver_search_runs=0,
                      calculation_parallelism=1, max_parallelism_authorized=4)
    manifest = dict(schema_version=1, frozen_compilation_commit=FROZEN,
                    compiler_byte_matches_frozen=frozen_match, source_files_sha256=dict(sorted(READS.items())),
                    python_version=platform.python_version(),
                    dependencies={name: importlib.metadata.version(name)
                                  for name in ("pydantic", "mpmath", "numpy", "sympy")},
                    p_primary_rule="S5.1 seed 0 p; no pooling; exact case ID and identical DSL",
                    s8_policy="Only assignment.json, projected to roster fields; all other S8 opens/traversal denied")
    artifacts = {"inputs.json": json_bytes(roster), "properties.csv": output.getvalue().encode(),
                 "condition-details.json": json_bytes(details), "p-provenance.json": json_bytes(p_sources),
                 "validation.json": json_bytes(validation), "source-hashes.json": json_bytes(manifest)}
    for name, raw in artifacts.items():
        if args.check:
            assert (OUT / name).read_bytes() == raw, f"Reproduction mismatch: {name}"
        else:
            (OUT / name).write_bytes(raw)
    hashes = {name: sha(raw) for name, raw in artifacts.items()}
    hashes.update({name: sha((OUT / name).read_bytes()) for name in ("README.md", "build_properties.py")})
    receipt = json_bytes(hashes)
    if args.check:
        assert (OUT / "artifact-hashes.json").read_bytes() == receipt
    else:
        (OUT / "artifact-hashes.json").write_bytes(receipt)
    print(json.dumps(dict(mode="check" if args.check else "build", **validation), ensure_ascii=False))


if __name__ == "__main__":
    main()
