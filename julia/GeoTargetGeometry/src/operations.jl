_squared_norm(point::Point2) = point.x * point.x + point.y * point.y

function _squared_distance(first::Point2, second::Point2)
    dx = first.x - second.x
    dy = first.y - second.y
    return dx * dx + dy * dy
end

distance(first::Point2, second::Point2) = sqrt(_squared_distance(first, second))

scalar_equality_residual(left::Real, right::Real) = left - right
scalar_equality_truth(left::Real, right::Real) = iszero(left - right)
positive_margin(value::Real) = value

safe_domain_margin(line::Line2) = _squared_norm(line.direction)
safe_domain_margin(circle::Circle2) = circle.radius
safe_domain_singularity(value) = iszero(safe_domain_margin(value))

function _point_on_line(line::Line2, parameter)
    return Point2(
        line.anchor.x + parameter * line.direction.x,
        line.anchor.y + parameter * line.direction.y,
    )
end

"""
Return all real line-circle intersections with algebraically stable branch keys.

The candidate validity margin covers the line/circle domain. Root separation is
not conflated with validity; selectors report their own independent margin.
"""
function line_circle_intersections(line::Line2, circle::Circle2)
    offset = Point2(line.anchor.x - circle.center.x, line.anchor.y - circle.center.y)
    a = _squared_norm(line.direction)
    iszero(a) && return Choice((), (), ())

    b = 2 * (
        offset.x * line.direction.x +
        offset.y * line.direction.y
    )
    c = _squared_norm(offset) - circle.radius * circle.radius
    discriminant = b * b - 4 * a * c
    discriminant < zero(discriminant) && return Choice((), (), ())

    domain_margin = min(sqrt(a), circle.radius)
    denominator = 2 * a
    if iszero(discriminant)
        parameter = -b / denominator
        return Choice(
            (_point_on_line(line, parameter),),
            ("tangent",),
            (domain_margin,),
        )
    end

    root = sqrt(discriminant)
    negative_parameter = (-b - root) / denominator
    positive_parameter = (-b + root) / denominator
    return Choice(
        (
            _point_on_line(line, negative_parameter),
            _point_on_line(line, positive_parameter),
        ),
        ("negative_root", "positive_root"),
        (domain_margin, domain_margin),
    )
end

function _select_by_score(choice::Choice, scores::Tuple; maximize::Bool)
    isempty(choice) && throw(
        InvariantError(:empty_choice_selection, "a selector cannot select from an empty Choice"),
    )
    length(scores) == length(choice) || throw(
        InvariantError(:selector_score_mismatch, "a selector requires one score per candidate"),
    )

    best_index = 1
    for index in 2:length(choice)
        score = scores[index]
        best_score = scores[best_index]
        better = maximize ? score > best_score : score < best_score
        tied_but_stable = score == best_score && isless(choice.keys[index], choice.keys[best_index])
        (better || tied_but_stable) && (best_index = index)
    end

    best_score = scores[best_index]
    if length(choice) == 1
        selector_margin = one(best_score)
    else
        margins = tuple(
            (
                maximize ? best_score - scores[index] : scores[index] - best_score
                for index in eachindex(scores) if index != best_index
            )...,
        )
        selector_margin = minimum(margins)
    end
    return Selection(choice, best_index, selector_margin)
end

function select_near(choice::Choice, reference::Point2)
    scores = tuple((_squared_distance(candidate, reference) for candidate in choice.candidates)...)
    return _select_by_score(choice, scores; maximize = false)
end

function select_far(choice::Choice, reference::Point2)
    scores = tuple((_squared_distance(candidate, reference) for candidate in choice.candidates)...)
    return _select_by_score(choice, scores; maximize = true)
end

function _orientation_score(origin::Point2, axis_point::Point2, candidate::Point2)
    axis_x = axis_point.x - origin.x
    axis_y = axis_point.y - origin.y
    candidate_x = candidate.x - origin.x
    candidate_y = candidate.y - origin.y
    return axis_x * candidate_y - axis_y * candidate_x
end

function select_orientation(choice::Choice, origin::Point2, axis_point::Point2)
    scores = tuple(
        (_orientation_score(origin, axis_point, candidate) for candidate in choice.candidates)...,
    )
    return _select_by_score(choice, scores; maximize = true)
end
