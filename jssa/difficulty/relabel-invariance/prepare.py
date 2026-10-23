"""Q38 stage 1 only: transform, statically verify, and seal; never run a solver.

Run with Python 3.12 and the existing pydantic dependency. All child processes
are read-only git queries. Public DSL validation/compilation is not a solve.
"""

from __future__ import annotations

import argparse
import ast
import copy
import csv
import hashlib
import importlib.metadata
import io
import json
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
RULES = json.loads((HERE / "rules.json").read_text())
FROZEN = RULES["frozen_commit"]
SOURCES = [
    "benchmarks/cases.jsonl",
    "benchmarks/research_runner.py",
    "jssa/difficulty/minima/basins-323.csv",
    "jssa/strategy/codex-tasks-1023.md",
    "jssa/strategy/gpt-pro-consult-12-prompt.md",
    "jssa/difficulty/fractal-basins/prediction.md",
    "jssa/difficulty/fractal-basins/local-summary.json",
    "jssa/difficulty/fractal-basins/full-summary.json",
    "pyproject.toml",
    "uv.lock",
]
SNAPSHOTS = {
    "jssa/difficulty/fractal-basins/prediction.md": "evidence/q34-prediction.md",
    "jssa/difficulty/fractal-basins/local-summary.json": "evidence/q34-local-summary.json",
    "jssa/difficulty/fractal-basins/full-summary.json": "evidence/q34-full-summary.json",
}


def canonical(value):
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False
    )


def digest(data):
    return hashlib.sha256(data).hexdigest()


def sha(path):
    return digest(path.read_bytes())


def rank(salt, value):
    return digest(f"{salt}|{value}".encode())


def git(*args):
    return subprocess.check_output(["git", *args], cwd=ROOT, timeout=30).decode().strip()


def write(path, text):
    payload = text.encode("utf-8")
    if len(payload) >= RULES["file_limit_bytes"]:
        raise ValueError(f"file too large: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload)


def write_json(path, value):
    write(path, json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n")


def write_csv(path, rows):
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
    writer.writeheader()
    writer.writerows(rows)
    write(path, stream.getvalue())


def check_frozen():
    # Refuse changes even if the current repository HEAD is newer than FROZEN.
    for p in [
        "src",
        "benchmarks/research_runner.py",
        "benchmarks/cases.jsonl",
        "pyproject.toml",
        "uv.lock",
    ]:
        if git("diff", FROZEN, "--", p):
            raise ValueError(f"different from frozen commit: {p}")
    if git("ls-files", "--others", "--exclude-standard", "src"):
        raise ValueError("untracked source under src")


def point_names(dsl):
    names = []
    for c in dsl["constructions"]:
        root = ast.parse(c["expression"], mode="eval").body
        if (
            isinstance(root, ast.Call)
            and isinstance(root.func, ast.Name)
            and root.func.id in RULES["point_roots"]
        ):
            names.append(c["name"])
    return names


def replace_names(source, mapping):
    """Replace only bound ast.Name occurrences, preserving every other byte.

    ast column positions are UTF-8 byte positions. Strings, selector literals,
    attributes and keyword labels are not Name nodes and are never rewritten.
    """
    tree = ast.parse(source, mode="eval")
    calls = {id(n.func) for n in ast.walk(tree) if isinstance(n, ast.Call)}
    lines = source.encode().splitlines(keepends=True)
    offsets = [0]
    for line in lines:
        offsets.append(offsets[-1] + len(line))
    edits = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and node.id in mapping:
            if id(node) in calls:
                raise ValueError("bound name collides with callable name")
            a = offsets[node.lineno - 1] + node.col_offset
            b = offsets[node.end_lineno - 1] + node.end_col_offset
            edits.append((a, b, mapping[node.id].encode()))
    raw = source.encode()
    for a, b, replacement in sorted(edits, reverse=True):
        raw = raw[:a] + replacement + raw[b:]
    return raw.decode()


def rename(dsl, mapping):
    d = copy.deepcopy(dsl)
    d["variables"] = [mapping.get(n, n) for n in d["variables"]]
    for c in d["constructions"]:
        c["name"] = mapping.get(c["name"], c["name"])
        c["expression"] = replace_names(c["expression"], mapping)
    for c in d["conditions"]:
        for key in ("left", "right", "predicate"):
            if key in c and isinstance(c[key], str):
                c[key] = replace_names(c[key], mapping)
    d["target"] = replace_names(d["target"], mapping)
    return d


def hashed_order(length, salt):
    order = sorted(range(length), key=lambda i: (rank(salt, i), i))
    if order == list(range(length)) and length > 1:
        order = order[1:] + order[:1]
    return order


def transform(dsl, mode):
    d = copy.deepcopy(dsl)
    points = point_names(dsl)
    mapping = {}
    v_order = list(range(len(d["variables"])))
    c_order = list(range(len(d["conditions"])))
    k_order = list(range(len(d["constructions"])))
    if mode in ("point_names", "combined"):
        if len(points) < 2:
            raise ValueError("fewer than two eligible point names")
        # A cyclic bijection within existing point names: no fresh identifier.
        mapping = dict(zip(points, points[1:] + points[:1], strict=True))
        d = rename(d, mapping)
    if mode in ("variable_order", "orders_combined", "combined"):
        v_order = (
            list(reversed(v_order))
            if mode != "combined"
            else hashed_order(len(v_order), f"Q38/variables/v1/{dsl['id']}")
        )
        d["variables"] = [d["variables"][i] for i in v_order]
    if mode in ("condition_order", "orders_combined", "combined"):
        c_order = (
            list(reversed(c_order))
            if mode != "combined"
            else hashed_order(len(c_order), f"Q38/conditions/v1/{dsl['id']}")
        )
        d["conditions"] = [d["conditions"][i] for i in c_order]
    # The construction list itself is immutable in all five interventions.
    return d, {
        "point_bijection": mapping,
        "inverse_point_bijection": {v: k for k, v in mapping.items()},
        "variable_new_to_old": v_order,
        "condition_new_to_old": c_order,
        "construction_new_to_old": k_order,
    }


def expression_key(value):
    if not isinstance(value, str):
        return [type(value).__name__, value]
    tree = ast.parse(value, mode="eval")
    # Keep the spelling of every numeric literal, in addition to the AST.
    lexemes = [
        ast.get_source_segment(value, n)
        for n in ast.walk(tree)
        if isinstance(n, ast.Constant) and type(n.value) in (int, float)
    ]
    return ["expression", ast.dump(tree, include_attributes=False), lexemes]


def signature(dsl):
    equalities, inequalities, predicates = [], [], []
    for c in dsl["conditions"]:
        if "predicate" in c:
            predicates.append(canonical(expression_key(c["predicate"])))
        else:
            row = canonical([c["operator"], expression_key(c["left"]), expression_key(c["right"])])
            (equalities if c["operator"] == "=" else inequalities).append(row)
    return {
        "id": dsl["id"],
        "variables": sorted(dsl["variables"]),
        "constructions": sorted(
            [c["name"], expression_key(c["expression"])] for c in dsl["constructions"]
        ),
        "equalities_multiset": sorted(equalities),
        "inequalities_multiset": sorted(inequalities),
        "predicates_multiset": sorted(predicates),
        "target": expression_key(dsl["target"]),
    }


def verify_equivalence(original, transformed, mapping):
    normalized = rename(transformed, mapping["inverse_point_bijection"])
    if normalized["constructions"] != original["constructions"]:
        raise ValueError("construction order or expression changed")
    first, second = signature(original), signature(normalized)
    if first != second:
        raise ValueError("AST alpha-equivalence/multiset check failed")
    # A second independent invariant: undo all list permutations and compare
    # the entire original document, including literal types and exact strings.
    recovered = copy.deepcopy(normalized)
    for field, key in [
        ("variables", "variable_new_to_old"),
        ("conditions", "condition_new_to_old"),
        ("constructions", "construction_new_to_old"),
    ]:
        order = mapping[key]
        if sorted(order) != list(range(len(recovered[field]))):
            raise ValueError("invalid permutation")
        recovered[field] = [normalized[field][order.index(i)] for i in range(len(order))]
    if recovered != original:
        raise ValueError("exact inverse transformation failed")
    return digest(canonical(first).encode())


def selection():
    cases = {c["id"]: c for c in map(json.loads, (ROOT / SOURCES[0]).read_text().splitlines())}
    rows = list(csv.DictReader((ROOT / SOURCES[2]).open()))
    groups, inventory = {}, []
    for r in rows:
        cid = r["id"]
        n = int(r["n_vars"] or 0)
        reason = ""
        if cid not in cases:
            reason = "not_in_development_corpus"
        elif r["status"] != "ok":
            reason = "basins_status_not_ok"
        elif n < RULES["minimum_variables"]:
            reason = "fewer_than_two_variables"
        if not reason and n != len(cases[cid]["dsl"]["variables"]):
            raise ValueError("declared/basins dimension mismatch")
        p = float(r["p"]) if r["p"] else None
        ns = "n2-3" if n <= 3 else "n4+"
        ps = (
            "p0"
            if p == 0
            else "p0-0.1"
            if p is not None and p < 0.1
            else "p0.1-0.9"
            if p is not None and p < 0.9
            else "p0.9-1"
        )
        row = {
            "id": cid,
            "n_vars": n,
            "p_existing": r["p"],
            "n_starts_existing": r["n_starts"],
            "dimension_stratum": ns,
            "p_stratum": ps,
            "selection_sha256": rank(RULES["selection_salt"], cid),
            "eligible": not reason,
            "reason": reason,
            "rank_in_stratum": "",
            "selected": False,
        }
        inventory.append(row)
        if not reason:
            groups.setdefault((ns, ps), []).append(row)
    chosen = []
    for ns in RULES["dimension_strata"]:
        for ps in RULES["p_strata"]:
            group = sorted(groups[(ns, ps)], key=lambda r: (r["selection_sha256"], r["id"]))
            if len(group) < RULES["per_stratum"]:
                raise ValueError("insufficient stratum; stop, do not substitute")
            for i, row in enumerate(group, 1):
                row["rank_in_stratum"] = i
                row["selected"] = i <= RULES["per_stratum"]
                if row["selected"]:
                    chosen.append(row)
    if len(chosen) != 40:
        raise ValueError("expected 40 problems")
    return cases, chosen, sorted(inventory, key=lambda r: r["id"])


def execution_plan(chosen):
    ids = sorted((r["id"] for r in chosen), key=lambda c: (rank("Q38/blocks/v1", c), c))
    batches = []
    modes = RULES["modes"] + ["original_repeat"]
    # 10 four-problem blocks, each with all three seeds and all seven modes.
    for block in range(10):
        problem_ids = ids[4 * block : 4 * block + 4]
        for seed in RULES["seeds"]:
            order = sorted(modes, key=lambda m: (rank(f"Q38/schedule/v1/{block}/{seed}", m), m))
            for mode in order:
                corpus_mode = "original" if mode == "original_repeat" else mode
                corpus = f"jssa/difficulty/relabel-invariance/inputs/{corpus_mode}/cases.jsonl"
                dest = f"<external-results-root>/b{block:02d}-s{seed}-{mode}"
                argv = [
                    "prlimit",
                    "--fsize=4900000:4900000",
                    "--",
                    "<verified-python3.12>",
                    "-B",
                    "-m",
                    "benchmarks.research_runner",
                    "run",
                    dest,
                    "--cases",
                    corpus,
                    "--seeds",
                    str(seed),
                    "--jobs",
                    "4",
                ]
                for cid in problem_ids:
                    argv += ["--case-id", cid]
                batches.append(
                    {
                        "batch": len(batches),
                        "block": block,
                        "seed": seed,
                        "mode": mode,
                        "case_ids": problem_ids,
                        "destination": dest,
                        "cases": corpus,
                        "run_argv_after_separate_authorization": argv,
                    }
                )
    return {
        "stage": 1,
        "execution_authorized": False,
        "gate": (
            "User confirms prediction commit AND push, then explicitly authorizes a separate task."
        ),
        "required_clean_checkout": True,
        "allow_dirty": False,
        "final_result_directory": "jssa/difficulty/relabel-invariance/results/",
        "result_staging": (
            "Outside checkout until all batches and assessments finish, so git stays clean."
        ),
        "environment": {
            "PYTHONHASHSEED": "0",
            "PYTHONPATH": "src",
            "OMP_NUM_THREADS": "1",
            "OPENBLAS_NUM_THREADS": "1",
            "MKL_NUM_THREADS": "1",
            "NUMEXPR_NUM_THREADS": "1",
            "PYTHONDONTWRITEBYTECODE": "1",
        },
        "main_runs": 720,
        "identical_baseline_repeats": 120,
        "total_runs": 840,
        "batches": batches,
    }


def public_validate(dsl):
    from geosolver.problem.models import GeometryProblem
    from geosolver.problem.validation import validate

    report = validate(GeometryProblem.model_validate(dsl))
    if not report.valid:
        raise ValueError(str(report.issues))


def check_modules():
    # The allowed public compiler is static. Abort if a search/service module
    # ever gets imported by a future dependency change.
    prohibited = [
        n
        for n in sys.modules
        if n.startswith(("geosolver.engine", "geosolver.application", "benchmarks.research_runner"))
    ]
    if prohibited:
        raise ValueError(f"unexpected solver/runner imports: {prohibited}")


def equivalence_controls():
    """Small static controls for changes the equivalence gate must reject."""
    original = {
        "id": "Q38-static-control",
        "variables": ["u", "v"],
        "constructions": [
            {"name": "A", "expression": "Point(0, 0)"},
            {"name": "B", "expression": "Point(u, v)"},
            {"name": "C", "expression": "Intersect(Circle(A, 1), Line(A, B), n=1)"},
        ],
        "conditions": [
            {"left": "u", "operator": ">", "right": 0},
            {"left": "Distance(A, B)", "operator": "=", "right": "1.0000000000000001"},
        ],
        "target": "Distance(A, C)",
    }
    transformed, mapping = transform(original, "combined")
    verify_equivalence(original, transformed, mapping)
    rejected = []
    for label in (
        "target",
        "operator",
        "condition_removed",
        "condition_duplicated",
        "numeric_lexeme",
        "intersection_selector",
        "non_bijective_binding",
    ):
        bad = copy.deepcopy(transformed)
        if label == "target":
            bad["target"] = "0"
        elif label == "operator":
            next(c for c in bad["conditions"] if c.get("operator") == ">")["operator"] = ">="
        elif label == "condition_removed":
            bad["conditions"].pop()
        elif label == "condition_duplicated":
            bad["conditions"].append(copy.deepcopy(bad["conditions"][0]))
        elif label == "numeric_lexeme":
            # Both decimal tokens parse to the SAME Python float; a plain
            # ast.dump check would miss the changed exact decimal input.
            next(c for c in bad["conditions"] if c.get("operator") == "=")["right"] = "1.0"
        elif label == "intersection_selector":
            c = next(c for c in bad["constructions"] if "Intersect(" in c["expression"])
            c["expression"] = c["expression"].replace("n=1", "n=2")
        else:
            bad["constructions"][0]["name"] = bad["constructions"][1]["name"]
        try:
            verify_equivalence(original, bad, mapping)
        except (ValueError, IndexError):
            rejected.append(label)
        else:
            raise ValueError(f"failed to reject control: {label}")
    mapping = {"A": "B", "B": "A"}
    expressions = {
        "Midpoint(A=A, B=B)": "Midpoint(A=B, B=A)",
        "IncircleContactPoint(A, B, C, vertex='A')": "IncircleContactPoint(B, A, C, vertex='A')",
        "Point(A.x, AA.y)": "Point(B.x, AA.y)",
        "Point(1.2300e-4 * A.x, B.y)": "Point(1.2300e-4 * B.x, A.y)",
    }
    for source, expected in expressions.items():
        if replace_names(source, mapping) != expected:
            raise ValueError("token-preservation control failed")
    return {
        "solver_calls": 0,
        "numeric_evaluations": 0,
        "positive_roundtrip": True,
        "rejected_mutations": rejected,
        "preserved_token_controls": len(expressions),
    }


def prepare():
    if (HERE / "prediction.lock.json").exists():
        raise ValueError("already sealed; do not regenerate")
    check_frozen()
    for source, target in SNAPSHOTS.items():
        write(HERE / target, (ROOT / source).read_text())
    cases, chosen, inventory = selection()
    write_csv(HERE / "selection.csv", chosen)
    write_csv(HERE / "selection-universe.csv", inventory)
    transformations, checks, corpus_rows = [], [], {m: [] for m in RULES["modes"]}
    for r in chosen:
        case = cases[r["id"]]
        original = case["dsl"]
        seen = set()
        for mode in RULES["modes"]:
            dsl, mapping = transform(original, mode)
            normal_hash = verify_equivalence(original, dsl, mapping)
            public_validate(dsl)
            fingerprint = canonical(dsl)
            if fingerprint in seen:
                raise ValueError(f"identity/duplicate variant: {r['id']} {mode}")
            seen.add(fingerprint)
            path = HERE / "inputs" / mode / "dsl" / f"{r['id']}.json"
            write_json(path, dsl)
            corpus_rows[mode].append(
                {
                    "id": case["id"],
                    "dsl": dsl,
                    "dsl_path": f"dsl/{r['id']}.json",
                    "answer": case["answer"],
                    "source": case["source"],
                    "authoring_status": "runnable",
                    "truth_status": "verified",
                    "dedupe_key": case.get("dedupe_key", case["id"]),
                }
            )
            transformations.append(
                {
                    "id": r["id"],
                    "mode": mode,
                    "dsl_path": str(path.relative_to(HERE)),
                    "dsl_sha256": sha(path),
                    **mapping,
                }
            )
            counts = signature(original)
            checks.append(
                {
                    "id": r["id"],
                    "mode": mode,
                    "public_dsl_valid": True,
                    "inverse_exact": True,
                    "alpha_ast_equal": True,
                    "normal_form_sha256": normal_hash,
                    "variables": r["n_vars"],
                    "point_names": len(point_names(original)),
                    "equalities": len(counts["equalities_multiset"]),
                    "inequalities": len(counts["inequalities_multiset"]),
                    "predicates": len(counts["predicates_multiset"]),
                }
            )
    for mode, rows in corpus_rows.items():
        write(HERE / "inputs" / mode / "cases.jsonl", "".join(canonical(r) + "\n" for r in rows))
    check_modules()
    write_json(HERE / "transformations.json", transformations)
    write_json(HERE / "equivalence-controls.json", equivalence_controls())
    write_json(HERE / "execution-plan.json", execution_plan(chosen))
    write_json(
        HERE / "static-validation.json",
        {
            "method": (
                "public DSL validation/compiler, inverse-byte restoration "
                "and AST multiset comparison"
            ),
            "python": sys.version.split()[0],
            "pydantic": importlib.metadata.version("pydantic"),
            "problems": 40,
            "transformed_dsls": 200,
            "original_dsls": 40,
            "validated_documents": 240,
            "solver_calls": 0,
            "numeric_substitution_performed": False,
            "notes": (
                "Mathematical equivalence proved structurally; "
                "no new existence claim for original DSLs."
            ),
            "checks": checks,
        },
    )
    source_files = git("ls-tree", "-r", "--name-only", FROZEN, "src").splitlines()
    write_json(
        HERE / "source-manifest.json",
        {
            "frozen_commit": FROZEN,
            "preparation_head": git("rev-parse", "HEAD"),
            "frozen_src_git_tree": git("rev-parse", f"{FROZEN}:src"),
            "source_bytes_match_frozen": True,
            "snapshots": SNAPSHOTS,
            "files_sha256": {p: sha(ROOT / p) for p in sorted(set(SOURCES + source_files))},
        },
    )
    print(
        canonical(
            {
                "stage": 1,
                "prepared": 40,
                "transformed": 200,
                "static_validation": "240/240",
                "solver_calls": 0,
            }
        )
    )


def verify():
    check_frozen()
    if {p.name for p in (HERE / "inputs").iterdir()} != set(RULES["modes"]):
        raise ValueError("unexpected/missing input mode directory")
    cases, chosen, universe = selection()
    stored_selection = list(csv.DictReader((HERE / "selection.csv").open()))
    if [r["id"] for r in chosen] != [r["id"] for r in stored_selection]:
        raise ValueError("selection mismatch")
    stored_transformations = json.loads((HERE / "transformations.json").read_text())
    expected = []
    for row in stored_transformations:
        original = cases[row["id"]]["dsl"]
        wanted, mapping = transform(original, row["mode"])
        p = HERE / row["dsl_path"]
        got = json.loads(p.read_text())
        if got != wanted or sha(p) != row["dsl_sha256"]:
            raise ValueError(f"DSL differs: {p}")
        for key, value in mapping.items():
            if row[key] != value:
                raise ValueError("transformation ledger differs")
        verify_equivalence(original, got, mapping)
        public_validate(got)
        expected.append(p)
    if len(expected) != 240 or len(set(expected)) != 240:
        raise ValueError("wrong DSL count")
    for mode in RULES["modes"]:
        corpus = HERE / "inputs" / mode / "cases.jsonl"
        rows = [json.loads(s) for s in corpus.read_text().splitlines()]
        if [r["id"] for r in rows] != [r["id"] for r in chosen]:
            raise ValueError("corpus selection mismatch")
        for r in rows:
            if r["dsl"] != json.loads((corpus.parent / r["dsl_path"]).read_text()):
                raise ValueError("corpus/file mismatch")
            if r["answer"] != cases[r["id"]]["answer"]:
                raise ValueError("reference answer changed")
        actual = set((corpus.parent / "dsl").glob("*.json"))
        if actual != {corpus.parent / r["dsl_path"] for r in rows}:
            raise ValueError("orphan/missing DSL")
    if json.loads((HERE / "execution-plan.json").read_text()) != execution_plan(chosen):
        raise ValueError("schedule differs")
    if json.loads((HERE / "equivalence-controls.json").read_text()) != equivalence_controls():
        raise ValueError("equivalence controls differ")
    manifest = json.loads((HERE / "source-manifest.json").read_text())
    for p, expected_sha in manifest["files_sha256"].items():
        actual = HERE / manifest["snapshots"][p] if p in manifest["snapshots"] else ROOT / p
        if sha(actual) != expected_sha:
            raise ValueError(f"source changed: {p}")
    check_modules()
    files = [p for p in HERE.rglob("*") if p.is_file()]
    if any(p.stat().st_size >= RULES["file_limit_bytes"] for p in files):
        raise ValueError("file limit exceeded")
    print(
        canonical(
            {
                "verified_documents": len(expected),
                "batches": 210,
                "solver_calls": 0,
                "max_file_bytes": max(p.stat().st_size for p in files),
            }
        )
    )


def seal():
    # Last stage-1 action. This command has no execution continuation.
    if (HERE / "prediction.lock.json").exists() or (HERE / "prediction.md").exists():
        raise ValueError("prediction already exists; refusing to overwrite")
    verify()
    prediction = sys.stdin.read()
    if not prediction.strip():
        raise ValueError("empty prediction")
    write(HERE / "prediction.md", prediction)
    files = {
        str(p.relative_to(HERE)): {"sha256": sha(p), "bytes": p.stat().st_size}
        for p in sorted(HERE.rglob("*"))
        if p.is_file()
    }
    dsls = {
        p: meta["sha256"]
        for p, meta in files.items()
        if p.startswith("inputs/") and "/dsl/" in p and not p.startswith("inputs/original/")
    }
    lock = {
        "schema_version": 1,
        "task": "Q38",
        "stage": 1,
        "locked_at_utc": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        "frozen_commit": FROZEN,
        "execution_authorized": False,
        "solver_calls": 0,
        "authorization_gate": (
            "User confirms prediction commit and push; separate task authorizes execution."
        ),
        "prediction_sha256": files["prediction.md"]["sha256"],
        "transformation_rules_sha256": {
            p: files[p]["sha256"] for p in ("rules.json", "rules.md", "prepare.py")
        },
        "all_transformed_dsl_sha256": dsls,
        "all_transformed_dsl_manifest_sha256": digest(canonical(dsls).encode()),
        "file_manifest_sha256": digest(canonical(files).encode()),
        "manifest_encoding": (
            "UTF-8, JSON ensure_ascii=False, sort_keys=True, separators=(',',':'), no newline"
        ),
        "self_hash_excluded": True,
        "files": files,
    }
    if len(dsls) != 200:
        raise ValueError("expected exactly 200 transformed DSL files")
    write_json(HERE / "prediction.lock.json", lock)
    # Read back the actual bytes, not a potentially stale in-memory digest.
    reread = json.loads((HERE / "prediction.lock.json").read_text())
    for p, record in reread["files"].items():
        if sha(HERE / p) != record["sha256"]:
            raise ValueError(f"seal read-back mismatch: {p}")
    print("予測固定・実行は許可待ち")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["prepare", "verify", "seal"])
    args = parser.parse_args()
    sys.dont_write_bytecode = True
    sys.path.insert(0, str(ROOT / "src"))
    {"prepare": prepare, "verify": verify, "seal": seal}[args.action]()


if __name__ == "__main__":
    main()
