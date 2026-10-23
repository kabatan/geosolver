"""Audit saved results only; never start numerical search or change the protocol."""
import hashlib
import json
from decimal import Decimal
from pathlib import Path

HERE = Path(__file__).resolve().parent
VARIANTS = ("E", "S", "L", "G", "Q", "GQ", "P")
inputs = json.loads((HERE / "inputs.json").read_text())
summary = json.loads((HERE / "summary.json").read_text())
paths = sorted((HERE / "runs").glob("*.json"))
rows = [json.loads(p.read_text()) for p in paths]
by = {(r["index"], r["variant"]): r for r in rows}
assert len(rows) == len(by) == len(inputs) * len(VARIANTS) == 84
assert set(by) == {(i, v) for i in range(len(inputs)) for v in VARIANTS}
for r in rows:
    assert r["id"] == inputs[r["index"]]["id"]
    for o in r["outputs"]:
        if o.get("norm") is None or o.get("error") is None:
            assert not o["high"] and not o["low"]
            continue
        valid = all(o.get(k) for k in ("guard", "hard", "inside"))
        assert o["high"] == bool(valid and Decimal(o["norm"]) <= Decimal("1e-60")
                                 and Decimal(o["error"]) <= Decimal("1e-50"))
        assert o["low"] == bool(valid and Decimal(o["norm"]) <= Decimal("1e-8")
                                and Decimal(o["error"]) <= Decimal("1e-6"))
    assert r["high"] == any(o["high"] for o in r["outputs"])
    assert r["low"] == any(o["low"] for o in r["outputs"])

success = {v: {i for i in range(len(inputs)) if by[i, v]["high"]} for v in VARIANTS}
for v in VARIANTS:
    assert len(success[v]) == summary["tallies"][v]["high"]
    assert sum(by[i, v]["low"] for i in range(len(inputs))) == summary["tallies"][v]["low"]

def ids(indices):
    return [inputs[i]["id"] for i in sorted(indices)]

def correct_refs(i, v):
    return {o["ref"] for o in by[i, v]["outputs"] if o["high"]}

same_qe = {i for i in range(len(inputs)) if correct_refs(i, "Q") & correct_refs(i, "E")}
assert len(same_qe) == summary["H2"]["Q_same_ref_as_E"]
assert len(success["E"] - success["G"]) == summary["H1"]["E_not_G"]
assert len(success["Q"] - success["GQ"]) == summary["H2"]["Q_not_GQ"]

phase_report = {}
for v in ("E", "P", "Q"):
    phase_report[v] = {}
    for i in range(len(inputs)):
        histories = [h for hs in by[i, v]["phase_history"] for h in hs]
        phase_report[v][inputs[i]["id"]] = dict(
            recorded_warm_newton=any(":warm_newton:" in h for h in histories),
            recorded_findroot_precisions=sorted({int(h.split(":")[0]) for h in histories if ":findroot:" in h}),
            high=by[i, v]["high"],
            timeout=by[i, v]["numerical_timeout"],
        )

errors = [dict(id=r["id"], variant=r["variant"], status=r["status"],
               error=r.get("numerical_error"), score_error=r.get("score_error"))
          for r in rows if "error" in r["status"] or r.get("score_error")]
report = dict(
    checks="84 unique records; saved scalar criteria, aggregation, reference intersections verified",
    no_new_search=True,
    successful_ids={v: ids(s) for v, s in success.items()},
    E_and_G_success_sets_equal=success["E"] == success["G"],
    E_and_P_success_sets_equal=success["E"] == success["P"],
    Q_preserves_E_successes=len(same_qe), E_successes=len(success["E"]),
    Q_extra_over_E=ids(success["Q"] - success["E"]),
    Q_extra_over_GQ=ids(success["Q"] - success["GQ"]),
    errors=errors, phases=phase_report,
    note="Preregistration's final-120-digits wording is inaccurate: schedule_dps ends at 120, but unchanged closure polishes may run at 250, 350 and 500. E/P also share a 120-digit warm Newton before LM. G/GQ are 120-digit raw-equation Newton only.",
    hashes={str(p.relative_to(HERE)): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths},
)
(HERE / "result-audit.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
print(json.dumps({k: report[k] for k in ("checks", "E_and_G_success_sets_equal", "E_and_P_success_sets_equal", "Q_preserves_E_successes", "E_successes", "Q_extra_over_E", "Q_extra_over_GQ", "errors")}, ensure_ascii=False))
