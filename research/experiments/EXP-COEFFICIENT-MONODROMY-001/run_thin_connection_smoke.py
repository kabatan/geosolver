"""Truth-blind generated smoke for the pinned thin real-source connection."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import Counter
from fractions import Fraction
from pathlib import Path

import sympy as sp

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import thin_real_connection as connection

TOTAL_WORK = 64_000
FAMILIES = ("symmetric_quadratic", "affine_cubic", "separated_quartic")


def _document(
    family: str, replicate: int
) -> tuple[dict[str, object], tuple[Fraction, ...]]:
    x = sp.Symbol("x")
    shift = Fraction(replicate - 5, 7)
    if family == "symmetric_quadratic":
        roots = (shift - 2, shift + 2)
    elif family == "affine_cubic":
        roots = (shift - 2, shift + Fraction(1, 2), shift + 3)
    elif family == "separated_quartic":
        roots = tuple(shift + offset for offset in (-3, -1, 2, 4))
    else:
        raise ValueError(family)
    expression = sp.prod(
        x - sp.Rational(root.numerator, root.denominator) for root in roots
    )
    document = {
        "id": f"generated-{family}-{replicate}",
        "task": "solve",
        "variables": {"names": ["x"]},
        "construction": [],
        "constraints": [{"def": sp.sstr(sp.expand(expression)), "value": 0}],
        "guards": [],
        "answer": "x",
        "post_process": "",
    }
    return document, roots


def _digest(document: object) -> str:
    payload = json.dumps(document, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(payload).hexdigest()


def _replay(roots: tuple[Fraction, ...]):
    def replay(point: tuple[float, ...]) -> str | None:
        matches = [root for root in roots if abs(float(root) - point[0]) <= 2.0e-6]
        if len(matches) != 1:
            return None
        root = matches[0]
        return f"Q:{root.numerator}/{root.denominator}"

    return replay


def run(root: Path) -> dict[str, object]:
    aggregate: Counter[str] = Counter()
    by_family: dict[str, Counter[str]] = {name: Counter() for name in FAMILIES}
    for family in FAMILIES:
        for replicate in range(10):
            document, roots = _document(family, replicate)
            baseline_descriptor = _replay(roots)((float(roots[0]),))
            assert baseline_descriptor is not None
            baseline_payload = (baseline_descriptor + "\n").encode()
            result = connection.connect(
                document,
                source_sha256=_digest(document),
                accepted_source_point=(float(roots[0]),),
                baseline_payload=baseline_payload,
                baseline_descriptors=(baseline_descriptor,),
                total_work=TOTAL_WORK,
                canonical_replay=_replay(roots),
                common_control_root=root,
            )
            expected = {f"Q:{item.numerator}/{item.denominator}" for item in roots}
            observed = set(result.descriptors)
            gained = observed - {baseline_descriptor}
            false = observed - expected
            for counter in (aggregate, by_family[family]):
                counter["cases"] += 1
                counter["eligible"] += int(result.eligible)
                counter["activation_cases"] += int(bool(gained))
                counter["descriptor_gains"] += len(gained)
                counter["descriptor_losses"] += int(baseline_descriptor not in observed)
                counter["false_or_extra"] += len(false)
                counter["payload_mismatch"] += int(
                    result.baseline_payload != baseline_payload
                )
                counter["baseline_floor_mismatch"] += int(
                    result.baseline_work != 48_000
                )
                counter["replay_rejections"] += result.canonical_replay_rejections
                counter["loops_completed"] += result.loops_completed

    negatives = []
    document, roots = _document("symmetric_quadratic", 0)
    negative_documents = {
        "multivariate": {**document, "variables": {"names": ["x", "y"]}},
        "nonsquarefree": {
            **document,
            "constraints": [{"def": "(x - 1)**2", "value": 0}],
        },
        "unsupported": {**document, "constraints": [{"def": "sin(x)", "value": 0}]},
    }
    for label, source in negative_documents.items():
        result = connection.connect(
            source,
            source_sha256=_digest(source),
            accepted_source_point=(float(roots[0]),),
            baseline_payload=b"opaque-baseline\x00",
            baseline_descriptors=("opaque-baseline",),
            total_work=TOTAL_WORK,
            canonical_replay=_replay(roots),
            common_control_root=root,
        )
        negatives.append(
            {"label": label, "rejected": not result.eligible, "reason": result.reason}
        )

    improved = sum(by_family[name]["descriptor_gains"] > 0 for name in FAMILIES)
    result = {
        "schema": "geotarget.exp-coefficient-monodromy-thin-connection-smoke/v1",
        "formal_run": False,
        "truth_scorer_or_case_outcome_read": False,
        "source_only_generated": True,
        "entrypoint": "thin_real_connection.py:connect",
        "policy": {
            "baseline_fraction": 0.75,
            "route": "pinned existing compiler -> direct QQ univariate square-free -> proposals -> caller canonical replay",
            "proposal_authority": False,
        },
        "aggregate": dict(aggregate),
        "by_family": {name: dict(row) for name, row in by_family.items()},
        "negative_gates": negatives,
        "gate": {
            "passed": aggregate["descriptor_losses"] == 0
            and aggregate["false_or_extra"] == 0
            and aggregate["payload_mismatch"] == 0
            and aggregate["baseline_floor_mismatch"] == 0
            and improved >= 2
            and all(item["rejected"] for item in negatives),
            "improved_families": improved,
        },
    }
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--common-control-root", type=Path, required=True)
    arguments = parser.parse_args()
    result = run(arguments.common_control_root.resolve())
    print(json.dumps(result, indent=2, sort_keys=True))
    raise SystemExit(0 if result["gate"]["passed"] else 1)


if __name__ == "__main__":
    main()
