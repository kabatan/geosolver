"""Freeze the manual audit of all post-v0 English teacher searches."""

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = Path("qwen/.runtime/qwen35_diverse_sft_20260924")
ARMS = [
    "material-revision-en-thinking-32k",
    "material-fresh-thinking-en-32k",
    "material-clean-en-32k",
    "material-h07-final-en-32k",
    "material-targeted-en-32k",
    "material-da18-clean-en-32k",
    "material-db06-clean-en-32k",
    "material-db06-final-en-32k",
    "material-db06-compact-en-32k",
]

ACCEPT = {
    "diverse-en-clean-H01-v0-0": "Self-contained coordinate derivation of AP=AM-BC^2/(4AM), followed by exact 32/5 application; no false-start text.",
    "diverse-en-final-H07-v0-0": "The contiguous proof-and-application passage derives O,M,N collinearity, OM*ON=OA^2, reflection E of M, the P,Q line intersections, and area 9. The preceding summary falsely states a different PQ formula and is excluded.",
    "diverse-en-clean-DA18-v0-0": "Defines alpha, proves FD*FE=BF^2 by two sine rules and angle DFE=120, then derives perimeter 32.",
}

REASONS = {
    "diverse-en-revision-H01-v0-0": "Correct later coordinate calculation, but visible answer contains incorrect trial algebra before it.",
    "diverse-en-fresh-thinking-H07-v0-0": "Correct-looking relations and value, but pivotal P,Q coordinate derivation refers to hidden thought rather than showing it visibly.",
    "diverse-en-clean-H07-v0-0": "Complete geometry but false displayed arithmetic x_M^2=7 from OM^2=10 and h_M^2=9.",
    "diverse-en-clean-H13-v0-0": "Incorrect tangency substitution for u, then an incorrect circumcenter and final value.",
    "diverse-en-clean-DA04-v0-0": "After correcting a false power claim, the decisive relation is still asserted without a proof.",
    "diverse-en-targeted-DB06-v0-0": "Promising midpoint argument but Y step is omitted and the vector-square identity has an incorrect coefficient.",
    "diverse-en-clean-DB06-v0-0": "Corrected Y ratio occurs only after an incorrect visible attempt; vector identity is not fully established.",
    "diverse-en-final-DB06-v0-0": "Complete midpoint derivation, but vector expansion contains repeated false coefficients and contradictory claims.",
    "diverse-en-compact-DB06-v0-0": "Midpoint derivation survives, but compact vector expansion has a wrong sign for c dot d and a false condition classification.",
}


def main():
    entries = []
    for arm in ARMS:
        for path in sorted((ROOT / arm).glob("diverse-*.json")):
            obj = json.loads(path.read_text())
            ident = obj["id"]
            accepted = ident in ACCEPT
            final = obj["final_text"]
            if accepted:
                start = final.index("### 2. Proof") if ident == "diverse-en-final-H07-v0-0" else 0
                end = len(final.removesuffix("<|im_end|>"))
                span = [start, end]
                reason = ACCEPT[ident]
            else:
                span = None
                reason = REASONS.get(ident, "No audited complete and self-contained visible relation, decisive proof, and numerical application; source answer retained for review.")
            entries.append({"id": ident, "config": obj["source_id"],
                            "source": str(path.resolve()),
                            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                            "status": "accept" if accepted else "reject",
                            "reason": reason, "finish": obj["finish_reason"],
                            "completion_tokens": len(obj["completion_ids"]),
                            "visible_span": span})
    assert len(entries) == 34, len(entries)
    assert sum(x["status"] == "accept" for x in entries) == len(ACCEPT)
    output = HERE / "candidate-audit-additional.json"
    output.write_text(json.dumps({"rubric": "RUBRIC-english.md", "entries": entries},
                                 ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({"searched": len(entries), "accepted": len(ACCEPT),
                      "output_sha256": hashlib.sha256(output.read_bytes()).hexdigest()}))


if __name__ == "__main__":
    main()
