"""Bounded symbolic requests, executed in the solve-owned symbolic worker."""

from dataclasses import asdict, replace

from mpmath import mp


def encode_identification(result):
    data = asdict(result)
    for field in ("verification_residual", "numeric_fallback_value"):
        if data[field] is not None:
            data[field] = tuple(map(int, data[field]._mpf_))
    if result.descriptor is not None:
        data["descriptor"] = result.descriptor.model_dump(mode="json")
    return data


def decode_identification(data):
    from pydantic import TypeAdapter

    from geosolver.engine.standard.contracts.pipeline_result import ExactIdentificationResult
    from geosolver.problem.models import ExactAnswer

    data = dict(data)
    for field in ("verification_residual", "numeric_fallback_value"):
        if data[field] is not None:
            data[field] = mp.make_mpf(tuple(data[field]))
    if data.get("minimal_polynomial") is not None:
        data["minimal_polynomial"] = tuple(data["minimal_polynomial"])
    if data.get("descriptor") is not None:
        data["descriptor"] = TypeAdapter(ExactAnswer).validate_python(data["descriptor"])
    return ExactIdentificationResult(**data)


def dispatch(operation, payload):
    if operation == "refinement_jacobian":
        from geosolver.engine.standard.refinement.analytic_jacobian import compile_jacobian

        return compile_jacobian(payload)
    if operation == "constant_geometry":
        from geosolver.engine.standard.exact_assembly.constant_geometry import (
            constant_geometry_expression,
        )

        return constant_geometry_expression(payload)
    if operation == "algebraic_branches":
        from geosolver.engine.standard.search.algebraic_branches import discover_polynomial_branches

        return discover_polynomial_branches(payload)
    if operation == "zero_signature":
        import sympy as sp

        from geosolver.problem.scalar_geometry import ScalarGeometry

        source, constructions = payload
        geometry = ScalarGeometry(dict(constructions), allow_opaque=True)
        try:
            expression = geometry.scalar(geometry.parse(source))
            if sp.count_ops(expression) > 300:
                return None
            # Nonzero line denominators are separately domain-checked. Abs has
            # the same zero set as its argument. Never strip additive terms.
            numerator = sp.together(expression).as_numer_denom()[0]
            if isinstance(numerator, sp.Abs):
                numerator = numerator.args[0]
            variables = sorted(numerator.free_symbols, key=str)
            if not variables:
                return "0" if numerator == 0 else None
            poly = sp.Poly(numerator, *variables)
            monic = poly.monic()
            return str(
                sp.Poly.from_dict(
                    {powers: sp.simplify(coefficient) for powers, coefficient in monic.terms()},
                    monic.gens,
                ).as_expr()
            )
        except (ValueError, TypeError, KeyError, sp.PolynomialError):
            return None
    if operation == "scalar_identity":
        import sympy as sp

        expression = sp.sympify(payload)
        if sp.count_ops(expression) > 300:
            return False
        return sp.trigsimp(sp.expand(expression)) == 0
    if operation == "normalize":
        from geosolver.engine.standard.evaluation.exact_constants import (
            exact_constant,
            normalized_difference,
        )

        result = []
        for left, right in payload:
            text = normalized_difference(left, right)
            constant = exact_constant(text)
            result.append((text, None if constant is None else (0 if constant == 0 else 1)))
        return result
    if operation != "identify":
        raise ValueError(f"unknown symbolic operation: {operation}")
    import sympy as sp

    from geosolver.engine.standard.contracts.pipeline_result import ExactIdentificationResult
    from geosolver.engine.standard.evaluation.exact_constants import exact_constant
    from geosolver.engine.standard.exact_assembly.identify_answer import _identify_answer_proposal
    from geosolver.exact.descriptors import describe_exact

    precision = int(payload["precision"])
    with mp.workdps(precision + 50):
        value = mp.make_mpf(tuple(payload["value"]))
        expression = (
            exact_constant(payload["closed_source"]) if payload.get("closed_source") else None
        )
        if expression is not None:
            try:
                descriptor = describe_exact(expression)
                result = ExactIdentificationResult(
                    "identified",
                    "closed_scalar_expression",
                    precision,
                    None,
                    None,
                    str(expression),
                    mp.mpf(0),
                    None,
                    descriptor,
                    "exact_expression",
                )
                return encode_identification(result)
            except (ValueError, NotImplementedError):
                # An exact expression outside algebraic/affine-pi is not rounded
                # into a simpler supported value by numerical reconstruction.
                return encode_identification(
                    ExactIdentificationResult(
                        "not_identified",
                        "unsupported_exact_expression",
                        precision,
                        None,
                        None,
                        None,
                        None,
                        value,
                    )
                )
        uncertainty = (
            mp.make_mpf(tuple(payload["uncertainty"]))
            if payload.get("uncertainty") is not None
            else max(1, abs(value)) * mp.power(10, -(precision - 20))
        )
        discovery_precision = precision
        if uncertainty > 0 and mp.isfinite(uncertainty):
            digits = int(mp.floor(-mp.log10(uncertainty / max(1, abs(value)))))
            discovery_precision = min(precision, digits + 10)
        if not mp.isfinite(uncertainty) or uncertainty < 0 or discovery_precision < 30:
            return encode_identification(
                ExactIdentificationResult(
                    "not_identified",
                    "insufficient_accuracy",
                    precision,
                    None,
                    None,
                    None,
                    None,
                    value,
                )
            )
        # Zero has no useful relative digits. A nonzero cancellation remainder
        # inside the independently confirmed absolute error interval must not
        # be sent to a power-of-ten/PSLQ reconstruction as a tiny nonzero root.
        # This uses the same final absolute-error test as other proposals.
        if abs(value) <= uncertainty:
            return encode_identification(
                ExactIdentificationResult(
                    "identified",
                    "zero_within_confirmed_error",
                    precision,
                    (1, 0),
                    1,
                    "0",
                    abs(value),
                    None,
                    describe_exact(sp.Integer(0)),
                )
            )
        # Every caller has independently verified this candidate's geometry.
        # Recheck the actual exact value at the new precision; overlapping
        # decimal approximations alone are never a cache key or a proof.
        matches = {}
        for encoded in payload.get("reusable_results", ()):
            prior = decode_identification(encoded)
            if prior.descriptor is None or prior.selected_exact_value is None:
                continue
            expression = sp.sympify(prior.selected_exact_value)
            root = mp.mpf(str(sp.N(expression, precision + 50)))
            root_error = abs(root) * mp.power(10, -(precision + 40))
            distance = abs(root - value)
            if distance <= uncertainty + root_error:
                matches[prior.descriptor.canonical_key()] = prior, distance
        if len(matches) == 1:
            prior, distance = next(iter(matches.values()))
            if discovery_precision >= (prior.discovery_precision_dps or prior.input_precision_dps):
                return encode_identification(
                    replace(
                        prior,
                        input_precision_dps=precision,
                        identification_method="verified_descriptor_reuse",
                        verification_residual=distance,
                        discovery_precision_dps=discovery_precision,
                    )
                )
        proposal = None
        # Geometry lowering supplies only a proposal. The original final
        # checks have run, and this path uses the same confirmed error bound.
        if payload.get("geometry_hint"):
            try:
                expression = sp.sympify(payload["geometry_hint"])
                root = mp.mpf(str(sp.N(expression, precision + 50)))
                root_error = abs(root) * mp.power(10, -(precision + 40))
                distance = abs(root - value)
                if mp.isfinite(root) and distance <= uncertainty + root_error:
                    descriptor = describe_exact(expression)
                    return encode_identification(
                        ExactIdentificationResult(
                            exact_status="identified",
                            identification_method="verified_constant_geometry",
                            input_precision_dps=precision,
                            minimal_polynomial=None,
                            polynomial_degree=None,
                            selected_exact_value=str(expression),
                            verification_residual=distance,
                            numeric_fallback_value=None,
                            descriptor=descriptor,
                            discovery_precision_dps=discovery_precision,
                        )
                    )
            except (
                ValueError,
                TypeError,
                ArithmeticError,
                NotImplementedError,
                sp.polys.polyerrors.BasePolynomialError,
            ):
                # A valid numeric hint can still lack a supported exact
                # descriptor. Optional geometry proposals must not prevent the
                # ordinary numerical reconstruction below from being attempted.
                pass
        if payload.get("prefer_affine_pi", False):
            from geosolver.engine.standard.exact_assembly.identify_answer import (
                RELAXED_TIER,
                TIER_CONFIGS,
                _identify_affine_pi_result,
            )

            possible = _identify_affine_pi_result(
                answer_hp=value,
                config=TIER_CONFIGS.get(payload["tier"], TIER_CONFIGS[RELAXED_TIER]),
                input_precision_dps=discovery_precision,
                # A pi/Angle feature may cancel in the final answer. Keep the
                # speculative prefix cheap; the existing fallback still searches
                # the full affine-pi family after algebraic reconstruction.
                rational_only=True,
            )
            if possible is not None:
                root = mp.mpf(str(sp.N(sp.sympify(possible.selected_exact_value), precision + 50)))
                root_error = abs(root) * mp.power(10, -(precision + 40))
                if mp.isfinite(uncertainty) and abs(root - value) <= uncertainty + root_error:
                    proposal = possible
        if proposal is None:
            proposal = _identify_answer_proposal(
                answer_hp=value, tier=payload["tier"], input_precision_dps=discovery_precision
            )
        proposal = replace(
            proposal, input_precision_dps=precision, discovery_precision_dps=discovery_precision
        )
        if proposal.selected_exact_value is None:
            return encode_identification(proposal)
        expression = sp.sympify(proposal.selected_exact_value)
        root = mp.mpf(str(sp.N(expression, precision + 50)))
        root_error = abs(root) * mp.power(10, -(precision + 40))
        distance = abs(root - value)
        if not mp.isfinite(uncertainty) or distance > uncertainty + root_error:
            return encode_identification(
                replace(
                    proposal,
                    exact_status="verification_failed",
                    selected_exact_value=None,
                    verification_residual=distance,
                    numeric_fallback_value=value,
                )
            )
        try:
            descriptor = describe_exact(expression, verified_polynomial=proposal.minimal_polynomial)
        except (ValueError, NotImplementedError):
            return encode_identification(
                replace(
                    proposal,
                    exact_status="not_identified",
                    selected_exact_value=None,
                    numeric_fallback_value=value,
                )
            )
        return encode_identification(
            replace(proposal, descriptor=descriptor, verification_residual=distance)
        )
