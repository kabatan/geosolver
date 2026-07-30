"""Throwaway D0 prototype: event-driven precision for deflation-one refinement.

This is deliberately not a solver framework.  It accepts only numerical F/J/H
callbacks, never a case or family label, and fails closed whenever the local
deflation-one evidence is ambiguous.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Sequence

import mpmath as mp


Vector = Sequence[mp.mpf]


@dataclass
class Model:
    residual: Callable[[Vector], mp.matrix]
    jacobian: Callable[[Vector], mp.matrix] | None
    hessian_bilinear: Callable[[Vector, Vector, Vector], mp.matrix] | None
    replay_residual: Callable[[Vector], mp.matrix]


@dataclass
class Result:
    proposal_only: bool
    endpoint: list[str]
    reason: str
    callbacks: int
    precision_work: float
    rungs: list[int] = field(default_factory=list)
    projector_disagreement: list[float] = field(default_factory=list)
    endpoint_disagreement: list[float] = field(default_factory=list)
    replay_norm: float | None = None
    rung_evidence: list[dict] = field(default_factory=list)


@dataclass
class _Trajectory:
    ok: bool
    endpoint: mp.matrix
    right_projector: mp.matrix | None
    left_projector: mp.matrix | None
    callbacks: int
    reason: str
    residual0: mp.mpf
    residual1: mp.mpf
    b_ratio: mp.mpf | None
    rank_ratio: mp.mpf | None


def _col(values: Vector) -> mp.matrix:
    return mp.matrix([mp.mpf(v) for v in values])


def _norm(v: mp.matrix) -> mp.mpf:
    return mp.sqrt(mp.fsum(v[i] * v[i] for i in range(v.rows)))


def _finite_matrix(a: mp.matrix) -> bool:
    return all(mp.isfinite(a[i, j]) for i in range(a.rows) for j in range(a.cols))


def _right_singular_column(vt: mp.matrix, index: int) -> mp.matrix:
    return mp.matrix([vt[index, j] for j in range(vt.cols)])


def _projector(v: mp.matrix) -> mp.matrix:
    den = (v.T * v)[0]
    return (v * v.T) / den


def _matrix_frobenius(a: mp.matrix) -> mp.mpf:
    return mp.sqrt(mp.fsum(a[i, j] ** 2 for i in range(a.rows) for j in range(a.cols)))


def _rank_one_split(j: mp.matrix, bits: int):
    """Return a stable rank-one/corank-one split for a square 2x2 endpoint."""
    if j.rows != 2 or j.cols != 2 or not _finite_matrix(j):
        return None
    u, s, vt = mp.svd(j)
    if len(s) != 2 or s[0] <= 0:
        return None
    ratio = abs(s[1] / s[0])
    # A precision-linked ambiguity band, not a fixed singular-value cutoff.
    # The semantic near-singular window is fixed in normalized operator units;
    # arithmetic uncertainty can only widen it at a weak precision rung.
    singular_max = max(mp.mpf("1e-6"), 64 * mp.eps)
    if ratio >= singular_max:
        return None
    vr = _right_singular_column(vt, 0)
    vn = _right_singular_column(vt, 1)
    ur = mp.matrix([u[i, 0] for i in range(2)])
    un = mp.matrix([u[i, 1] for i in range(2)])
    return ur, un, vr, vn, abs(s[0]), ratio


def _trajectory(model: Model, start: Vector, bits: int, max_steps: int = 4) -> _Trajectory:
    callbacks = 0
    with mp.workprec(bits):
        x = _col(start)
        try:
            f0 = model.residual(x); callbacks += 1
            j0 = model.jacobian(x); callbacks += 1  # type: ignore[misc]
        except Exception:
            return _Trajectory(False, x, None, None, callbacks, "callback-error", mp.inf, mp.inf, None, None)
        if not _finite_matrix(f0) or not _finite_matrix(j0):
            return _Trajectory(False, x, None, None, callbacks, "nonfinite", mp.inf, mp.inf, None, None)
        residual0 = _norm(f0)
        split0 = _rank_one_split(j0, bits)
        if split0 is None:
            return _Trajectory(False, x, None, None, callbacks, "ambiguous-or-noncorank1", residual0, residual0, None, None)
        _, un0, _, vn0, _, rank_ratio0 = split0
        p0 = _projector(vn0)
        lp0 = _projector(un0)
        b_start = None
        last_right_projector = p0
        last_left_projector = lp0
        last_rank_ratio = rank_ratio0

        for _ in range(max_steps):
            f = model.residual(x); callbacks += 1
            j = model.jacobian(x); callbacks += 1  # type: ignore[misc]
            split = _rank_one_split(j, bits)
            if split is None:
                return _Trajectory(False, x, last_right_projector, last_left_projector, callbacks, "rank-drift", residual0, _norm(f), None, last_rank_ratio)
            ur, un, vr, vn, sr, last_rank_ratio = split
            last_right_projector = _projector(vn)
            last_left_projector = _projector(un)

            # Do not perturb an endpoint already below the arithmetic noise of
            # this rung merely to fill a fixed iteration count.
            if _norm(f) <= 128 * mp.eps * max(1, residual0):
                break

            # First (range) step from Lee--Li--Zhi's two-step decomposition.
            alpha = (ur.T * f)[0] / sr
            xr = x - vr * alpha
            jr = model.jacobian(xr); callbacks += 1  # type: ignore[misc]
            hvv = model.hessian_bilinear(xr, vn, vn); callbacks += 1  # type: ignore[misc]
            b = (un.T * hvv)[0]
            if not mp.isfinite(b) or abs(b) <= 64 * mp.eps * max(1, _norm(hvv)):
                return _Trajectory(False, x, last_right_projector, last_left_projector, callbacks, "projected-hessian-collapse", residual0, _norm(f), None, last_rank_ratio)
            if b_start is None:
                b_start = abs(b)
            rhs = -(un.T * jr * vn)[0]
            delta = rhs / b
            proposal = xr + vn * delta
            fp = model.residual(proposal); callbacks += 1
            if not _finite_matrix(fp) or _norm(fp) > _norm(f) * (1 + mp.mpf("1e-20")):
                return _Trajectory(False, x, last_right_projector, last_left_projector, callbacks, "no-residual-descent", residual0, _norm(f), None, last_rank_ratio)
            x = proposal

        ff = model.residual(x); callbacks += 1
        jf = model.jacobian(x); callbacks += 1  # type: ignore[misc]
        sf = _rank_one_split(jf, bits)
        if sf is None:
            return _Trajectory(False, x, last_right_projector, last_left_projector, callbacks, "final-rank-drift", residual0, _norm(ff), None, last_rank_ratio)
        _, unf, _, vnf, _, final_rank_ratio = sf
        hvvf = model.hessian_bilinear(x, vnf, vnf); callbacks += 1  # type: ignore[misc]
        b_final = abs((unf.T * hvvf)[0])
        ratio = b_final / b_start if b_start and b_start > 0 else mp.inf
        # Higher-depth roots make the projected quadratic operator collapse.
        if not mp.isfinite(ratio) or ratio < mp.mpf(1) / 16 or ratio > 16:
            return _Trajectory(False, x, _projector(vnf), _projector(unf), callbacks, "projected-order-drift", residual0, _norm(ff), ratio, final_rank_ratio)
        if _norm(ff) >= residual0:
            return _Trajectory(False, x, _projector(vnf), _projector(unf), callbacks, "no-net-progress", residual0, _norm(ff), ratio, final_rank_ratio)
        return _Trajectory(True, x, _projector(vnf), _projector(unf), callbacks, "ok", residual0, _norm(ff), ratio, final_rank_ratio)


def _replay_norm(model: Model, endpoint: Vector, bits: int = 384) -> mp.mpf:
    with mp.workprec(bits):
        return _norm(model.replay_residual(_col(endpoint)))


def _pack_endpoint(x: mp.matrix, digits: int = 120) -> list[str]:
    return [mp.nstr(x[i], digits) for i in range(x.rows)]


def solve_fixed(model: Model, start: Vector, bits: int) -> Result:
    """Fixed-precision control, including the same high-precision source replay."""
    if model.jacobian is None or model.hessian_bilinear is None:
        return Result(False, [str(v) for v in start], "opaque-fallback", 0, 0.0, [bits])
    try:
        tr = _trajectory(model, start, bits)
    except Exception as exc:
        return Result(False, [str(v) for v in start], f"callback-failed:{type(exc).__name__}", 0, 0.0, [bits])
    work = tr.callbacks * bits / 64
    if not tr.ok:
        return Result(False, _pack_endpoint(tr.endpoint), tr.reason, tr.callbacks, work, [bits])
    try:
        replay = _replay_norm(model, tr.endpoint)
    except Exception as exc:
        return Result(False, _pack_endpoint(tr.endpoint), f"replay-failed:{type(exc).__name__}", tr.callbacks, work, [bits])
    if replay > mp.mpf("1e-30"):
        return Result(False, _pack_endpoint(tr.endpoint), "canonical-replay-failed", tr.callbacks + 1, work + 6, [bits], replay_norm=float(replay))
    return Result(True, _pack_endpoint(tr.endpoint), "proposal-ready-not-authoritative", tr.callbacks + 1, work + 6, [bits], replay_norm=float(replay))


def solve_adaptive(model: Model, start: Vector, ladder=(64, 96, 144, 216, 324)) -> Result:
    """Escalate only on observed rank/projector/endpoint/replay uncertainty."""
    if model.jacobian is None or model.hessian_bilinear is None:
        return Result(False, [str(v) for v in start], "opaque-fallback", 0, 0.0, [])

    total_callbacks = 0
    precision_work = 0.0
    used: list[int] = []
    projector_gaps: list[float] = []
    endpoint_gaps: list[float] = []
    previous: _Trajectory | None = None
    latest: _Trajectory | None = None
    evidence: list[dict] = []

    for bits in ladder:
        try:
            tr = _trajectory(model, start, bits)
        except Exception as exc:
            evidence.append({"bits": bits, "reason": f"callback-failed:{type(exc).__name__}"})
            return Result(False, [str(v) for v in start], evidence[-1]["reason"], total_callbacks, precision_work, used,
                          projector_gaps, endpoint_gaps, rung_evidence=evidence)
        used.append(bits)
        total_callbacks += tr.callbacks
        precision_work += tr.callbacks * bits / 64
        latest = tr
        evidence.append({
            "bits": bits,
            "reason": tr.reason,
            "ok": tr.ok,
            "rank_ratio": float(tr.rank_ratio) if tr.rank_ratio is not None and mp.isfinite(tr.rank_ratio) else None,
            "b_ratio": float(tr.b_ratio) if tr.b_ratio is not None and mp.isfinite(tr.b_ratio) else None,
            "residual0": float(tr.residual0) if mp.isfinite(tr.residual0) else None,
            "residual1": float(tr.residual1) if mp.isfinite(tr.residual1) else None,
        })
        if total_callbacks > 256:
            return Result(False, _pack_endpoint(tr.endpoint), "proposal-callback-cap", total_callbacks, precision_work, used,
                          projector_gaps, endpoint_gaps, rung_evidence=evidence)
        if not tr.ok:
            # Equal labels are not mathematical agreement: run the ladder until
            # actual invariant operands resolve or the hard cap is exhausted.
            previous = tr
            continue

        try:
            replay = _replay_norm(model, tr.endpoint)
        except Exception as exc:
            return Result(False, _pack_endpoint(tr.endpoint), f"replay-failed:{type(exc).__name__}", total_callbacks,
                          precision_work, used, projector_gaps, endpoint_gaps, rung_evidence=evidence)
        total_callbacks += 1
        precision_work += 384 / 64
        if (previous is not None and previous.ok and previous.right_projector is not None and
                tr.right_projector is not None and previous.left_projector is not None and tr.left_projector is not None):
            # Comparison itself must run at the stronger rung; doing this in
            # the ambient default precision manufactured 2^-53 disagreement.
            with mp.workprec(bits):
                right_gap = _matrix_frobenius(tr.right_projector - previous.right_projector)
                left_gap = _matrix_frobenius(tr.left_projector - previous.left_projector)
                pgap = max(right_gap, left_gap)
                scale = max(1, _norm(tr.endpoint), _norm(previous.endpoint))
                egap = _norm(tr.endpoint - previous.endpoint) / scale
                # The tolerance is tied to the weaker rung's arithmetic, with
                # a semantic floor. Replay is evaluated independently.
                weak_bits = used[-2]
                proj_tol = max(mp.power(2, -weak_bits / 3), mp.mpf("1e-18"))
                endpoint_tol = max(mp.power(2, -weak_bits / 2), mp.mpf("1e-24"))
            projector_gaps.append(float(pgap))
            endpoint_gaps.append(float(egap))
            if pgap <= proj_tol and egap <= endpoint_tol and replay <= mp.mpf("1e-30"):
                return Result(True, _pack_endpoint(tr.endpoint), "proposal-ready-not-authoritative", total_callbacks,
                              precision_work, used, projector_gaps, endpoint_gaps, float(replay), evidence)
        previous = tr

    assert latest is not None
    replay = _replay_norm(model, latest.endpoint) if latest.ok else None
    return Result(False, _pack_endpoint(latest.endpoint), "precision-ladder-exhausted" if latest.ok else latest.reason,
                  total_callbacks, precision_work, used, projector_gaps, endpoint_gaps,
                  float(replay) if replay is not None else None, evidence)
