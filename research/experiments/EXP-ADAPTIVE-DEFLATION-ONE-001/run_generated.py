"""Generated D0, truth-isolated from the candidate callbacks."""

from __future__ import annotations

import hashlib
import json
import random
from dataclasses import dataclass
from pathlib import Path

import mpmath as mp

from candidate import Model, solve_adaptive, solve_fixed


with mp.workprec(512):
    I = mp.matrix([[1, 0], [0, 1]])
    ROT = mp.matrix([[mp.mpf(3)/5, -mp.mpf(4)/5], [mp.mpf(4)/5, mp.mpf(3)/5]])
    ROT2 = mp.matrix([[mp.mpf(5)/13, -mp.mpf(12)/13], [mp.mpf(12)/13, mp.mpf(5)/13]])
    SWAP = mp.matrix([[0, 1], [-1, 0]])


@dataclass
class Problem:
    mechanism: str
    root_scale: str
    a: str
    beta: str
    gamma: str
    q: mp.matrix
    r: mp.matrix
    offset: str
    opaque: bool = False

    def root(self):
        with mp.workprec(512):
            return mp.sqrt(2) * mp.mpf(self.root_scale)

    def canonical(self, y):
        root = self.root()
        d, v = y[0] - root, y[1]
        a, b, g = mp.mpf(self.a), mp.mpf(self.beta), mp.mpf(self.gamma)
        if self.mechanism == "quadratic":
            return mp.matrix([a*d*d + b*v, v + g*d*d])
        if self.mechanism == "cubic":
            return mp.matrix([a*d**3 + b*v, v + g*d**3])
        if self.mechanism == "manifold":
            return mp.matrix([d*d, d*v])
        if self.mechanism == "close_regular":
            sep = mp.mpf("1e-10")
            return mp.matrix([a*(d*d-sep*sep) + b*v, v + g*(d*d-sep*sep)])
        if self.mechanism == "inconsistent":
            return mp.matrix([a*d*d + mp.mpf("1e-18") + b*v, v + g*d*d])
        raise ValueError(self.mechanism)

    def canonical_j(self, y):
        root = self.root()
        d, v = y[0] - root, y[1]
        a, b, g = mp.mpf(self.a), mp.mpf(self.beta), mp.mpf(self.gamma)
        if self.mechanism in ("quadratic", "close_regular", "inconsistent"):
            return mp.matrix([[2*a*d, b], [2*g*d, 1]])
        if self.mechanism == "cubic":
            return mp.matrix([[3*a*d*d, b], [3*g*d*d, 1]])
        if self.mechanism == "manifold":
            return mp.matrix([[2*d, 0], [v, d]])
        raise ValueError(self.mechanism)

    def canonical_h(self, y, v, w):
        root = self.root()
        d, yy = y[0] - root, y[1]
        a, g = mp.mpf(self.a), mp.mpf(self.gamma)
        if self.mechanism in ("quadratic", "close_regular", "inconsistent"):
            return mp.matrix([2*a*v[0]*w[0], 2*g*v[0]*w[0]])
        if self.mechanism == "cubic":
            return mp.matrix([6*a*d*v[0]*w[0], 6*g*d*v[0]*w[0]])
        if self.mechanism == "manifold":
            return mp.matrix([2*v[0]*w[0], v[0]*w[1] + v[1]*w[0]])
        raise ValueError(self.mechanism)

    def model(self):
        def residual(x):
            return self.r * self.canonical(self.q * mp.matrix(x))
        def jacobian(x):
            y = self.q * mp.matrix(x)
            return self.r * self.canonical_j(y) * self.q
        def hessian(x, v, w):
            y = self.q * mp.matrix(x)
            return self.r * self.canonical_h(y, self.q*mp.matrix(v), self.q*mp.matrix(w))
        return Model(residual, None if self.opaque else jacobian,
                     None if self.opaque else hessian, residual)

    def start(self):
        with mp.workprec(512):
            if self.mechanism in ("close_regular", "inconsistent"):
                y = mp.matrix([self.root(), 0])
            else:
                y = mp.matrix([self.root() + mp.mpf(self.offset), mp.mpf(self.offset)/7])
            return self.q.T * y

    def truth_root(self):
        with mp.workprec(512):
            return self.q.T * mp.matrix([self.root(), 0])


def success(problem: Problem, result) -> bool:
    if problem.mechanism != "quadratic" or not result.proposal_only:
        return False
    with mp.workprec(512):
        endpoint = mp.matrix([mp.mpf(x) for x in result.endpoint])
        err = mp.sqrt(mp.fsum((endpoint[i]-problem.truth_root()[i])**2 for i in range(2)))
        return err <= mp.mpf("1e-14") * max(1, abs(problem.root()))


def make_cases():
    cases = []
    families = [
        ("separated", "1", "0", "0"),
        ("row_coupled", "3", "2", "0.25"),
        ("mixed_scale", "1e-7", "0.5", "2e-8"),
    ]
    reps = [("identity", I, I), ("orthogonal", ROT, ROT2), ("signed", SWAP, ROT), ("orthogonal_2", ROT2, SWAP)]
    for fam, a, b, g in families:
        for k in range(40):
            _, q, r = reps[k % len(reps)]
            scale = "1e12" if k % 2 else "1"
            cases.append((fam, Problem("quadratic", scale, a, b, g, q, r, "1e-8")))
    for mech in ("cubic", "manifold", "close_regular", "inconsistent"):
        for k in range(20):
            _, q, r = reps[k % len(reps)]
            cases.append((mech, Problem(mech, "1", "1", "0.25", "0.125", q, r, "1e-8")))
    for k in range(20):
        _, q, r = reps[k % len(reps)]
        cases.append(("opaque", Problem("quadratic", "1", "1", "0", "0", q, r, "1e-8", True)))
    return cases


def main():
    random.seed(0)
    cases = make_cases()
    rows = []
    for family, problem in cases:
        model, start = problem.model(), problem.start()
        low = solve_fixed(model, start, 64)
        high = solve_fixed(model, start, 256)
        cand = solve_adaptive(model, start)
        rows.append({
            "family": family,
            "eligible": problem.mechanism == "quadratic" and not problem.opaque,
            "low_success": success(problem, low),
            "high_success": success(problem, high),
            "candidate_success": success(problem, cand),
            "low_proposal": low.proposal_only,
            "high_proposal": high.proposal_only,
            "candidate_proposal": cand.proposal_only,
            "low_work": low.precision_work,
            "high_work": high.precision_work,
            "candidate_work": cand.precision_work,
            "candidate_rungs": cand.rungs,
            "candidate_reason": cand.reason,
        })

    positives = [r for r in rows if r["eligible"]]
    negatives = [r for r in rows if not r["eligible"]]
    by_family = {}
    for fam in sorted({r["family"] for r in rows}):
        rr = [r for r in rows if r["family"] == fam]
        by_family[fam] = {
            "n": len(rr),
            "low_success": sum(r["low_success"] for r in rr),
            "high_success": sum(r["high_success"] for r in rr),
            "candidate_success": sum(r["candidate_success"] for r in rr),
            "candidate_proposals": sum(r["candidate_proposal"] for r in rr),
        }
    aggregate = {
        "schema": "adaptive-deflation-one-d0/v1",
        "case_count": len(rows),
        "positive_count": len(positives),
        "negative_count": len(negatives),
        "fixed64_success": sum(r["low_success"] for r in positives),
        "fixed256_success": sum(r["high_success"] for r in positives),
        "adaptive_success": sum(r["candidate_success"] for r in positives),
        "adaptive_vs_fixed64_wins": sum(r["candidate_success"] and not r["low_success"] for r in positives),
        "adaptive_vs_fixed64_losses": sum(r["low_success"] and not r["candidate_success"] for r in positives),
        "adaptive_vs_fixed256_wins": sum(r["candidate_success"] and not r["high_success"] for r in positives),
        "adaptive_vs_fixed256_losses": sum(r["high_success"] and not r["candidate_success"] for r in positives),
        "negative_control_proposals": sum(r["candidate_proposal"] for r in negatives),
        "final_promotions_or_emissions": 0,
        "authority": "proposal-only; proof-bearing canonical verifier is not implemented or bypassed",
        "opaque_parity": all(not r["candidate_proposal"] and r["candidate_rungs"] == [] for r in rows if r["family"] == "opaque"),
        "mean_precision_work": {
            "fixed64": sum(r["low_work"] for r in positives)/len(positives),
            "fixed256": sum(r["high_work"] for r in positives)/len(positives),
            "adaptive": sum(r["candidate_work"] for r in positives)/len(positives),
        },
        "adaptive_vs_fixed256_work_ratio": (sum(r["candidate_work"] for r in positives) /
                                               sum(r["high_work"] for r in positives)),
        "rung_histogram": {str(bits): sum(bits in r["candidate_rungs"] for r in positives) for bits in (64,96,144,216,324)},
        "by_family": by_family,
        "mechanism_sha256": hashlib.sha256(Path(__file__).with_name("candidate.py").read_bytes()).hexdigest(),
    }
    out = Path(__file__).with_name("D0_AGGREGATE.json")
    out.write_text(json.dumps(aggregate, indent=2, sort_keys=True) + "\n")
    print(json.dumps(aggregate, indent=2, sort_keys=True))
    print("aggregate_sha256", hashlib.sha256(out.read_bytes()).hexdigest())


if __name__ == "__main__":
    main()
