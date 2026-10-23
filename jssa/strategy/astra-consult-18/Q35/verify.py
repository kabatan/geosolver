"""Independent checks of counts, input integrity, and small exact certificates.

Does not re-run the optimizer or Groebner bases. The --replay-census option
rebuilds the census in a disposable Q35 subdirectory, preserving the locked files.
"""
from __future__ import annotations
import argparse
import contextlib
import csv
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
from datetime import datetime, timezone

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
sys.path.insert(0, str(ROOT / "jssa/strategy/astra-consult-17/L"))
from verify_certificate import verify as fraction_verify
import sympy as sp


def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def table(p): return list(csv.DictReader(p.open()))


def check_linear(arm, target):
    fs = list(map(sp.sympify, arm["input_equations"]))
    vs = list(map(sp.Symbol, arm["input_variables"]))
    for step in arm["linear_substitutions"]:
        assert fs == list(map(sp.sympify, step["before_equations"]))
        v, value = sp.Symbol(step["variable"]), sp.sympify(step["value"])
        assert v in vs and v != target and v not in value.free_symbols
        i = step["pivot_index"]
        pivot = fs[i]
        assert sp.expand(pivot - sp.sympify(step["pivot"])) == 0
        a = sp.diff(pivot, v)
        assert a.is_Rational and a != 0
        assert sp.expand(pivot.subs(v, value)) == 0
        # Recompute the entire transform, independently of the reducer's choices.
        fs = list(dict.fromkeys(sp.expand(f.subs(v, value)) for j, f in enumerate(fs) if j != i))
        fs = [f for f in fs if f != 0]
        assert fs == list(map(sp.sympify, step["after_equations"]))
        vs.remove(v)
    assert fs == list(map(sp.sympify, arm["output_equations"]))
    assert [v for v in vs if v != target] + [target] == list(map(sp.Symbol, arm["output_variables"]))
    return len(arm["linear_substitutions"])


def sparse_expr(data, vs):
    return sp.expand(sum(sp.Rational(c)*sp.prod(v**k for v,k in zip(vs, m, strict=True)) for m,c in data))


def main(replay=False):
    lock = json.loads((HERE / "prediction.lock.json").read_text())
    for path, dig in lock["files"].items(): assert sha(ROOT / path) == dig, path
    src = subprocess.check_output(["git", "rev-parse", "HEAD:src"], cwd=ROOT, text=True).strip()
    assert src == lock["src_tree"]
    assert not subprocess.check_output(["git", "diff", lock["solver_commit"], "--", "src", "benchmarks/cases.jsonl", "pyproject.toml", "uv.lock"], cwd=ROOT)
    manifest = json.loads((HERE / "source-manifest.json").read_text())
    for path, metadata in manifest.items():
        assert sha(ROOT / path) == metadata["sha256"]
        assert (ROOT / path).stat().st_size == metadata["bytes"]
    h = {r["id"]:r for r in table(ROOT / "jssa/strategy/astra-consult-17/H/classification.csv")}
    original = {r["id"]:r for r in table(ROOT / "jssa/difficulty/certify-all/per-case.csv")}
    counts = {}
    for g, labels in (("G", {"G"}), ("I", {"L0","R0"})):
        ids = [cid for cid,r in h.items() if r["evidence_code"] in labels]
        counts[g] = [sum(original[cid]["status"] == "certified_saved_endpoint_set" for cid in ids), len(ids)]
    assert counts == {"G": [6,16], "I": [1,38]}
    systems_checked = 0; substitutions = 0; certificates = 0; families = 0
    for kind in ("paired", "components"):
        for path in sorted((HERE / kind).glob("*.json")):
            d = json.loads(path.read_text())
            rr = original[d["id"]]
            syspath = (ROOT / "jssa/difficulty/certify-all" / rr["result_path"]).parent / "system.json"
            system = json.loads(syspath.read_text())
            target = sp.Symbol(system["target"])
            orig = list(map(sp.sympify, system["F_saturated"]))
            extra = list(map(sp.sympify, d.get("additional_equations", [])))
            for i, a in enumerate(d["arms"]):
                expected = orig + (extra if kind == "components" and i == 1 else [])
                assert expected == list(map(sp.sympify, a["input_equations"]))
                substitutions += check_linear(a, target)
                systems_checked += 1
                if a["certificate_verified"]:
                    c = json.loads((HERE / a["certificate_path"]).read_text())
                    assert fraction_verify(c)
                    vs = list(map(sp.Symbol, c["variables"]))
                    assert c["variables"] == a["output_variables"]
                    assert [sparse_expr(f, vs) for f in c["F"]] == list(map(sp.sympify, a["output_equations"]))
                    q = sparse_expr(c["Q"], vs)
                    assert q.free_symbols <= {target}
                    assert sp.Poly(q, target).degree() > 0
                    assert sp.expand(sp.Poly(q, target).sqf_part().monic().as_expr() - sp.sympify(d["predicted_eliminant_sqf"])) == 0
                    certificates += 1
            if kind == "components":
                good = {sp.Symbol(k): sp.sympify(v) for k,v in d["allowed_witness"].items()}
                bad = {sp.Symbol(k): sp.sympify(v) for k,v in d["forbidden_family"].items()}
                assert all(sp.simplify(f.subs(good)) == 0 for f in orig + extra)
                assert all(sp.simplify(f.subs(bad)) == 0 for f in orig)
                assert sp.diff(bad[target], sp.Symbol("w")) != 0
                assert all(d["witness_side_checks"].values())
                families += 1
                if d["id"] == "AIME-2009-I-12":
                    # The only root compatible with the strict triangle bound.
                    poly = sp.Poly(sp.sympify(d["predicted_eliminant_sqf"]), target)
                    assert poly.count_roots(2, sp.oo) == 1 and poly.eval(sp.Rational(8,3)) == 0
                elif d["id"] == "HMMT-2006-FEB-GEO-01":
                    # Explicit realification p2=p3=0 and sqrt(2)>0 fix the sign.
                    ss = sp.Symbol("s1"); f0,f1 = orig[:2]; f2=orig[2]; f5=orig[5]
                    p2,p3,g,hh = sp.symbols("p2 p3 v_g v_h")
                    assert sp.expand(f1+f2-ss*(p2+p3+g-2)) == 0
                    assert sp.expand(f1-2*f0-(ss*p2+ss-hh+4)) == 0
                    assert sp.expand(f5-(target-g-hh-14)) == 0
                    assert sp.simplify(good[target]-(20+sp.sqrt(2))) == 0
                else:
                    poly = sp.Poly(sp.sympify(d["predicted_eliminant_sqf"]), target)
                    assert poly.count_roots(0, sp.oo) == 1 and poly.eval(12) == 0
    seed = json.loads((HERE / "seed-candidates.json").read_text())
    for path, dig in seed["source_sha256"].items(): assert sha(ROOT / path) == dig
    selected = [r for r in seed["cases"] if r["certified_seed0"]]
    assert len(selected) == 7 and all(r["n1"] > 0 and r["same_numeric_candidate_set"] for r in selected)
    es = json.loads((HERE / "experiment-summary.json").read_text())
    assert [v["successes"] for v in es["predictions"].values()] == [3,0,0,7]
    assert [v["passed"] for v in es["predictions"].values()] == [True,False,False,True]
    assert systems_checked == 18 and certificates == 3 and families == 3
    census_replayed = False
    replay_heads = None
    if replay:
        spec = importlib.util.spec_from_file_location("q35_reanalysis", HERE / "analyze.py")
        module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
        with tempfile.TemporaryDirectory(prefix="replay-", dir=HERE) as dest:
            module.HERE = Path(dest)
            with contextlib.redirect_stdout(io.StringIO()): module.main()
            for name in ("case-matrix.csv", "strata.csv", "archived-certificates.csv", "source-manifest.json"):
                assert (Path(dest)/name).read_bytes() == (HERE/name).read_bytes(), name
            new = json.loads((Path(dest)/"summary.json").read_text())
            old = json.loads((HERE/"summary.json").read_text())
            new.pop("created_utc"); old.pop("created_utc")
            # This is a shared checkout: other work can advance HEAD. All
            # actual input hashes and the frozen src tree were checked above.
            replay_heads = {"archived": old.pop("archive_head"), "current": new.pop("archive_head")}
            assert new == old
        census_replayed = True
    files = [p for p in HERE.rglob("*") if p.is_file()]
    assert all(p.stat().st_size < 5_000_000 for p in files)
    out = {"verified_utc": datetime.now(timezone.utc).isoformat(), "lock_intact": True,
           "original_sources_unchanged": len(manifest), "seed_source_hashes_checked": len(seed["source_sha256"]),
           "src_tree": src, "frozen_src_and_cases_and_dependencies_unchanged": True, "counts": counts,
           "arms_checked": systems_checked, "constant_coefficient_substitutions_checked": substitutions,
           "independent_Fraction_certificates": certificates, "exact_nonconstant_forbidden_families": families,
           "exact_allowed_witnesses": 3, "prediction_successes": [3,0,0,7],
           "census_replayed_identically_except_timestamp_and_head_metadata": census_replayed,
           "replay_archive_heads": replay_heads,
           "files_below_5MB": True, "largest_file_bytes": max(p.stat().st_size for p in files),
           "total_directory_bytes_before_this_receipt": sum(p.stat().st_size for p in files)}
    (HERE/"verification.json").write_text(json.dumps(out, ensure_ascii=False, indent=2)+"\n")
    print(json.dumps(out, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    p = argparse.ArgumentParser(); p.add_argument("--replay-census", action="store_true")
    main(p.parse_args().replay_census)
