"""Load optional SciPy search machinery only when an algorithm uses it.

The delegates preserve SciPy implementations, call arguments, and random streams.
NOMAD-only and direct-evaluation solves need not initialize scipy.stats/optimize.
"""


def brentq(*args, **kwargs):
    from scipy.optimize import brentq as implementation

    return implementation(*args, **kwargs)


def least_squares(*args, **kwargs):
    from scipy.optimize import least_squares as implementation

    return implementation(*args, **kwargs)


def minimize(*args, **kwargs):
    from scipy.optimize import minimize as implementation

    return implementation(*args, **kwargs)


def minimize_scalar(*args, **kwargs):
    from scipy.optimize import minimize_scalar as implementation

    return implementation(*args, **kwargs)
