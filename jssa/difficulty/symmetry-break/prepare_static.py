"""Q41 段階1専用。標準ライブラリで構文・有理多項式・hashだけを扱う。

solver の import、式の eval、乱数点生成、最適化、数値幾何を含まない。
子プロセスは読み取り専用 git のみ。--check はファイルを書かない。
"""

from __future__ import annotations

import argparse
import ast
from collections import Counter
import copy
import csv
from fractions import Fraction
import hashlib
import io
import json
from pathlib import Path
import subprocess

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
RULES = json.loads((HERE / "rules.json").read_text())
FROZEN = RULES["frozen_commit"]
POINT_CALLS = set("Point Midpoint Centroid Circumcenter Incenter Orthocenter Reflect Rotate FootOfPerpendicular PointOnLine PointOnSegment PointOnCircle PointOnArc IncircleContactPoint Center".split())
LINE_CALLS = set("Line ParallelLine PerpendicularLine PerpendicularBisector AngleBisector".split())


def sha(data):
    return hashlib.sha256(data).hexdigest()


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def pretty(value):
    return (json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n").encode()


def git(*args):
    return subprocess.check_output(["git", *args], cwd=ROOT, timeout=30)


def frozen(path):
    return git("show", f"{FROZEN}:{path}")


def tree(value):
    return ast.parse(str(value), mode="eval").body


def call(node):
    return node.func.id if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) else None


def expressions(dsl):
    for c in dsl["constructions"]:
        yield c["expression"]
    for c in dsl["conditions"]:
        for key in ("left", "right", "predicate"):
            if key in c:
                yield str(c[key])
    yield dsl["target"]


def names(source):
    return {n.id for n in ast.walk(tree(source)) if isinstance(n, ast.Name)}


def point_kind(node, definitions, seen=frozenset()):
    if isinstance(node, ast.Name) and node.id in definitions and node.id not in seen:
        return point_kind(definitions[node.id], definitions, seen | {node.id})
    if call(node) in POINT_CALLS:
        return "point"
    if call(node) in LINE_CALLS:
        return "line"
    return "unknown"


def edge(node, definitions):
    if call(node) != "Distance" or len(node.args) != 2 or node.keywords:
        return None
    if not all(isinstance(a, ast.Name) and point_kind(a, definitions) == "point" for a in node.args):
        return None
    result = tuple(sorted(a.id for a in node.args))
    return result if result[0] != result[1] else None


def motifs(dsl):
    definitions = {c["name"]: tree(c["expression"]) for c in dsl["constructions"]}
    found = []
    for index, condition in enumerate(dsl["conditions"]):
        if condition.get("operator") != "=":
            continue
        left, right = (edge(tree(condition[key]), definitions) for key in ("left", "right"))
        if left and right and len(set(left) & set(right)) == 1:
            found.append({"family": "equal_sides", "path": ["conditions", index, "right"],
                          "left_edge": left, "right_edge": right,
                          "apex": next(iter(set(left) & set(right))),
                          "evidence": copy.deepcopy(condition),
                          "scope": "triangle_only_not_whole_system"})
    for index, construction in enumerate(dsl["constructions"]):
        node = definitions[construction["name"]]
        if call(node) == "Reflect":
            point = ast.unparse(node.args[0]) if node.args else None
            axis = ast.unparse(node.args[1]) if len(node.args) > 1 else None
            found.append({"family": "mirror", "path": ["constructions", index, "expression"],
                          "point": point, "axis": axis,
                          "point_kind": point_kind(node.args[0], definitions) if point else "unknown",
                          "axis_kind": point_kind(node.args[1], definitions) if axis else "unknown",
                          "arity_ok": len(node.args) == 2 and not node.keywords,
                          "evidence": copy.deepcopy(construction),
                          "scope": "constructed_pair_not_whole_system"})
        elif call(node) == "RegularPolygon":
            found.append({"family": "regular_native", "path": ["constructions", index, "expression"],
                          "evidence": copy.deepcopy(construction),
                          "scope": "native_polygon_only"})
    return found


# 有理数係数の多項式だけを厳密に扱う。sqrt・三角関数・属性は判定不能。
# 単項式は変数名を重複込みでソートしたtuple、係数はFraction。
def plus(a, b, scale=Fraction(1)):
    result = dict(a)
    for monomial, coeff in b.items():
        result[monomial] = result.get(monomial, Fraction(0)) + scale * coeff
        if not result[monomial]:
            del result[monomial]
    return result


def times(a, b):
    result = {}
    for ma, ca in a.items():
        for mb, cb in b.items():
            monomial = tuple(sorted(ma + mb))
            if len(monomial) > 6:
                raise ValueError("polynomial_degree_above_6")
            result = plus(result, {monomial: ca * cb})
    if len(result) > 256:
        raise ValueError("polynomial_terms_above_256")
    return result


def polynomial(node, variables):
    if isinstance(node, ast.Constant) and type(node.value) in (int, float):
        f = Fraction(str(node.value))
        return {(): f} if f else {}
    if isinstance(node, ast.Name) and node.id in variables:
        return {(node.id,): Fraction(1)}
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
        return plus({}, polynomial(node.operand, variables), Fraction(-1 if isinstance(node.op, ast.USub) else 1))
    if isinstance(node, ast.BinOp):
        a, b = polynomial(node.left, variables), polynomial(node.right, variables)
        if isinstance(node.op, ast.Add):
            return plus(a, b)
        if isinstance(node.op, ast.Sub):
            return plus(a, b, Fraction(-1))
        if isinstance(node.op, ast.Mult):
            return times(a, b)
        if isinstance(node.op, ast.Div) and set(b) == {()} and b[()]:
            return {m: c / b[()] for m, c in a.items()}
        if isinstance(node.op, ast.Pow) and set(b) <= {()}:
            exponent = b.get((), Fraction(0))
            if exponent.denominator == 1 and 0 <= exponent <= 4:
                result = {(): Fraction(1)}
                for _ in range(int(exponent)):
                    result = times(result, a)
                return result
    raise ValueError("not_rational_polynomial")


def point_poly(name, dsl):
    construction = next(c for c in dsl["constructions"] if c["name"] == name)
    node = tree(construction["expression"])
    if call(node) != "Point" or len(node.args) != 2 or node.keywords:
        raise ValueError("not_direct_point")
    return [polynomial(x, set(dsl["variables"])) for x in node.args]


def distance_squared(e, dsl):
    a, b = (point_poly(p, dsl) for p in e)
    result = {}
    for ax, bx in zip(a, b):
        diff = plus(ax, bx, Fraction(-1))
        result = plus(result, times(diff, diff))
    return result


def used_in_equations(dsl, name):
    definitions = {c["name"]: names(c["expression"]) for c in dsl["constructions"]}
    used = set()
    for c in dsl["conditions"]:
        if c.get("operator") == "=":
            used |= names(c["left"]) | names(c["right"])
    pending = list(used)
    while pending:
        for dep in definitions.get(pending.pop(), ()):
            if dep not in used:
                used.add(dep)
                pending.append(dep)
    return name in used


def equality_implied_elsewhere(dsl, site):
    # 同じ辺の等長が他の「距離=距離」の鎖で残るなら破れない。
    definitions = {c["name"]: tree(c["expression"]) for c in dsl["constructions"]}
    links = {}
    for i, c in enumerate(dsl["conditions"]):
        if i == site["path"][1] or c.get("operator") != "=":
            continue
        a, b = (edge(tree(c[k]), definitions) for k in ("left", "right"))
        if a and b:
            links.setdefault(a, set()).add(b)
            links.setdefault(b, set()).add(a)
    seen = {tuple(site["left_edge"])}
    pending = list(seen)
    while pending:
        for nxt in links.get(pending.pop(), set()) - seen:
            seen.add(nxt)
            pending.append(nxt)
    return tuple(site["right_edge"]) in seen


def applicable(dsl, site):
    if site["family"] == "regular_native":
        return False, "regular_polygon_rewrite_not_supported"
    if site["family"] == "mirror":
        if not site["arity_ok"] or site["point_kind"] != "point" or site["axis_kind"] not in {"point", "line"}:
            return False, "not_proved_point_reflection"
        name = dsl["constructions"][site["path"][1]]["name"]
        if not used_in_equations(dsl, name):
            return False, "reflected_point_unused_in_equalities"
        return True, "point_reflection_only_local_symmetry"
    if equality_implied_elsewhere(dsl, site):
        return False, "equal_sides_implied_by_other_distance_rows"
    try:
        left = distance_squared(site["left_edge"], dsl)
        right = distance_squared(site["right_edge"], dsl)
    except ValueError as exc:
        return False, f"independent_symmetry_parameter_unproved:{exc}"
    difference = plus(left, right, Fraction(-1))
    if not difference:
        return False, "equal_sides_already_built_into_coordinates"
    if not any(m for m in difference):
        return False, "squared_distance_difference_is_constant"
    return True, "nonconstant_exact_squared_distance_difference"


def modify(dsl, site, arm):
    result = copy.deepcopy(dsl)
    if arm == "original":
        return result, []
    if arm == "row_scale":
        equalities = [i for i, c in enumerate(dsl["conditions"]) if c.get("operator") == "="]
        index = site["path"][1] if site["family"] == "equal_sides" else equalities[0]
        changes = []
        for key in ("left", "right"):
            before = result["conditions"][index][key]
            after = f"(1 + (1/100)) * ({before})"
            result["conditions"][index][key] = after
            changes.append({"path": ["conditions", index, key], "before": before, "after": after})
        return result, changes
    eps = RULES["arms"][arm]
    top, index, key = site["path"]
    before = result[top][index][key]
    if site["family"] == "equal_sides":
        after = f"(1 + ({eps})) * ({before})"
    else:
        # R=Reflect(P,L), H=(P+R)/2。Q=R+eps*(R-P)/2。
        # 軸への足（点対称なら中心）を保ち、Hからの変位を1+eps倍。
        point = site["point"]
        after = "Point(" + ", ".join(
            f"({before}).{axis} + (({eps}) / 2) * (({before}).{axis} - ({point}).{axis})"
            for axis in ("x", "y")
        ) + ")"
    result[top][index][key] = after
    return result, [{"path": site["path"], "before": before, "after": after}]


def syntax_audit(dsl, spec):
    if set(dsl) != {"id", "variables", "constructions", "conditions", "target"}:
        raise ValueError("unexpected_DSL_fields")
    declared = set(dsl["variables"])
    if len(declared) != len(dsl["variables"]):
        raise ValueError("duplicate_variable")
    symbols = {s["name"] for s in spec["symbols"]}
    for s in spec["symbols"]:
        symbols.update(s.get("aliases", []))
    # 凍結validation.pyの定数。piはdsl-spec.jsonの関数一覧にはない。
    allowed = declared | symbols | {"pi", "True", "False"}
    for c in dsl["constructions"]:
        unknown = names(c["expression"]) - allowed
        if unknown:
            raise ValueError(f"forward_or_unknown_names:{sorted(unknown)}")
        if c["name"] in allowed:
            raise ValueError(f"duplicate_or_shadowed_name:{c['name']}")
        allowed.add(c["name"])
    for source in list(expressions(dsl))[len(dsl["constructions"]):]:
        unknown = names(source) - allowed
        if unknown:
            raise ValueError(f"unknown_names:{sorted(unknown)}")


def build():
    if git("diff", FROZEN, "--", "src") or git("ls-files", "--others", "--exclude-standard", "src"):
        raise ValueError("src_differs_from_frozen")
    cases_bytes = frozen(RULES["source_cases"])
    records = [json.loads(line) for line in cases_bytes.splitlines()]
    assert len(records) == RULES["expected_universe_size"] == len({r["id"] for r in records})
    spec_bytes = frozen("src/geosolver/problem/dsl-spec.json")
    spec = json.loads(spec_bytes)
    census = []
    by_id = {}
    for record in sorted(records, key=lambda r: r["id"]):
        # answer・rating・problem_statement・既存結果は参照しない。
        ident, dsl = record["id"], record["dsl"]
        by_id[ident] = dsl
        found = motifs(dsl)
        calls = {call(n) for s in expressions(dsl) for n in ast.walk(tree(s)) if isinstance(n, ast.Call)}
        reasons = []
        if not found:
            reasons.append("no_registered_syntactic_motif")
        if not RULES["min_variables"] <= len(dsl["variables"]) <= RULES["max_variables"]:
            reasons.append("variable_count_outside_1_to_12")
        discrete = sorted(calls & set(RULES["discrete_calls"]))
        if discrete:
            reasons.append("discrete_or_disjunctive:" + ",".join(discrete))
        for motif in found:
            motif["site_rank"] = sha(RULES["site_salt"].encode() + b"|" + ident.encode() + b"|" + canonical(motif["path"]))
            ok, why = applicable(dsl, motif)
            motif.update({"applicable": ok, "applicability_reason": why})
        found.sort(key=lambda m: (RULES["family_order"].index(m["family"]), m["site_rank"]))
        site = found[0] if found else None  # 可否を見る前の規則。別の箇所へ逃げない。
        census.append({"id": ident, "n_variables": len(dsl["variables"]),
                       "dsl_sha256": sha(canonical(dsl)), "motifs": found,
                       "candidate": not reasons, "exclusion_reasons": reasons,
                       "family": site["family"] if site else None, "chosen_site": site,
                       "rank": sha((RULES["selection_salt"] + "|" + ident).encode()),
                       "selected": False})
    queues = {family: sorted([r for r in census if r["candidate"] and r["family"] == family],
                            key=lambda r: (r["rank"], r["id"])) for family in RULES["family_order"]}
    selected = []
    while len(selected) < RULES["max_selected"] and any(queues.values()):
        for family in RULES["family_order"]:
            if queues[family] and len(selected) < RULES["max_selected"]:
                selected.append(queues[family].pop(0))
    for row in selected:
        row["selected"] = True
    selected.sort(key=lambda r: r["id"])
    payloads = {}
    selection = []
    for row in selected:
        ident, site = row["id"], row["chosen_site"]
        dsl = by_id[ident]
        arms = {}
        for arm in RULES["arms"]:
            if arm != "original" and not site["applicable"]:
                arms[arm] = {"status": "not_generated", "reason": site["applicability_reason"], "file": None}
                continue
            variant, changes = modify(dsl, site, arm)
            try:
                syntax_audit(variant, spec)
                status, reason = "syntax_checked", None
            except ValueError as exc:
                status, reason = "static_invalid", str(exc)
            assert variant["id"] == dsl["id"]
            assert variant["variables"] == dsl["variables"]
            assert variant["target"] == dsl["target"]
            restored = copy.deepcopy(variant)
            for change in changes:
                top, i, key = change["path"]
                restored[top][i][key] = change["before"]
            assert restored == dsl, "unexpected_difference"
            path = f"dsl/{ident}/{arm}.json"
            payloads[path] = pretty(variant)
            arms[arm] = {"status": status, "reason": reason, "file": path,
                         "sha256": sha(payloads[path]), "changes": changes}
        selection.append({"id": ident, "family": row["family"], "rank": row["rank"],
                          "n_variables": row["n_variables"], "site": site, "arms": arms})
    files = ["src/geosolver/problem/dsl-spec.json", "src/geosolver/problem/models.py", "src/geosolver/problem/validation.py",
             "src/geosolver/geometry/operations/transforms.py",
             "src/geosolver/engine/standard/search/scipy_multistart_backend.py",
             "src/geosolver/engine/standard/orchestration/run_initial_probe.py", "pyproject.toml", "uv.lock"]
    source_manifest = {"frozen_commit": FROZEN, "src_tree": git("rev-parse", f"{FROZEN}:src").decode().strip(),
                       "cases_sha256": sha(cases_bytes), "cases_from_git_not_worktree": True,
                       "source_sha256": {path: sha(frozen(path)) for path in files},
                       "instructions_sha256": sha((ROOT / "jssa/strategy/codex-tasks-1023.md").read_bytes())}
    summary = {"stage": 1, "solver_calls": 0, "local_search_calls": 0,
               "solver_modules_imported": False, "geometry_evaluations": 0,
               "universe": len(census), "candidates": sum(r["candidate"] for r in census),
               "selected": len(selection), "selected_by_family": dict(Counter(r["family"] for r in selection)),
               "selected_applicable": sum(r["site"]["applicable"] for r in selection),
               "applicable_by_family": dict(Counter(r["family"] for r in selection if r["site"]["applicable"])),
               "selected_inapplicable": sum(not r["site"]["applicable"] for r in selection),
               "selected_inapplicable_reasons": dict(Counter(r["site"]["applicability_reason"] for r in selection if not r["site"]["applicable"])),
               "arm_status_counts": dict(Counter(a["status"] for r in selection for a in r["arms"].values())),
               "dsl_files": len(payloads),
               "detected_motifs_by_family": dict(Counter(m["family"] for r in census for m in r["motifs"])),
               "limitations": ["構文・名前参照・許可箇所だけの差分を検査した。solver側の型検査・loweringは未実行。",
                               "解の存在・全系の対称性・ヤコビアン退化・枝の合流は未検証。",
                               "no_registered_syntactic_motifは非対称の証明ではない。"]}
    table = io.StringIO(newline="")
    writer = csv.DictWriter(table, fieldnames=["id", "family", "n_variables", "applicable", "reason", "changed_path"], lineterminator="\n")
    writer.writeheader()
    for r in selection:
        writer.writerow({"id": r["id"], "family": r["family"], "n_variables": r["n_variables"],
                         "applicable": r["site"]["applicable"], "reason": r["site"]["applicability_reason"],
                         "changed_path": "/".join(str(x) for x in r["site"]["path"])})
    payloads.update({"census.json": pretty(census), "selection.json": pretty(selection),
                     "selection.csv": table.getvalue().encode(),
                     "selected-problems.txt": ("\n".join(r["id"] for r in selection) + "\n").encode(),
                     "source-manifest.json": pretty(source_manifest), "static-checks.json": pretty(summary)})
    return payloads, summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="静的成果物をメモリ内で再生成して一致を確認。書込なし。")
    args = parser.parse_args()
    if not args.check and (HERE / "prediction.lock.json").exists():
        raise SystemExit("封印済み。書き換え禁止。検査には --check を使用。")
    payloads, summary = build()
    for name, content in payloads.items():
        if len(content) >= RULES["per_file_max_bytes"]:
            raise ValueError(f"file_too_large:{name}")
        path = HERE / name
        if args.check:
            if not path.is_file() or path.read_bytes() != content:
                raise ValueError(f"artifact_mismatch:{name}")
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(content)
    expected = {name for name in payloads if name.startswith("dsl/")}
    actual = {p.relative_to(HERE).as_posix() for p in (HERE / "dsl").rglob("*.json")}
    if actual != expected:
        raise ValueError("unexpected_or_missing_DSL_files")
    print(json.dumps(summary, ensure_ascii=False))


if __name__ == "__main__":
    main()
