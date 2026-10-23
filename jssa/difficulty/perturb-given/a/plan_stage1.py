"""Q40a: input-only preparation. No solver imports or execution entry point.

Only JSON/AST inspection, arithmetic on constant literals, hashing, and three
read-only git commands are used. `check` does not write. `build` refuses a lock.
"""

from __future__ import annotations

import argparse
import ast
import copy
import csv
import hashlib
import io
import json
import math
import re
import subprocess
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
FROZEN = "60db4b679b04167175c51c479c87c22fa663fda0"
INSTRUCTIONS = "jssa/strategy/codex-tasks-1023.md"
SOURCES = {
    "development": ["benchmarks/cases.jsonl"],
    "unseen": [
        "jssa/difficulty/new2026/cases.jsonl",
        "jssa/difficulty/unseen-2/a/cases.jsonl",
        "jssa/difficulty/unseen-2/b/cases.jsonl",
    ],
}
SEED = 4040
START_SEEDS = [404001, 404002, 404003]
VARIANTS = [
    ("original", 0, 0, 0),
    ("e3_plus", 1000, 0, 1),
    ("e3_minus", 1000, 0, -1),
    ("e2_plus", 100, 0, 1),
    ("e2_minus", 100, 0, -1),
    ("e1_random", 10, 1, 1),
]


def packed(obj):
    return (json.dumps(obj, ensure_ascii=False, sort_keys=True, indent=2,
                       allow_nan=False) + "\n").encode("utf-8")


def jsonl(rows):
    return ("".join(json.dumps(r, ensure_ascii=False, sort_keys=True,
                               separators=(",", ":"), allow_nan=False) + "\n"
                    for r in rows)).encode("utf-8")


def sha(data):
    return hashlib.sha256(data).hexdigest()


def digest(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def git_read(args):
    # Do not extend this to a general command runner.
    allowed = [
        ["ls-tree", "-r", "--full-tree", FROZEN, "--", "src"],
        ["rev-parse", f"{FROZEN}:src"],
        ["rev-parse", "HEAD"],
    ]
    if args not in allowed:
        raise ValueError("Only the three fixed read-only git commands are allowed")
    return subprocess.run(["git", *args], cwd=ROOT, check=True,
                          capture_output=True, text=True).stdout.strip()


def canonical_id(raw):
    value = raw.upper()
    match = re.fullmatch(r"AIME-(\d{4})-(1|2|I|II)-(\d+)", value)
    if match:
        year, part, number = match.groups()
        part = {"1": "I", "2": "II"}.get(part, part)
        return f"AIME-{year}-{part}-{int(number):02d}"
    head, sep, tail = value.rpartition("-")
    return f"{head}-{int(tail):02d}" if sep and tail.isdigit() else value


def expression(value):
    if isinstance(value, bool) or not isinstance(value, (str, int, float)):
        raise ValueError(f"Not a DSL expression: {type(value).__name__}")
    return str(value)


def parsed(value):
    return ast.parse(expression(value), mode="eval").body


def constant_value(node):
    """Closed scalar AST only; never evaluate a geometry expression or eval()."""
    if isinstance(node, ast.Constant) and type(node.value) in (int, float):
        value = float(node.value)
    elif isinstance(node, ast.Name) and node.id == "pi":
        value = math.pi
    elif isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
        value = constant_value(node.operand)
        if isinstance(node.op, ast.USub):
            value = -value
    elif isinstance(node, ast.BinOp):
        left, right = constant_value(node.left), constant_value(node.right)
        if isinstance(node.op, ast.Add):
            value = left + right
        elif isinstance(node.op, ast.Sub):
            value = left - right
        elif isinstance(node.op, ast.Mult):
            value = left * right
        elif isinstance(node.op, ast.Div):
            value = left / right
        elif isinstance(node.op, ast.Pow) and right.is_integer() and abs(right) <= 16:
            value = left ** int(right)
        else:
            raise ValueError("Not a supported constant operator")
    elif (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
          and node.func.id == "sqrt" and len(node.args) == 1 and not node.keywords):
        value = math.sqrt(constant_value(node.args[0]))
    else:
        raise ValueError("Not a closed numeric expression")
    if not math.isfinite(value):
        raise ValueError("Nonfinite constant")
    return value


def is_constant(node):
    try:
        constant_value(node)
        return True
    except (ValueError, ZeroDivisionError, OverflowError, TypeError):
        return False


def dimension(node):
    """Conservative direct-given grammar, not general symbolic inference."""
    if is_constant(node):
        return "scalar"
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
        if node.func.id in {"Distance", "Radius", "Length"}:
            return "length"
        if node.func.id == "Angle":
            return "angle"
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
        return dimension(node.operand)
    if isinstance(node, ast.BinOp):
        left, right = dimension(node.left), dimension(node.right)
        if isinstance(node.op, (ast.Add, ast.Sub)) and left == right:
            return left
        if isinstance(node.op, ast.Mult):
            if left == "scalar":
                return right
            if right == "scalar":
                return left
        if isinstance(node.op, ast.Div):
            if right == "scalar":
                return left
            if left == right and left in {"length", "angle"}:
                return "ratio"
    return None


def dependencies(node, constructions, variables, seen=frozenset()):
    result = set()
    for part in ast.walk(node):
        if not isinstance(part, ast.Name):
            continue
        if part.id in variables:
            result.add(part.id)
        elif part.id in constructions and part.id not in seen:
            result.update(dependencies(parsed(constructions[part.id]), constructions,
                                       variables, seen | {part.id}))
    return result


def given_slots(dsl):
    variables = set(dsl["variables"])
    constructions = {r["name"]: r["expression"] for r in dsl["constructions"]}
    slots = []
    for index, condition in enumerate(dsl["conditions"]):
        if condition.get("operator") != "=":
            continue
        nodes = {side: parsed(condition[side]) for side in ("left", "right")}
        found = None
        # An entire constant side takes precedence, right before left.
        for side, other in [("right", "left"), ("left", "right")]:
            if (is_constant(nodes[side]) and constant_value(nodes[side]) > 0
                    and dimension(nodes[other]) in {"length", "angle", "ratio"}
                    and dependencies(nodes[other], constructions, variables)):
                text = expression(condition[side])
                found = {"condition_index": index, "side": side, "start": 0,
                         "end": len(text), "constant_expression": text,
                         "kind": dimension(nodes[other]), "mode": "whole_side"}
                break
        # A direct ratio such as Distance(A,B) = 2*Distance(C,D).
        if found is None:
            for side, other in [("right", "left"), ("left", "right")]:
                node = nodes[side]
                if not (isinstance(node, ast.BinOp) and isinstance(node.op, ast.Mult)):
                    continue
                for factor, geometric in [(node.left, node.right), (node.right, node.left)]:
                    kind = dimension(geometric)
                    if (is_constant(factor) and constant_value(factor) > 0
                            and kind in {"length", "angle"} and dimension(nodes[other]) == kind
                            and dependencies(nodes[other], constructions, variables)
                            and dependencies(geometric, constructions, variables)):
                        text = expression(condition[side])
                        # AST offsets are UTF-8 byte offsets. These corpus expressions
                        # are ASCII; refuse non-ASCII here instead of slicing wrongly.
                        if not text.isascii():
                            raise ValueError("Non-ASCII coefficient expression")
                        found = {"condition_index": index, "side": side,
                                 "start": factor.col_offset, "end": factor.end_col_offset,
                                 "constant_expression": ast.get_source_segment(text, factor),
                                 "kind": "ratio", "mode": "coefficient"}
                        break
                if found is not None:
                    break
        if found is not None:
            found["slot_id"] = f"conditions/{index}/{found['side']}/{found['start']}:{found['end']}"
            found["condition"] = condition
            slots.append(found)
    return slots


def validate_dsl(dsl):
    variables = dsl["variables"]
    names = [r["name"] for r in dsl["constructions"]]
    assert len(variables) == len(set(variables)) and len(names) == len(set(names))
    assert not set(variables) & set(names)
    expressions = [r["expression"] for r in dsl["constructions"]] + [dsl["target"]]
    for row in dsl["conditions"]:
        if "predicate" in row:
            expressions.append(row["predicate"])
        else:
            assert row["operator"] in {"=", "!=", ">", "<", ">=", "<="}
            expressions.extend([row["left"], row["right"]])
    for value in expressions:
        parsed(value)
    return len(expressions)


def frozen_sources():
    files = {}
    for line in git_read(["ls-tree", "-r", "--full-tree", FROZEN, "--", "src"]).splitlines():
        info, path = line.split("\t", 1)
        mode, kind, blob = info.split()
        assert kind == "blob" and mode in {"100644", "100755"}, (path, mode, kind)
        data = (ROOT / path).read_bytes()
        actual = hashlib.sha1(b"blob " + str(len(data)).encode("ascii") + b"\0" + data).hexdigest()
        if actual != blob:
            raise ValueError(f"Frozen src differs: {path}")
        files[path] = {"sha256": sha(data), "bytes": len(data), "git_blob": blob}
    assert files
    # Newly introduced source files would also change the solver import surface.
    extras = sorted(str(p.relative_to(ROOT)) for p in (ROOT / "src").rglob("*.py")
                    if str(p.relative_to(ROOT)) not in files)
    if extras:
        raise ValueError(f"Extra Python sources under src: {extras}")
    return {"frozen_commit": FROZEN, "src_git_tree": git_read(["rev-parse", f"{FROZEN}:src"]),
            "files": files, "all_tracked_src_bytes_match_frozen_commit": True}


def build_expected():
    outputs = {}
    intervention_rules = json.loads((HERE / "interventions.json").read_text())
    ledger, selected = [], []
    seen = set()
    source_hashes = {}
    cohort_counts = {}
    for cohort, paths in SOURCES.items():
        pool = []
        for path in paths:
            data = (ROOT / path).read_bytes()
            source_hashes[path] = {"sha256": sha(data), "bytes": len(data)}
            for line in data.decode("utf-8").splitlines():
                if not line.strip():
                    continue
                record = json.loads(line)
                # Do not access answer, rating, prior results, or reference figures.
                pool.append({"id": record["id"], "canonical_id": canonical_id(record["id"]),
                             "dsl": record["dsl"], "cohort": cohort, "source": path})
        pool.sort(key=lambda r: (r["canonical_id"], r["source"]))
        outputs[f"inputs/{cohort}.jsonl"] = jsonl(pool)
        eligible = []
        for row in pool:
            dsl = row["dsl"]
            key = row["canonical_id"]
            rank_key = digest(f"Q40|{SEED}|{cohort}|{key}")
            reasons = []
            if key in seen:
                reasons.append("duplicate_id")
            seen.add(key)
            if len(dsl["variables"]) < 2:
                reasons.append("n_vars_lt_2")
            try:
                slots = given_slots(dsl)
            except (ValueError, SyntaxError, KeyError, TypeError) as error:
                slots = []
                reasons.append(f"unsupported_static_syntax:{type(error).__name__}")
            if not slots:
                reasons.append("no_supported_direct_numeric_given")
            # Continuous figure existence must not depend on an answer-format
            # integer constraint. This is an input-only eligibility rule.
            if any("IsInteger" in expression(c.get(s, ""))
                   for c in dsl["conditions"] for s in ["left", "right", "predicate"]):
                reasons.append("integer_constraint")
            entry = {"id": row["id"], "canonical_id": key, "source": row["source"],
                     "cohort": cohort, "n_vars": len(dsl["variables"]),
                     "rank_key": rank_key, "given_count": len(slots),
                     "eligible": not reasons, "exclusion_reasons": reasons, "selected": False}
            ledger.append(entry)
            if not reasons:
                eligible.append((rank_key, key, row, slots, entry))
        eligible.sort(key=lambda r: (r[0], r[1]))
        if len(eligible) < 20:
            raise ValueError(f"Fewer than 20 eligible cases in {cohort}; do not substitute")
        for rank, (_, _, row, slots, entry) in enumerate(eligible, 1):
            entry["eligible_rank"] = rank
            if rank <= 20:
                entry["selected"] = True
                selected.append({**entry, "given_slots": slots, "dsl": row["dsl"]})
        cohort_counts[cohort] = {"population": len(pool), "eligible": len(eligible), "selected": 20}
    assert len(selected) == 40
    variants, expression_count = [], 0
    for row in selected:
        base = row["dsl"]
        key = row["canonical_id"]
        rule = intervention_rules["exceptions"].get(key, {})
        active = [s for s in row["given_slots"]
                  if s["condition_index"] in rule.get("active_condition_indices", range(len(base["conditions"])))]
        assert active, key
        row["perturbed_slot_ids"] = [s["slot_id"] for s in active]
        row["perturbed_given_count"] = len(active)
        for name, denominator, direction, orientation in VARIANTS:
            dsl = copy.deepcopy(base)
            edits = []
            replacements = {}
            if denominator:
                for slot in active:
                    h = digest(f"Q40|{SEED}|direction|{key}|{direction}|{slot['slot_id']}")
                    sign = (1 if int(h, 16) % 2 == 0 else -1) * orientation
                    index, side = slot["condition_index"], slot["side"]
                    text = expression(base["conditions"][index][side])
                    old = text[slot["start"]:slot["end"]]
                    assert old == slot["constant_expression"]
                    new = f"({old})*({denominator + sign}/{denominator})"
                    # Parentheses protect a coefficient embedded in a larger expression.
                    updated = text[:slot["start"]] + f"({new})" + text[slot["end"]:]
                    dsl["conditions"][index][side] = updated
                    replacements[slot["slot_id"]] = f"({new})"
                    edits.append({"slot_id": slot["slot_id"], "kind": slot["kind"],
                                  "path": ["conditions", index, side],
                                  "condition_index": index, "side": side,
                                  "before": base["conditions"][index][side], "after": updated,
                                  "delta_numerator": sign, "delta_denominator": denominator})
                for linked in rule.get("linked_expressions", []):
                    section, index, field = linked["path"]
                    assert base[section][index][field] == linked["before"]
                    updated = linked["template"]
                    for alias, slot_id in rule["aliases"].items():
                        updated = updated.replace(f"${alias}", replacements[slot_id])
                    assert "$" not in updated
                    dsl[section][index][field] = updated
                    edits.append({"path": linked["path"], "kind": "linked_given",
                                  "before": linked["before"], "after": updated})
            expression_count += validate_dsl(dsl)
            restored = copy.deepcopy(dsl)
            for edit in edits:
                section, index, field = edit["path"]
                restored[section][index][field] = edit["before"]
            assert restored == base
            assert dsl["variables"] == base["variables"] and dsl["target"] == base["target"]
            data = packed(dsl)
            path = f"dsl/{key}/{name}.json"
            outputs[path] = data
            variants.append({"id": row["id"], "canonical_id": key, "cohort": row["cohort"],
                             "variant": name, "epsilon": (f"1/{denominator}" if denominator else "0"),
                             "path": path, "sha256": sha(data), "edits": edits})
        hashes = [r["sha256"] for r in variants if r["canonical_id"] == key]
        assert len(set(hashes)) == 6, key
    selected_public = [{k: v for k, v in r.items() if k != "dsl"} for r in selected]
    outputs["selected.json"] = packed(selected_public)
    stream = io.StringIO(newline="")
    fields = ["cohort", "eligible_rank", "id", "canonical_id", "n_vars", "given_count", "source", "rank_key"]
    writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\n", extrasaction="ignore")
    writer.writeheader()
    writer.writerows(selected_public)
    outputs["selected.csv"] = stream.getvalue().encode("utf-8")
    outputs["selection-ledger.jsonl"] = jsonl(ledger)
    outputs["variants.jsonl"] = jsonl(variants)
    outputs["selection-contract.json"] = packed({
        "protocol": "Q40-common-selection-v1", "seed": SEED, "sources": SOURCES,
        "source_files": source_hashes, "quota": {"development": 20, "unseen": 20},
        "canonical_id_rule": "canonical_id() in plan_stage1.py",
        "eligibility_rule": "given_slots() and build_expected() in plan_stage1.py; prediction.md section 2",
        "rank": "ascending (SHA256(UTF8('Q40|4040|' + cohort + '|' + canonical_id)), canonical_id)",
        "cohort_counts": cohort_counts,
        "sibling_contract": "Q40b must use this exact selection-contract.json, selected.json and DSL bytes; seed alone is insufficient",
        "interventions_sha256": sha((HERE / "interventions.json").read_bytes()),
        "outcomes_used": False, "replacement_after_lock": False,
    })
    outputs["execution-plan.json"] = packed({
        "stage": 1, "execution_authorized": False, "frozen_commit": FROZEN,
        "requires": ["Claude confirms the prediction commit and push", "explicit execution permission in a separate task"],
        "start_seeds": START_SEEDS, "starts_per_seed_condition": 200,
        "primary_seed": START_SEEDS[0], "conditions_per_problem": 6,
        "problem_count": 40, "planned_local_trials": 144000,
        "local_method": "unmodified _collect_local_start_record; LM or frozen Powell fallback",
        "max_nfev_lm": 80, "lm_tolerances": {"ftol": 1e-14, "xtol": 1e-14, "gtol": 1e-14},
        "powell_maxiter": 400, "powell_ftol": 1e-16,
        "constraint_scales": None, "local_deadline_seconds": 2,
        "hard_worker_timeout_seconds": 5, "build_timeout_seconds": 60,
        "cores_per_worker": 1, "maximum_concurrent_workers": 8,
        "bounds": "original DSL infer_problem_bounds, identical for all 6 variants",
        "start_coordinates": "SHA256-based 52-bit midpoint uniforms specified in prediction.md; same arrays for all variants",
        "primary_hit": "finite endpoint; frozen equality L2 <= 1e-8; all guards and hard checks true; in original box",
        "failure_denominator": "always 200 per case/variant/seed, including nonattempted, timeouts and invalid variants",
        "full_solver_calls": 0, "answer_identification": False,
    })
    manifest = frozen_sources()
    manifest["input_files"] = source_hashes
    manifest["instruction_file"] = {"path": INSTRUCTIONS, "sha256": sha((ROOT / INSTRUCTIONS).read_bytes())}
    outputs["source-manifest.json"] = packed(manifest)
    outputs["static-checks.json"] = packed({
        "status": "static_only_pass", "cohort_counts": cohort_counts,
        "selected_problem_count": 40, "original_dsls": 40, "perturbed_dsls": 200,
        "variant_allocation_per_problem": {"1e-3": 2, "1e-2": 2, "1e-1": 1},
        "ast_expressions_checked": expression_count,
        "all_changes_restore_exact_original_json_values": True,
        "unchanged_variables_predicates_targets": True,
        "other_dsl_changes_limited_to_frozen_intervention_map": True,
        "six_distinct_dsl_hashes_per_problem": True,
        "src_matches_frozen_commit": True, "frozen_src_file_count": len(manifest["files"]),
        "solver_calls": 0, "local_search_calls": 0, "geometry_evaluations": 0,
        "not_verified": ["solver DSL compilation", "existence of any original or perturbed figure",
                         "semantic independence of all numeric givens", "Jacobian rank or branch separation"],
        "selection_exclusion_counts": dict(sorted(Counter(reason for r in ledger
                                                          for reason in r["exclusion_reasons"]).items())),
    })
    return outputs


def check():
    outputs = build_expected()
    for name, data in outputs.items():
        if (HERE / name).read_bytes() != data:
            raise ValueError(f"Static regeneration differs: {name}")
    lock_path = HERE / "prediction.lock.json"
    if lock_path.exists():
        lock = json.loads(lock_path.read_text())
        for name, record in lock["files"].items():
            data = (HERE / name).read_bytes()
            assert sha(data) == record["sha256"] and len(data) == record["bytes"], name
        actual = {str(p.relative_to(HERE)) for p in HERE.rglob("*")
                  if p.is_file() and p.name != "prediction.lock.json" and "__pycache__" not in p.parts
                  and p.relative_to(HERE).parts[0] != "stage2"
                  and p.relative_to(HERE).as_posix() != "answer.md"}
        assert actual == set(lock["files"]), "The fixed-file inventory changed"
        assert lock["execution_authorized"] is False
    return outputs


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["build", "check", "lock"])
    args = parser.parse_args()
    if args.action == "build":
        if (HERE / "prediction.lock.json").exists():
            raise SystemExit("Locked: build is prohibited. There is no override flag.")
        outputs = build_expected()
        for name, data in outputs.items():
            path = HERE / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
        print(json.dumps(json.loads(outputs["static-checks.json"]), ensure_ascii=False))
    elif args.action == "check":
        outputs = check()
        print(f"static check passed: {len(outputs)} generated files; solver/local-search calls = 0")
    else:
        if (HERE / "prediction.lock.json").exists():
            raise SystemExit("Lock already exists; it will not be overwritten.")
        check()
        assert (HERE / "prediction.md").is_file()
        assert not (HERE / "stage2").exists() and not (HERE / "answer.md").exists()
        files = {}
        for path in sorted(HERE.rglob("*")):
            if path.is_file() and "__pycache__" not in path.parts:
                data = path.read_bytes()
                assert len(data) < 5_000_000, path
                files[str(path.relative_to(HERE))] = {"sha256": sha(data), "bytes": len(data)}
        lock = {"schema_version": 1, "task": "Q40a", "stage": 1,
                "locked_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
                "repo_head_at_lock": git_read(["rev-parse", "HEAD"]), "frozen_solver_commit": FROZEN,
                "execution_authorized": False, "commit_push_confirmed": False,
                "separate_task_permission_received": False, "solver_calls": 0, "local_search_calls": 0,
                "hash_algorithm": "sha256", "path_base": "this directory",
                "self_hash_excluded": True, "files": files}
        (HERE / "prediction.lock.json").write_bytes(packed(lock))
        print(f"stage1 locked: {len(files)} files; execution remains prohibited")


if __name__ == "__main__":
    main()
