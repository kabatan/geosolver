"""Answer-level manual audit against DISCOVERY_RUBRIC.md; never used in prompts."""
import argparse
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = Path("qwen/.runtime/qwen35_sft_pilot_20260924")

# Each entry: final adopted main claim true, proof acceptable, concrete correct use,
# then an audit note. Earlier errors explicitly withdrawn are not counted as final errors.
BASE = {
    "H01-discovery-0": (True, True, True, "Derives MP*AM=BC^2/4 by orthocenter coordinates and projection; BC=10, AM=6 gives MP=25/6."),
    "H01-discovery-1": (True, True, False, "Derives AP=bc cos(A)/AM and MP=a^2/(4AM), but the final example evaluates 35*(19/35) as 95; the reported AP is five times too large. The unused displayed u-sign is also wrong."),
    "DA15-discovery-0": (True, True, True, "After withdrawing false guesses, derives angle BFC=2A from the two perpendicular-bisector isosceles triangles and computes 120 degrees for A=60 degrees."),
    "DA15-discovery-1": (True, True, False, "Derives B,C,F,O concyclic via angle BFC=angle BOC=2A, but gives no solved numerical length or angle example; one proposed diameter interpretation is also wrong."),
    "DA01-discovery-0": (True, False, True, "Correctly derives AT^2=BT*CT and a consistent numeric instance, but retains false additional conclusions BT:CT=AB:AC (the actual ratio is squared) and a false T-position assertion, so the whole argument fails the unretracted-error rule."),
    "DA01-discovery-1": (False, False, False, "Adopts BT/CT=AB/AC, BT*CT=AB*AC, and angle BTC=90 degrees; these do not hold generally. The similarity correspondence and numerical use are invalid."),
    "DA08-discovery-0": (False, False, False, "Runs out of tokens after asserting AQ perpendicular MN without proof. Counterexample: B=(-1,0), C=(1,0), A=(1/5,17/10) gives O=(0,193/340), Q=(0,-340/193); AQ dot AC is nonzero while MN is parallel to AC."),
    "DA08-discovery-1": (False, False, False, "Runs out of tokens during conjectures and coordinate exploration, without a final proved and applied relation."),
}

AFTER = {
    "H01-discovery-0": (True, True, True, "Derives MP*AM=R^2-OM^2 by the orthocenter vector identity and projection; a feasible example R=10, OM=6, AM=15 gives MP=64/15."),
    "H01-discovery-1": (False, False, False, "Runs out of tokens while adopting the generally false angle MHP=MAC; no complete proof or computed example."),
    "DA15-discovery-0": (False, False, False, "Runs out of tokens after adopting the false conjecture that F lies on the A-angle bisector; no completed proof or use."),
    "DA15-discovery-1": (True, True, False, "Derives B,C,O,F concyclic, but the proposed Ptolemy application has the chords in the wrong order: it gives OF=R(BF+CF)/BC instead of R*abs(BF-CF)/BC. An exact rational triangle yields OF=0.13435 versus the claimed 1.32002; no solved numerical use is supplied."),
    "DA01-discovery-0": (False, False, False, "Runs out of tokens in conflicting cyclicity and tangent-chord conjectures; does not settle on a proved and applied general relation."),
    "DA01-discovery-1": (False, False, False, "Runs out of tokens after finding a right-triangle counterexample to its own wrong BT/CT=AB/AC conjecture, without producing the corrected general relation or use."),
    "DA08-discovery-0": (False, False, False, "Adopts the false AQ perpendicular MN conjecture even after its attempted numeric check contradicts it; the decisive dot-product calculation is omitted. Exact scalene witness in verify_discovery_claims.py."),
    "DA08-discovery-1": (False, False, False, "Runs out of tokens before choosing and applying a general relation. It correctly recognizes en route that Q is the tangent intersection at B and C, a useful partial observation."),
}

DOSE = {
    "H01-discovery-0": (True, True, False, "After explicitly rejecting false candidate formulas, derives MP*AM=BC^2/4 using AH=2 OM, the projection onto AM, Apollonius and the cosine rule. It gives limiting checks but no concrete numeric worked use."),
    "H01-discovery-1": (True, True, True, "Derives MP*AM=BC^2/4 from orthocenter coordinates and the projection dot product. BC=6, AM=4 gives MP=9/4. Its numeric triangle is acute isosceles, outside the requested scalene subclass, but the proved relation and construction remain valid there; this is a weaker use example."),
    "DA15-discovery-0": (True, True, False, "Withdraws the false F,O,M collinearity conjecture and correctly derives B,C,O,F concyclic via angle BFC=angle BOC=2A. The proposed BF*CF application leaves the value unsolved and uses the false OF=new-circle-radius and a wrong Ptolemy order."),
    "DA15-discovery-1": (False, False, False, "Adopts the false assertion F=(O+M)/2 without doing the intersection algebra. The acute scalene rational triangle in verify_discovery_claims.py has F_x=393/2930 whereas (O+M)_x/2=0; no valid numerical use follows."),
    "DA01-discovery-0": (False, False, False, "Runs out of tokens after rejecting its own false B,C,T collinearity and tangency deductions, then speculates that T is the circumcenter from an equilateral case; no adopted proved general relation or use."),
    "DA01-discovery-1": (False, False, False, "Runs out of tokens. It explicitly falsifies its initial 1/AT=1/AB+1/AC conjecture using an inversion calculation but does not adopt and apply a replacement relation."),
    "DA08-discovery-0": (False, False, False, "Stops after adopting T on BC without a proof or numeric use. Exact construction for A=(1/5,17/10), B=(-1,0), C=(1,0) gives T_y=3281/5860, not zero."),
    "DA08-discovery-1": (False, False, False, "Runs out of tokens after adopting T on BC, recognizing Q as a tangent intersection, then retracting that recognition and restarting its calculation. No settled correct general relation or computed use; exact rational witness refutes T on BC."),
}


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--phase", choices=["discovery-baseline", "discovery-after-multiconfig-mapped", "discovery-after-dose-mapped"], required=True)
    args = p.parse_args()
    if args.phase == "discovery-baseline":
        decisions = BASE
    elif args.phase == "discovery-after-multiconfig-mapped":
        decisions = AFTER
    else:
        decisions = DOSE
        expected = [f"{c}-discovery-{i}" for c in ("H01", "DA15", "DA01", "DA08") for i in range(2)]
        missing = sorted(set(expected) - set(decisions))
        if missing:
            raise SystemExit(f"Manual decisions still needed: {missing}")
    rows = []
    for id, (claim, proof, use, reason) in decisions.items():
        source = ROOT / args.phase / f"{id}.json"
        raw = source.read_bytes()
        answer = json.loads(raw)
        rows.append(dict(id=id, source=str(source), source_sha256=hashlib.sha256(raw).hexdigest(),
                         configuration=id.split("-discovery")[0],
                         actual_train_configuration_overlap=id.startswith(("H01-", "DA15-")),
                         claim_true=claim, proof_valid=proof, useful_application=use,
                         complete=claim and proof and use,
                         truncated=answer["finish_reason"] == "length",
                         finish_reason=answer["finish_reason"], answer_tokens=len(answer["completion_ids"]),
                         reason=reason))
    summary = dict(n=len(rows), true_claims=sum(r["claim_true"] for r in rows),
                   valid_proofs=sum(r["proof_valid"] for r in rows),
                   useful_applications=sum(r["useful_application"] for r in rows),
                   complete=sum(r["complete"] for r in rows),
                   truncated=sum(r["truncated"] for r in rows),
                   complete_train_overlap=sum(r["complete"] and r["actual_train_configuration_overlap"] for r in rows),
                   complete_untrained_configuration=sum(r["complete"] and not r["actual_train_configuration_overlap"] for r in rows),
                   by_configuration={c:sum(r["complete"] for r in rows if r["configuration"] == c)
                                     for c in ("H01", "DA15", "DA01", "DA08")})
    (HERE / f"{args.phase}-grades.json").write_text(json.dumps(rows, ensure_ascii=False, indent=2) + "\n")
    (HERE / f"{args.phase}-summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(summary))


if __name__ == "__main__":
    main()
