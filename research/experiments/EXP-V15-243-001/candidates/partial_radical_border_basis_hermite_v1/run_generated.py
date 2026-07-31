#!/usr/bin/env python3
"""Run the frozen generated panel and emit aggregate D0 evidence."""

from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path

from candidate import NotCertified, certify, verify_certificate
from generated_cases import metamorphics, negatives, positives


def main() -> int:
    failures = []
    positive_pass = 0
    negative_pass = 0
    metamorphic_pass = 0
    mutation_pass = 0
    certificates = {}
    for name, problem in positives().items():
        try:
            certificate = certify(problem)
            if not (
                certificate["authority"] is True
                and certificate["ideal_inclusion"] == "I_SUBSET_J"
                and certificate["variety_inclusion"] == "V_J_SUBSET_V_I"
                and certificate["target_set_completeness_claim"] is False
                and certificate["positive_tarski_count"] > 0
            ):
                raise AssertionError("positive authority contract")
            certificates[name] = (problem, certificate)
            positive_pass += 1
        except Exception as error:
            failures.append(f"positive:{name}:{type(error).__name__}:{error}")
    for name, problem in negatives().items():
        try:
            certify(problem)
            failures.append(f"negative:{name}:false-authority")
        except Exception:
            negative_pass += 1
    for name, problem in metamorphics().items():
        try:
            certificate = certify(problem)
            if certificate["positive_tarski_count"] <= 0:
                raise AssertionError("metamorphic count")
            metamorphic_pass += 1
        except Exception as error:
            failures.append(f"metamorphic:{name}:{type(error).__name__}:{error}")

    if certificates:
        problem, certificate = next(iter(certificates.values()))
        mutations = []
        bad = deepcopy(certificate)
        bad["hplus"][0][0] = str(int(bad["hplus"][0][0]) + 1)
        mutations.append(("forged-moment", bad))
        bad = deepcopy(certificate)
        bad["multiplication_matrices"][0][0][0] = "17"
        mutations.append(("forged-multiplication-matrix", bad))
        bad = deepcopy(certificate)
        bad["positive_tarski_count"] += 1
        mutations.append(("forged-tarski-count", bad))
        bad = deepcopy(certificate)
        bad["variety_inclusion"] = "V_I_SUBSET_V_J"
        mutations.append(("reversed-variety-inclusion", bad))
        for name, artifact in mutations:
            try:
                verify_certificate(problem, artifact)
                failures.append(f"mutation:{name}:accepted")
            except Exception:
                mutation_pass += 1

    aggregate = {
        "schema_version": "geotarget.partial-radical-border-basis-hermite-generated-result/v1",
        "positive_pass": positive_pass,
        "positive_total": len(positives()),
        "negative_pass": negative_pass,
        "negative_total": len(negatives()),
        "metamorphic_pass": metamorphic_pass,
        "metamorphic_total": len(metamorphics()),
        "certificate_mutation_pass": mutation_pass,
        "certificate_mutation_total": 4,
        "false_authority_count": sum("false-authority" in item or item.endswith(":accepted") for item in failures),
        "failures": failures,
        "gate_pass": not failures,
        "truth_used": False,
        "formal_scorer_used": False,
        "global_completeness_claim": False,
    }
    output = Path(__file__).with_name("GENERATED_RESULT.json")
    output.write_text(json.dumps(aggregate, indent=2, sort_keys=True) + "\n")
    print(json.dumps(aggregate, sort_keys=True))
    return 0 if aggregate["gate_pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
