"""Post-run recheck; never changes or upgrades a measured result.

Rebuild F and s from the frozen input; check each archived identity with Fraction;
recompute the original-domain bounds and candidate-set root comparison. This is
validation time, reported separately from the preregistered measurement.
"""
import hashlib
import json
import os
from pathlib import Path
import sys
import time

os.environ["PYTHONHASHSEED"] = "0"
sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from worker import (sp, encode, verify, stable_json, check_roots, target_bounds, deadline)
from certificate import sparse, Prover, make_certificate
from result_paths import result_path, results


def audit_one(cid):
    out = result_path(cid).parent
    result = json.loads((out / "result.json").read_text())
    inp = HERE / "inputs" / f"{cid}.json"
    case = json.loads(inp.read_text())
    rec = {"id": cid, "measured_status": result["status"], "checks": [], "pass": True}
    start = time.monotonic()
    try:
        with deadline(60):
            assert hashlib.sha256(inp.read_bytes()).hexdigest() == result["input_sha256"]
            sy, t, fs, vs, nd = encode(case["dsl"])
            system = {"variables": list(map(str, vs)), "F_saturated": list(map(str, fs)), "nondeg_factors": list(map(str, nd)), "target": str(t)}
            assert hashlib.sha256(stable_json(system)).hexdigest() == result["system_sha256"]
            rec["checks"].append("input_and_rebuilt_system_sha256_match")
            bounds, proof = target_bounds(case["dsl"])
            assert proof == result["bound_derivation"]
            rec["checks"].append("bounds_rebuilt_from_original_DSL")
            candidates = [{"P_expr": sp.sympify(c["P"], locals={str(t): t}), "root_interval_exact": tuple(sp.Rational(x) for x in c["root_interval"])}
                          for c in result["candidates"] if c.get("candidate_status") == "proposed"]
            identity_checks = []
            regenerated_provers = {}
            for ident in result["identities"]:
                detail = {"kind": ident["kind"], "runtime_verified": ident["verified_fraction"], "raw_saved": ident["raw_saved"]}
                if ident["raw_saved"]:
                    cert = json.loads((out / f"certificate-{ident['kind']}.json").read_text())
                    assert hashlib.sha256(stable_json(cert)).hexdigest() == ident["sha256"]
                    vv = [sp.Symbol(v) for v in cert["variables"]]
                    original = fs[:-1] if sp.Symbol("zz") in vs else fs
                    assert cert["F"] == [sparse(f, vv) for f in original]
                    assert cert["s"] == sparse(sp.prod(nd) if sp.Symbol("zz") in vs else sp.Integer(1), vv)
                    assert verify(cert)
                    detail["archived_identity_rechecked"] = True
                else:
                    detail["archived_identity_rechecked"] = False
                    order = "lex" if ident["kind"] == "E_lex" else "grevlex"
                    if order not in regenerated_provers:
                        vv = [v for v in vs if v != t] + [t] if order == "lex" else vs
                        regenerated_provers[order] = Prover(fs, vv, order=order)
                    pr = regenerated_provers[order]
                    q = sp.sympify(ident["Q"], locals={str(t): t})
                    cofs = pr.coefficients(q)
                    assert cofs is not None
                    cert = make_certificate(fs, pr.vs, nd, q, cofs)
                    assert hashlib.sha256(stable_json(cert)).hexdigest() == ident["sha256"]
                    assert verify(cert)
                    detail["regenerated_identity_hash_matches_and_fraction_rechecked"] = True
                if "root_check" in ident:
                    q = sp.sympify(ident["Q"], locals={str(t): t})
                    recomputed = check_roots(q, t, bounds, candidates)
                    assert recomputed == ident["root_check"]
                    detail["root_check_recomputed"] = True
                identity_checks.append(detail)
            rec["identity_checks"] = identity_checks
            if result["status"] == "certified_saved_endpoint_set":
                chosen = next(r for r in result["identities"] if r["kind"] == result["certificate_kind"])
                assert chosen["root_check"]["set_complete"] and chosen["verified_fraction"]
                assert len(candidates) == result["saved_candidate_count"]
                rec["checks"].append("whole_saved_candidate_set_certified")
    except Exception as e:
        rec.update({"pass": False, "error": type(e).__name__ + ": " + str(e)[:300]})
    rec["seconds"] = time.monotonic() - start
    return rec


def main():
    if len(sys.argv) > 1:
        print(json.dumps(audit_one(sys.argv[1]), ensure_ascii=False)); return
    rows = []
    for rp in results():
        r = json.loads(rp.read_text())
        if not r.get("identities"): continue
        row = audit_one(r["id"])
        rows.append(row)
        print(r["id"], row["pass"], round(row["seconds"], 3), flush=True)
        (HERE / "validation.json").write_text(json.dumps({
            "all_pass": all(x["pass"] for x in rows), "cases_checked": len(rows),
            "validation_seconds": sum(x["seconds"] for x in rows), "cases": rows,
        }, indent=2, ensure_ascii=False) + "\n")


if __name__ == "__main__": main()
