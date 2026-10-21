"""Round-two holdout: freeze before candidate measurements; do not use for tuning."""
from __future__ import annotations

import ast
from datetime import datetime, timezone
from fractions import Fraction
import hashlib
import json
from pathlib import Path
import random

ROOT = Path(__file__).resolve().parent / "fresh-holdout"
RNG = random.Random(202610110237)


def eq(left, right):
    return {"left": left, "operator": "=", "right": str(right)}


def positive(left):
    return {"left": left, "operator": ">", "right": "0"}


def pt(name, expression):
    return {"name": name, "expression": expression}


def problem(variables, constructions, conditions, target):
    return dict(variables=variables, constructions=constructions, conditions=conditions, target=target)


def alternate(source):
    p = json.loads(json.dumps(source))
    mapping = {v: f"q_{i}" for i, v in enumerate(p["variables"])}

    class Rename(ast.NodeTransformer):
        def visit_Name(self, node):
            return ast.copy_location(ast.Name(id=mapping.get(node.id, node.id), ctx=node.ctx), node)

    def rewrite(text):
        return ast.unparse(Rename().visit(ast.parse(str(text), mode="eval")))

    p["variables"] = [mapping[v] for v in reversed(p["variables"])]
    for item in p["constructions"]:
        item["expression"] = rewrite(item["expression"])
    for condition in p["conditions"]:
        for side in ("left", "right"):
            condition[side] = rewrite(condition[side])
        if condition["operator"] == "=":
            for side in ("left", "right"):
                condition[side] = f"(-13/17)*({condition[side]})"
    p["conditions"] = list(reversed(p["conditions"])) + [eq("0", "0")]
    p["target"] = rewrite(p["target"])
    return p


entries = []


def add(family, index, p, answers, proof):
    entries.append((family, index, p, list(map(str, answers)), proof))


for i in range(4):
    a, b, c = RNG.sample(range(2, 12), 3)
    roots = [-a, b, c]
    add("symmetric_cubic", i, problem(["x", "y", "z"], [], [
        eq("x+y+z", sum(roots)),
        eq("x*y+y*z+z*x", -a*b+b*c-a*c), eq("x*y*z", -a*b*c),
    ], "x"), roots,
        "The three coordinates are roots of the fixed monic cubic whose elementary symmetric coefficients are constrained; its distinct real roots are -a,b,c. All permutations exist.")
    add("hyperbola_section", i, problem(["x", "y"], [], [
        eq("x*y", a*b), eq("x+y", a+b), positive("x"), positive("y"),
    ], "x-y"), [a-b, b-a],
        "x and y are the two positive roots a,b of t^2-(a+b)t+ab; both orders satisfy every condition.")
    add("ellipse_section", i, problem(["x", "y"], [pt("P", "Point(x,y)")], [
        eq(f"x**2/{a*a}+y**2/{b*b}", 1), eq(f"{a}*y", f"{b}*x"),
    ], "x"), [f"-{a}/sqrt(2)", f"{a}/sqrt(2)"],
        "Substitution y=b*x/a gives 2*x^2/a^2=1; both real signs are permitted.")
    aa = a*a
    add("parabola_circle", i, problem(["x", "y"], [pt("O", "Point(0,0)"), pt("P", "Point(x,y)")], [
        eq("y", f"x**2-{aa+1}"), eq("Distance(O,P)**2", aa+1),
    ], "x"), [-a, a, f"-sqrt({aa+1})", f"sqrt({aa+1})"],
        "Writing t=x^2 reduces the circle equation to (t-a^2)*(t-a^2-1)=0. Both t values are positive and both x signs are valid; y is -1 or 0.")
    add("singular_sum_squares", i, problem(["x", "y"], [], [
        eq(f"(x-{a})**2+(y+{b})**2", 0),
        eq(f"{c}*((x-{a})**2+(y+{b})**2)", 0),
    ], "x*y"), [-a*b],
        "Each real square is nonnegative, so the sum vanishes iff x=a,y=-b. The second row is redundant; the Jacobian vanishes at the solution.")
    xvalue = Fraction(a*a+b*b-c*c, 2*(a+c))
    add("signed_norm", i, problem(["x"], [pt("O", "Point(0,0)"), pt("P", f"Point(x-{a},{b})")], [
        eq("Distance(O,P)", f"x+{c}"), positive(f"x+{c}"),
    ], "x"), [xvalue],
        "Squaring gives the linear equation 2(a+c)x=a^2+b^2-c^2. At that root x+c=((a+c)^2+b^2)/(2(a+c))>0, so squaring has introduced no extra root.")
    k = a
    add("tangent_line_circle", i, problem(["x", "y"], [pt("O", "Point(0,0)"), pt("P", "Point(x,y)")], [
        eq("4*y-3*x", 5*k), eq("Distance(O,P)", k),
    ], "x+y"), [Fraction(k,5)],
        "The line has distance k from the origin. Equality in Cauchy-Schwarz forces (x,y)=(-3k/5,4k/5), giving a unique tangency point and target k/5.")
    add("right_incircle_scale", i, problem(["x", "y"], [
        pt("O", "Point(0,0)"), pt("A", "Point(x,0)"), pt("B", "Point(0,y)"), pt("K", "Incircle(O,A,B)"),
    ], [eq("3*x", "4*y"), positive("x"), positive("y"), eq("Radius(K)", k)],
        "Distance(O,A)+Distance(A,B)+Distance(B,O)"), [12*k],
        "Positive legs in ratio 4:3 equal (4s,3s); hypotenuse is 5s and the inradius is s. Radius k fixes s=k and perimeter 12k.")
    add("periodic_target", i, problem(["t"], [], [eq("sin(t)**2", Fraction(a, a+b))], "cos(2*t)"),
        [Fraction(b-a,a+b)],
        "0<a/(a+b)<1 has infinitely many real t; the identity cos(2t)=1-2 sin(t)^2 fixes exactly one target value for every solution.")
    add("rational_hole", i, problem(["x"], [], [eq(f"((x-{a})*(x-{b}))/(x-{a})", 0)], "x"), [b],
        "The original denominator excludes x=a. At every other x the expression equals x-b, so the distinct x=b is the sole solution.")
    add("oriented_similarity_target", i, problem(["x", "y"], [
        pt("O", f"Point({a},{b})"), pt("A", f"Point({a}+x,{b}+y)"), pt("B", f"Point({a}-{c}*y,{b}+{c}*x)"),
    ], [positive("Distance(O,A)")], "Area(O,A,B)/Distance(O,A)**2"), [Fraction(c,2)],
        "The two displacement vectors are v=(x,y) and c*R90(v). Their determinant is c*(x^2+y^2)>0 and squared first length is x^2+y^2. All nonzero v have target c/2.")

if ROOT.exists():
    raise SystemExit("Refusing to overwrite a frozen holdout")
(ROOT / "dsl").mkdir(parents=True)
rows, proofs = [], []
for family, index, p, answers, proof in entries:
    for form in range(2):
        identifier = f"{family}-{index}-form{form}"
        dsl = {"id": identifier, **(alternate(p) if form else p)}
        path = ROOT / "dsl" / f"{identifier}.json"
        path.write_text(json.dumps(dsl, indent=2) + "\n")
        rows.append(dict(id=identifier, source="round-two analytic holdout", dsl_path=f"dsl/{identifier}.json", dsl=dsl,
                         answer=answers, authoring_status="runnable", truth_status="verified", dedupe_key=identifier))
        proofs.append(dict(id=identifier, family=family, parameter_index=index, equivalent_form=form, derivation=proof))
payload = "".join(json.dumps(row, sort_keys=True) + "\n" for row in rows)
(ROOT / "cases.jsonl").write_text(payload)
(ROOT / "derivations.json").write_text(json.dumps(proofs, indent=2) + "\n")
manifest = dict(created_at=datetime.now(timezone.utc).isoformat(), seed=202610110237, count=len(rows),
                family_count=len({entry[0] for entry in entries}), families=sorted({entry[0] for entry in entries}),
                cases_sha256=hashlib.sha256(payload.encode()).hexdigest(), generator_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                policy="Freeze before evaluating experimental candidates; do not solve baseline or candidate holdout until final candidate selection. Do not tune after results. Parameter and representation variants are dependent samples, not distinct structural families.")
(ROOT / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
print(json.dumps(manifest, indent=2))
