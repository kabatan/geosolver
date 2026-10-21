"""Homogeneous barycentrics for Kimberling X13--X16.

ETC trilinears are csc(A +/- pi/3) and sin(A +/- pi/3); converting
trilinears to barycentrics multiplies by a,b,c. Squared-side formulas
avoid inverse trig, division by a vanishing sine, and repeated side lengths.
"""

from mpmath import mp

from geosolver.errors import GeometryDomainError


def compute_special_triangle_center(A, B, C, n, point_cls):
    if n not in {13, 14, 15, 16}:
        return None
    a2 = (B.x - C.x) ** 2 + (B.y - C.y) ** 2
    b2 = (C.x - A.x) ** 2 + (C.y - A.y) ** 2
    c2 = (A.x - B.x) ** 2 + (A.y - B.y) ** 2
    scale2 = max(a2, b2, c2)
    cross = abs(mp.fdot((B.x - A.x, B.y - A.y), (C.y - A.y, A.x - C.x)))
    if scale2 == 0 or cross == 0:
        raise GeometryDomainError("triangle center requires non-collinear points")
    a2, b2, c2 = a2 / scale2, b2 / scale2, c2 / scale2
    area4 = 2 * cross / scale2
    sign = 1 if n in {13, 15} else -1
    radical = sign * mp.sqrt(3)
    qa = area4 + radical * (b2 + c2 - a2)
    qb = area4 + radical * (c2 + a2 - b2)
    qc = area4 + radical * (a2 + b2 - c2)
    weights = (qb * qc, qc * qa, qa * qb) if n in {13, 14} else (a2 * qa, b2 * qb, c2 * qc)
    total = mp.fsum(weights)
    if max(abs(qa), abs(qb), abs(qc)) <= 32 * mp.eps or abs(total) <= (
        32 * mp.eps * mp.fsum(abs(w) for w in weights)
    ):
        raise GeometryDomainError("triangle center has no resolved finite barycentrics")
    _, wb, wc = weights
    return point_cls(
        A.x + (wb * (B.x - A.x) + wc * (C.x - A.x)) / total,
        A.y + (wb * (B.y - A.y) + wc * (C.y - A.y)) / total,
    )
