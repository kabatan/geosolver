"""Checked exact consequences of polynomial zero equalities over real inputs."""


def _bounded_rows(equations, variables):
    import sympy as sp

    return (
        1 <= len(equations) <= 32
        and len(variables) <= 12
        and all(
            p.gens == tuple(variables)
            and (p.domain.is_QQ or p.domain.is_AlgebraicField)
            and p.total_degree() <= 8
            and len(p.terms()) <= 60
            for p in equations
        )
        and all(
            max(abs(int(atom.p)).bit_length(), int(atom.q).bit_length()) <= 4096
            for p in equations
            for coefficient in p.coeffs()
            for atom in coefficient.atoms(sp.Rational)
        )
    )


def squarefree_zero_consequences(equations, variables):
    """Return squarefree equations with exact factorization receipts.

    F=c*product(G_i**m_i), c!=0, m_i>0, has precisely the same complex
    zero set as product(G_i). Original rows remain with the caller.
    """
    import sympy as sp

    if not _bounded_rows(equations, variables):
        return ()
    consequences = []
    for original in equations:
        if original.total_degree() < 2:
            continue
        coefficient, factors = original.sqf_list()
        if not any(power > 1 for _, power in factors):
            continue
        reconstructed = coefficient * sp.prod(
            factor.as_expr() ** power for factor, power in factors
        )
        if not sp.Poly(
            original.as_expr() - reconstructed, *variables, domain=original.domain
        ).is_zero:
            raise ValueError("unverified squarefree factorization")
        squarefree = sp.Poly(
            sp.prod(factor.as_expr() for factor, _ in factors), *variables, domain=original.domain
        )
        consequences.append((squarefree, coefficient, tuple(factors)))
    return tuple(consequences)


def quadratic_sos_zero_consequences(equations, variables):
    """Return affine zero equations from exact rational semidefinite quadratics.

    Exact symmetric elimination proves sign*F=sum(d_i*L_i**2), d_i>0.
    Every real zero of F must therefore make every affine L_i zero. Negative
    or unknown pivots and nonzero rows with zero diagonal decline this subset.
    """
    import sympy as sp

    if not _bounded_rows(equations, variables):
        return ()
    consequences = []
    coordinates = (*variables, sp.S.One)
    size = len(coordinates)
    for original in equations:
        if not original.domain.is_QQ or original.total_degree() != 2:
            continue
        matrix = sp.zeros(size)
        for i, variable in enumerate(variables):
            matrix[i, i] = original.coeff_monomial(variable**2)
            matrix[i, -1] = matrix[-1, i] = original.coeff_monomial(variable) / 2
            for j in range(i):
                matrix[i, j] = matrix[j, i] = original.coeff_monomial(variable * variables[j]) / 2
        matrix[-1, -1] = original.coeff_monomial(1)
        certificate = None
        for sign in (1, -1):
            remainder = sign * matrix
            active = list(range(size))
            terms = []
            while active:
                if any(remainder[i, i] < 0 for i in active):
                    break
                pivot_index = next((i for i in active if remainder[i, i] > 0), None)
                if pivot_index is None:
                    if all(remainder[i, j] == 0 for i in active for j in active):
                        certificate = (sign, tuple(terms))
                    break
                pivot = remainder[pivot_index, pivot_index]
                affine = sum(remainder[pivot_index, j] * coordinates[j] for j in active) / pivot
                terms.append((pivot, sp.Poly(affine, *variables, domain=sp.QQ)))
                remaining = [i for i in active if i != pivot_index]
                for i in remaining:
                    for j in remaining:
                        # Every update reads the unchanged pivot row/column.
                        remainder[i, j] -= (
                            remainder[i, pivot_index] * remainder[pivot_index, j] / pivot
                        )
                active = remaining
                if not active:
                    certificate = (sign, tuple(terms))
            if certificate is not None:
                break
        if certificate is None:
            continue
        sign, terms = certificate
        difference = sign * original.as_expr() - sum(d * row.as_expr() ** 2 for d, row in terms)
        if not sp.Poly(sp.expand(difference), *variables, domain=sp.QQ).is_zero:
            raise ValueError("unverified rational SOS certificate")
        consequences.append((original, sign, terms))
    return tuple(consequences)
