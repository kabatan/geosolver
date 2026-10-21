"""Necessary algebraic equations for bounded linear unsigned-angle relations."""


def necessary_angle_equation(expression):
    """Apply cosine to one angle, or a sum/difference of two angles.

    For A=acos(u), B=acos(v), A+s*B=t with s in {-1,1} implies
    u=v*cos(t)+s*sqrt(1-v*v)*sin(t). The principal-angle sine is nonnegative.
    Only closed exact algebraic sin(t),cos(t) are admitted. The implication
    may add extraneous roots; every original angle/domain remains mandatory.
    """
    import sympy as sp

    angles = sorted(expression.atoms(sp.acos), key=sp.default_sort_key)
    if not angles:
        return expression
    if len(angles) > 2 or any(angle.args[0].has(sp.acos) for angle in angles):
        raise ValueError("unsupported nested or multiple angle relation")
    symbols = [sp.Dummy(f"angle_{i}") for i in range(len(angles))]
    try:
        lifted = sp.Poly(expression.xreplace(dict(zip(angles, symbols, strict=True))), *symbols)
    except sp.PolynomialError:
        raise ValueError("unsupported nonlinear angle relation") from None
    if lifted.total_degree() != 1:
        raise ValueError("unsupported nonlinear angle relation")
    coefficients = [lifted.coeff_monomial(symbol) for symbol in symbols]
    constant = lifted.coeff_monomial(1)
    if any(value.free_symbols or value.is_real is not True for value in (*coefficients, constant)):
        raise ValueError("angle coefficients must be closed and real")
    if coefficients[0].is_zero is not False:
        raise ValueError("unproved nonzero angle coefficient")
    theta = sp.cancel(-constant / coefficients[0])
    cosine = sp.cos(theta)
    if cosine.is_algebraic is not True or cosine.is_real is not True:
        raise ValueError("unsupported exact angle constant")
    first = angles[0].args[0]
    if len(angles) == 1:
        return first - cosine
    ratio = sp.cancel(coefficients[1] / coefficients[0])
    if ratio not in (-1, 1):
        raise ValueError("unsupported angle coefficient ratio")
    sine = sp.sin(theta)
    if sine.is_algebraic is not True or sine.is_real is not True:
        raise ValueError("unsupported exact angle constant")
    second = angles[1].args[0]
    return first - cosine * second - ratio * sine * sp.sqrt(1 - second * second)
