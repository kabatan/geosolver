"""Exact disjoint boxes bind accepted numerical witnesses to algebraic roots."""

from fractions import Fraction


def certified_branch_boxes(solutions, points):
    """Enclose every exact configuration in a pairwise disjoint rational box.

    CRootOf intervals and rational interval arithmetic prove containment. No
    approximate sign test is used; unsupported algebraic expressions decline.
    This runs inside the existing optional symbolic worker deadline.
    """
    import sympy as sp

    centers = [tuple(sp.Rational(value) for value in point) for point in points]
    if not centers:
        return []
    radius = max(sp.S.One, *(abs(value) for point in centers for value in point)) / 8
    for index, first in enumerate(centers):
        for second in centers[:index]:
            separation = max(abs(a - b) for a, b in zip(first, second, strict=True))
            if separation == 0:
                return None
            radius = min(radius, separation / 8)
    root_width = min(radius / 65536, sp.Rational(1, 2**640))
    interval = exact_algebraic_interval_evaluator(root_width)

    boxes = []
    for solution, center in zip(solutions, centers, strict=True):
        box = []
        for exact, value in zip(solution, center, strict=True):
            lower, upper = interval(exact)
            left, right = value - radius, value + radius
            if not left < lower <= upper < right:
                return None
            box.append((str(left), str(right)))
        boxes.append(box)
    return boxes


def _mpf_fraction(value):
    """Read the stored binary number exactly, without a precision context."""
    sign, mantissa, exponent, bits = map(int, value._mpf_)
    if bits < 0:
        raise ValueError("nonfinite numerical enclosure")
    number = Fraction(-mantissa if sign else mantissa)
    return number * (2**exponent) if exponent >= 0 else number / (2**-exponent)


def accepted_within_origin_box(candidate, proposal):
    """The entire accepted coordinate uncertainty must fit its own root box."""
    box = proposal.originating_branch_box
    if (
        not box
        or len(box) != len(candidate.x_hp)
        or len(box) != len(candidate.coordinate_uncertainty)
    ):
        return False
    try:
        for coordinate, uncertainty, (left, right) in zip(
            candidate.x_hp, candidate.coordinate_uncertainty, box, strict=True
        ):
            value, error = _mpf_fraction(coordinate), _mpf_fraction(uncertainty)
            if error < 0 or not Fraction(left) <= value - error <= value + error <= Fraction(right):
                return False
    except (AttributeError, TypeError, ValueError, OverflowError):
        return False
    return True


def exact_algebraic_interval_evaluator(root_width):
    """Return a bounded exact rational interval evaluator for real algebraic values."""
    import sympy as sp

    cache = {}

    def multiply(first, second):
        products = [a * b for a in first for b in second]
        return min(products), max(products)

    def inverse(value):
        lower, upper = value
        if lower <= 0 <= upper:
            raise ValueError("interval denominator can vanish")
        return 1 / upper, 1 / lower

    def integer_power(value, exponent):
        if exponent < 0:
            return integer_power(inverse(value), -exponent)
        result = (sp.S.One, sp.S.One)
        for _ in range(exponent):
            result = multiply(result, value)
        return result

    def root_bound(value, degree, upper):
        if value < 0:
            raise ValueError("nonpositive-domain algebraic root interval")
        denominator = 2**640
        scaled = (int(value.p) * denominator**degree) // int(value.q)
        integer, _ = sp.integer_nthroot(scaled, degree)
        exact = integer**degree * int(value.q) == int(value.p) * denominator**degree
        return sp.Rational(integer + int(upper and not exact), denominator)

    def interval(expression):
        if expression in cache:
            return cache[expression]
        if expression.is_Rational:
            result = (expression, expression)
        elif isinstance(expression, sp.CRootOf) and expression.is_real is True:
            root_interval = expression._get_interval().refine_size(root_width)
            result = (sp.Rational(root_interval.a), sp.Rational(root_interval.b))
        elif isinstance(expression, sp.AlgebraicNumber):
            result = interval(expression.as_expr())
        elif expression.is_Add:
            values = [interval(term) for term in expression.args]
            result = (sum(value[0] for value in values), sum(value[1] for value in values))
        elif expression.is_Mul:
            result = (sp.S.One, sp.S.One)
            for factor in expression.args:
                result = multiply(result, interval(factor))
        elif expression.is_Pow and expression.exp.is_Rational:
            exponent = expression.exp
            if abs(exponent.p) > 16 or exponent.q > 8:
                raise ValueError("unsupported algebraic interval exponent")
            base = interval(expression.base)
            if exponent.q == 1:
                result = integer_power(base, int(exponent))
            else:
                if base[0] < 0:
                    raise ValueError("unproved real radical interval")
                result = (
                    root_bound(base[0], int(exponent.q), False),
                    root_bound(base[1], int(exponent.q), True),
                )
                result = integer_power(result, int(exponent.p))
        else:
            raise ValueError("unsupported exact algebraic coordinate interval")
        cache[expression] = result
        return result

    return interval
