"""Search-box expansion locks derived from mathematical domains."""

from geosolver.problem.domain_bounds import mathematical_bounds


def infer_bound_expansion_locks(spec, var_names):
    domains = mathematical_bounds(spec)
    return [
        (domains[name].lower is not None, domains[name].upper is not None) for name in var_names
    ]
