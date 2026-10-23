"""Q39 stage 1: syntax-only selection. Never imports or executes the solver.

The four frozen helper modules below only inspect expression ASTs. Import nodes
are restricted to the standard library, and only function definitions are
loaded. No geometry evaluation, compilation of problems, optimization, numerical
refinement, test, or benchmark execution is performed by this script.
"""

from __future__ import annotations

import argparse
import ast
from collections import Counter
import hashlib
import json
from pathlib import Path
import subprocess


ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent
FROZEN = "60db4b679b04167175c51c479c87c22fa663fda0"
CAP = 6
PRIORITY = (
    "positive_radius_aux",
    "distance_radius_contact",
    "tangency_contact",
    "tangency_circle_gap",
    "tangency_line_gap",
    "distance_point_zero",
)
HELPERS = (
    "src/geosolver/problem/expression_source.py",
    "src/geosolver/engine/standard/problem/zero_test_source.py",
    "src/geosolver/engine/standard/problem/tangency_contacts.py",
    "src/geosolver/engine/standard/problem/positive_radius_contacts.py",
)
POINT_CALLS = frozenset(
    "Point Midpoint Centroid Circumcenter Incenter Orthocenter Reflect Rotate "
    "FootOfPerpendicular PointOnLine PointOnSegment PointOnCircle PointOnArc "
    "IncircleContactPoint Center TriangleCenter".split()
)
LINE_CALLS = frozenset(
    "Line ParallelLine PerpendicularLine PerpendicularBisector AngleBisector".split()
)
CIRCLE_CALLS = frozenset("Circle Circumcircle Incircle Excircle NinePointCircle".split())


def sha(data):
    return hashlib.sha256(data).hexdigest()


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":"), allow_nan=False).encode()


def frozen_bytes(path):
    return subprocess.run(["git", "show", f"{FROZEN}:{path}"], cwd=ROOT,
                          check=True, capture_output=True).stdout


def syntax_helpers():
    namespace = {}
    digests = {}
    allowed = {"__future__", "ast", "copy", "hashlib", "re", "fractions", "functools"}
    for path in HELPERS:
        payload = frozen_bytes(path)
        if (ROOT / path).read_bytes() != payload:
            raise ValueError(f"frozen helper mismatch: {path}")
        digests[path] = sha(payload)
        tree = ast.parse(payload, filename=path)
        nodes = []
        for node in tree.body:
            if isinstance(node, ast.ImportFrom) and (node.module or "").startswith("geosolver."):
                continue  # Injected from the already loaded syntax helpers.
            if isinstance(node, ast.ImportFrom):
                if node.module not in allowed:
                    raise ValueError(f"non-stdlib import in {path}")
                nodes.append(node)
            elif isinstance(node, ast.Import):
                if any(item.name not in allowed for item in node.names):
                    raise ValueError(f"non-stdlib import in {path}")
                nodes.append(node)
            elif isinstance(node, ast.FunctionDef):
                if any(isinstance(n, (ast.Import, ast.ImportFrom)) for n in ast.walk(node)):
                    raise ValueError(f"nested import in {path}:{node.name}")
                nodes.append(node)
            elif isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant):
                continue  # Module docstring.
            else:
                raise ValueError(f"unexpected top-level code in {path}")
        exec(compile(ast.Module(body=nodes, type_ignores=[]), path, "exec"), namespace)
    return namespace, digests


def call_name(node):
    return node.func.id if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) else None


def classify(record, helpers):
    dsl = record["dsl"]
    constructions = tuple((c["name"], c["expression"]) for c in dsl["constructions"])
    definitions = {name: ast.parse(source, mode="eval").body for name, source in constructions}
    equalities = tuple((str(c["left"]), str(c["right"]))
                       for c in dsl["conditions"] if c.get("operator") == "=")
    condition_indices = [i for i, c in enumerate(dsl["conditions"]) if c.get("operator") == "="]
    tags, rewrites, untouched, unsupported = set(), [], [], []

    def kind(node, active=frozenset()):
        if isinstance(node, ast.Name) and node.id in definitions and node.id not in active:
            return kind(definitions[node.id], active | {node.id})
        name = call_name(node)
        if name in POINT_CALLS:
            return "point"
        if name in LINE_CALLS:
            return "line"
        if name in CIRCLE_CALLS:
            return "circle"
        if name == "Arc":
            return "arc"
        # Intersect is deliberately not assumed to be a single point: its
        # branch/selector signature needs a separate audit.
        return "unknown"

    distance_contacts = helpers["distance_contact_sources"](constructions, equalities)
    radius_sources = helpers["positive_radius_contact_sources"](
        tuple(dsl.get("variables", [])), constructions, equalities)
    if radius_sources:
        tags.add("positive_radius_aux")
        rewrites.append({"kind": "positive_radius_aux", "sources": list(radius_sources),
                         "retains_original_rows": True})
    for index, (lhs, rhs) in enumerate(equalities):
        base = {"equality_index_before_lowering": index,
                "condition_index": condition_indices[index], "lhs": lhs, "rhs": rhs}
        if index in distance_contacts:
            tags.add("distance_radius_contact")
            rewrites.append({**base, "kind": "distance_radius_contact",
                             "source": distance_contacts[index]})
            continue
        try:
            zero = helpers["rational_constant"](
                helpers["annotate_source"](ast.parse(rhs, mode="eval"), rhs).body) == 0
        except (ValueError, ArithmeticError):
            zero = False
        node = helpers["zero_test_call"](lhs) if zero else None
        name = call_name(node)
        if name not in {"Distance", "IsTangent", "OnSegment"}:
            continue
        if name == "OnSegment":
            untouched.append({**base, "kind": "OnSegment_pre_lowering"})
            continue
        if len(node.args) != 2 or node.keywords:
            unsupported.append({**base, "reason": "arity_or_keywords"})
            continue
        args = [ast.get_source_segment(lhs, arg) for arg in node.args]
        types = [kind(arg) for arg in node.args]
        if name == "Distance":
            if types == ["point", "point"]:
                tags.add("distance_point_zero")
                rewrites.append({**base, "kind": "distance_point_zero", "arguments": args})
            elif set(types) == {"point", "line"}:
                untouched.append({**base, "kind": "distance_point_line_zero"})
            else:
                unsupported.append({**base, "reason": "unproved_distance_types", "types": types})
        else:
            contact = helpers["contact_tangency_source"](*args, constructions, equalities)
            circles = {"circle", "arc"}
            if contact is not None:
                tags.add("tangency_contact")
                rewrites.append({**base, "kind": "tangency_contact", "source": contact,
                                 "argument_types": types,
                                 "coincident_circle_caveat": all(t in circles for t in types)})
            elif all(t in circles for t in types):
                tags.add("tangency_circle_gap")
                rewrites.append({**base, "kind": "tangency_circle_gap", "arguments": args})
            elif sorted(types) in (["circle", "line"], ["arc", "line"]):
                tags.add("tangency_line_gap")
                rewrites.append({**base, "kind": "tangency_line_gap", "arguments": args})
            else:
                unsupported.append({**base, "reason": "unproved_tangency_types", "types": types})
    expressions = [source for _, source in constructions]
    for condition in dsl["conditions"]:
        expressions += [str(condition[k]) for k in ("left", "right", "predicate") if k in condition]
    calls = set()
    for source in expressions:
        calls.update(call_name(n) for n in ast.walk(ast.parse(source, mode="eval"))
                     if isinstance(n, ast.Call))
    excluded = []
    if not 1 <= len(dsl.get("variables", [])) <= 12:
        excluded.append("raw_variable_count_outside_1_to_12")
    if calls & {"IsInteger", "IsPrime", "Or", "And", "Not"}:
        excluded.append("discrete_or_logical_residual")
    if unsupported:
        excluded.append("static_argument_type_unproved")
    group = next((tag for tag in PRIORITY if tag in tags), None)
    if group is None and any(x["kind"] == "distance_point_line_zero" for x in untouched):
        group = "unchanged_distance_point_line"
    if group is None and any(x["kind"] == "OnSegment_pre_lowering" for x in untouched):
        group = "unchanged_onsegment"
    return {"id": record["id"], "dsl_path": "benchmarks/" + record["dsl_path"],
            "raw_variables": len(dsl.get("variables", [])),
            "dsl_sha256": sha((ROOT / "benchmarks" / record["dsl_path"]).read_bytes()),
            "dsl_canonical_sha256": sha(canonical(dsl)),
            "rank_sha256": sha(("Q39-stage-representation-v1\0" + record["id"]).encode()),
            "stratum": group, "tags": sorted(tags), "rewrites": rewrites,
            "unchanged": untouched, "unsupported": unsupported, "exclusion_reasons": excluded}


def build():
    helpers, helper_hashes = syntax_helpers()
    path = ROOT / "benchmarks/cases.jsonl"
    data = path.read_bytes()
    if data != frozen_bytes("benchmarks/cases.jsonl"):
        raise ValueError("corpus differs from frozen commit")
    records = [json.loads(line) for line in data.splitlines() if line.strip()]
    if len(records) != 323:
        raise ValueError("expected development corpus of 323 cases")
    audit = []
    for record in records:
        file_dsl = json.loads((ROOT / "benchmarks" / record["dsl_path"]).read_text())
        if file_dsl != record["dsl"]:
            raise ValueError(f"embedded/file DSL mismatch: {record['id']}")
        audit.append(classify(record, helpers))
    selected = []
    for group in (*PRIORITY, "unchanged_distance_point_line", "unchanged_onsegment"):
        eligible = sorted((r for r in audit if r["stratum"] == group and not r["exclusion_reasons"]),
                          key=lambda r: (r["rank_sha256"], r["id"]))
        limit = 3 if group.startswith("unchanged_") else CAP
        selected.extend(eligible[:limit])
    selected.sort(key=lambda r: r["id"])
    ids = [r["id"] for r in selected]
    selection = {"schema_version": 1, "frozen_commit": FROZEN,
                 "method": "stdlib AST plus frozen syntax-only helper functions; no solver import/run",
                 "corpus": "benchmarks/cases.jsonl", "corpus_sha256": sha(data),
                 "helper_sha256": helper_hashes, "stratum_priority": list(PRIORITY),
                 "cap_per_primary_stratum": CAP, "cap_per_unchanged_control_stratum": 3,
                 "ranking": "sha256(UTF-8('Q39-stage-representation-v1' + NUL + exact case id)), then id",
                 "eligible_stratum_counts": dict(sorted(Counter(
                     r["stratum"] for r in audit if r["stratum"] and not r["exclusion_reasons"]).items())),
                 "selected_stratum_counts": dict(sorted(Counter(r["stratum"] for r in selected).items())),
                 "selected_ids": ids, "selected": selected}
    audit_output = {"corpus_sha256": sha(data), "total_cases": len(audit), "cases": audit}
    return selection, audit_output


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true", help="write syntax-only selection artifacts")
    options = parser.parse_args()
    selection, audit = build()
    if options.write:
        if (OUT / "prediction.lock.json").exists():
            raise SystemExit("prediction is already locked; do not overwrite selection")
        outputs = {"selection.json": json.dumps(selection, ensure_ascii=False, indent=2) + "\n",
                   "selection-audit.json": json.dumps(audit, ensure_ascii=False, indent=2) + "\n",
                   "selected-problems.txt": "".join(i + "\n" for i in selection["selected_ids"])}
        for name, payload in outputs.items():
            if len(payload.encode()) >= 5_000_000:
                raise ValueError(f"file too large: {name}")
            (OUT / name).write_text(payload, encoding="utf-8", newline="\n")
    print(json.dumps({k: selection[k] for k in (
        "eligible_stratum_counts", "selected_stratum_counts", "selected_ids")},
        ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
