"""Build DSL variants with k extra variable points (dose-response of extra variables).

Rule (fixed before any run, same rules as rewrite experiment C): take the
point-returning constructions of the supported kinds in order of appearance
and replace the first k of them by a free point Point(xN, yN) plus two
equations that characterise the original construction uniquely.  The
original conditions, guards and target are not touched; the point keeps its
name, so every reference still points to the same point.

Supported kinds (each adds 2 variables and 2 equations):
  M = Midpoint(P, Q)                 Vector(P, M).x = Vector(M, Q).x, same for .y
  X = Intersect(L1, L2), Li = Line(P, Q) (inline or named)
                                     Collinear(P1, Q1, X) = 0, Collinear(P2, Q2, X) = 0
  H = FootOfPerpendicular(P, Line(U, V))
                                     Collinear(U, V, H) = 0, Dot(Vector(H, P), Vector(U, V)) = 0
  O = Circumcenter(A, B, C)          Distance(O, A) = Distance(O, B), Distance(O, A) = Distance(O, C)

Usage: python expand_k.py OUT_DIR [--kmax 3] [--min-eligible 3]
Writes OUT_DIR/<id>.k<k>.json for k = 0..min(kmax, eligible) and OUT_DIR/manifest.json.
"""

from __future__ import annotations

import argparse
import copy
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

LINE_RE = re.compile(r"^\s*Line\(\s*(\w+)\s*,\s*(\w+)\s*\)\s*$")


def split_args(text: str) -> list[str]:
    depth, cur, out = 0, "", []
    for ch in text:
        if ch == "," and depth == 0:
            out.append(cur.strip()); cur = ""; continue
        if ch in "([":
            depth += 1
        elif ch in ")]":
            depth -= 1
        cur += ch
    if cur.strip():
        out.append(cur.strip())
    return out


def head_args(expr: str):
    m = re.match(r"^\s*(\w+)\((.*)\)\s*$", expr)
    if not m:
        return None, []
    return m.group(1), split_args(m.group(2))


def resolve_line(arg: str, named_lines: dict[str, tuple[str, str]]):
    m = LINE_RE.match(arg)
    if m:
        return m.group(1), m.group(2)
    return named_lines.get(arg.strip())


def rule_for(name: str, expr: str, named_lines, point_names) -> list[str] | None:
    head, args = head_args(expr)
    ok = lambda xs: all(x in point_names for x in xs)  # noqa: E731
    if head == "Midpoint" and len(args) == 2 and ok(args):
        p, q = args
        return [f"Vector({p}, {name}).x = Vector({name}, {q}).x",
                f"Vector({p}, {name}).y = Vector({name}, {q}).y"]
    if head == "Intersect" and len(args) == 2:
        l1 = resolve_line(args[0], named_lines)
        l2 = resolve_line(args[1], named_lines)
        if l1 and l2 and ok(l1) and ok(l2):
            return [f"Collinear({l1[0]}, {l1[1]}, {name}) = 0",
                    f"Collinear({l2[0]}, {l2[1]}, {name}) = 0"]
    if head == "FootOfPerpendicular" and len(args) == 2:
        line = resolve_line(args[1], named_lines)
        if line and ok([args[0], *line]):
            u, v = line
            return [f"Collinear({u}, {v}, {name}) = 0",
                    f"Dot(Vector({name}, {args[0]}), Vector({u}, {v})) = 0"]
    if head == "Circumcenter" and len(args) == 3 and ok(args):
        a, b, c = args
        return [f"Distance({name}, {a}) = Distance({name}, {b})",
                f"Distance({name}, {a}) = Distance({name}, {c})"]
    return None


def eligible(dsl: dict):
    named_lines, point_names, out = {}, set(), []
    for i, c in enumerate(dsl.get("constructions", [])):
        name, expr = c["name"], c["expression"]
        m = LINE_RE.match(expr)
        if m:
            named_lines[name] = (m.group(1), m.group(2))
        rule = rule_for(name, expr, named_lines, point_names)
        head, _ = head_args(expr)
        if head in {"Point", "Midpoint", "Intersect", "FootOfPerpendicular", "Circumcenter",
                    "Incenter", "Centroid", "Orthocenter", "Reflect", "Rotate", "PointOnSegment",
                    "PointOnLine", "PointOnCircle", "ContactPoint", "IncircleContactPoint", "Center"}:
            point_names.add(name)
        if rule:
            out.append((i, name, rule))
    return out


def expand(dsl: dict, k: int, picks) -> dict:
    new = copy.deepcopy(dsl)
    new_vars = list(new.get("variables", []))
    for i, name, rule in picks[:k]:
        xv, yv = f"x_{name}", f"y_{name}"
        new_vars += [xv, yv]
        new["constructions"][i] = {"name": name, "expression": f"Point({xv}, {yv})"}
        for eq in rule:
            left, right = eq.split(" = ")
            new["conditions"].append({"left": left, "operator": "=", "right": right})
    new["variables"] = new_vars
    new["id"] = f"{dsl.get('id', '')}.k{k}"
    return new


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("out_dir")
    ap.add_argument("--kmax", type=int, default=3)
    ap.add_argument("--min-eligible", type=int, default=3)
    ap.add_argument("--max-vars", type=int, default=4)
    args = ap.parse_args()
    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    manifest = []
    for line in (ROOT / "benchmarks" / "cases.jsonl").open():
        case = json.loads(line)
        dsl = case["dsl"]
        nv = len(dsl.get("variables", []))
        if not (1 <= nv <= args.max_vars):
            continue
        picks = eligible(dsl)
        if len(picks) < args.min_eligible:
            continue
        kmax = min(args.kmax, len(picks))
        for k in range(kmax + 1):
            variant = expand(dsl, k, picks)
            (out / f"{case['id']}.k{k}.json").write_text(json.dumps(variant, ensure_ascii=False, indent=1))
        manifest.append({"id": case["id"], "n_vars": nv, "eligible": [p[1] for p in picks], "kmax": kmax})
    (out / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=1))
    print(len(manifest), "cases")


if __name__ == "__main__":
    main()
