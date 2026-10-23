"""Preregistered five contradictions, derived from certified values, no oracle."""
import copy
from functools import cmp_to_key
import json
from pathlib import Path
import sympy as s

from exact_onevar import exact_sign, root_from_wire

HERE = Path(__file__).resolve().parent


def explicit(w):
    if "rational" in w:
        return s.Rational(w["rational"])
    if "op" in w:
        return {"Add": s.Add, "Mul": s.Mul, "Pow": s.Pow}[w["op"]](*(explicit(a) for a in w["args"]))
    z = s.Symbol("z")
    p = s.Poly.from_list([s.Rational(c) for c in w["poly_coefficients"]], z)
    candidate = p.all_roots(radicals=True)[w["index"]]
    if candidate.has(s.CRootOf):
        raise ValueError("no supported explicit radical representation for this fixed case")
    assert exact_sign(candidate - root_from_wire(w)) == 0
    return candidate


def main():
    gen = HERE / "pilot-v2"
    certs = []
    for path in sorted(gen.glob("*.json")):
        data = json.loads(path.read_text())
        if data.get("status") == "complete" and data["answer_set"]:
            certs.append(data)
    chosen = certs[:5]
    assert len(chosen) == 5
    out = HERE / "contradiction-inputs"
    out.mkdir(exist_ok=False)
    manifest = []
    for cert in chosen:
        src = json.loads((HERE / "inputs" / (cert["id"] + ".json")).read_text())
        values = [explicit(w) for w in cert["answer_set"]]
        maximum = sorted(values, key=cmp_to_key(lambda a, b: exact_sign(a-b)))[-1]
        upper = s.simplify(maximum + 1)
        new = copy.deepcopy(src)
        new_id = cert["id"] + "__contradiction"
        new["id"] = new_id
        new["dsl"]["id"] = new_id
        added = {"left": new["dsl"]["target"], "operator": ">", "right": str(upper)}
        new["dsl"]["conditions"].append(added)
        (out / (new_id + ".json")).write_text(json.dumps(new, ensure_ascii=False, indent=2) + "\n")
        manifest.append({"id": new_id, "source_id": cert["id"], "maximum_certified_value": str(maximum),
                         "added_condition": added, "expected": "empty set"})
    (HERE / "contradiction-manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(manifest, ensure_ascii=False))


if __name__ == "__main__":
    main()
