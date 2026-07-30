#!/usr/bin/env julia

# Exact straight-line replay over Nemo's direct FLINT qqbar wrapper.  This
# worker consumes a truth-blind JSON DAG and prints one compact JSON result.

using JSON3
using Nemo

const QB = algebraic_closure(QQ)

struct ReplayFailure <: Exception
  message::String
end
Base.showerror(io::IO, error::ReplayFailure) = print(io, error.message)

struct QPoint
  x::QQBarFieldElem
  y::QQBarFieldElem
end

struct QLine
  a::QQBarFieldElem
  b::QQBarFieldElem
  c::QQBarFieldElem
end

struct QCircle
  center::QPoint
  radius::QQBarFieldElem
end

struct QArc
  circle::QCircle
  start::QPoint
  finish::QPoint
  including::Union{Nothing, QPoint}
  excluding::Union{Nothing, QPoint}
end

struct PiMultiple
  coefficient::Rational{BigInt}
end

struct AngleExpression
  cosine::QQBarFieldElem
  sine::QQBarFieldElem
  lower_pi::Rational{BigInt}
  upper_pi::Rational{BigInt}
end

to_qbar(value::QQBarFieldElem) = value
to_qbar(value::QQFieldElem) = QB(value)
to_qbar(value::Integer) = QB(value)
to_qbar(value::Rational) = QB(value)

function exact_rational(text::AbstractString)::Rational{BigInt}
  parts = split(String(text), "/")
  length(parts) in (1, 2) || throw(ReplayFailure("rational literal is malformed"))
  denominator_value = length(parts) == 1 ? BigInt(1) : parse(BigInt, parts[2])
  denominator_value != 0 || throw(ReplayFailure("rational literal has zero denominator"))
  return parse(BigInt, parts[1]) // denominator_value
end

function descriptor_polynomial(coefficients, ring, variable)
  length(coefficients) >= 2 || throw(ReplayFailure("descriptor polynomial is constant"))
  degree_value = length(coefficients) - 1
  polynomial = zero(ring)
  for (index, coefficient) in enumerate(coefficients)
    polynomial += ZZ(parse(BigInt, string(coefficient))) * variable^(degree_value - index + 1)
  end
  leading_coefficient(polynomial) > 0 || throw(ReplayFailure("descriptor leading coefficient is not positive"))
  return polynomial
end

function interval_for_descriptor(descriptor)
  interval = haskey(descriptor, "isolating_interval") ? descriptor["isolating_interval"] : nothing
  if interval === nothing && haskey(descriptor, "polynomial_metadata")
    metadata = descriptor["polynomial_metadata"]
    interval = haskey(metadata, "isolating_interval") ? metadata["isolating_interval"] : nothing
  end
  interval === nothing && throw(ReplayFailure("descriptor isolating interval is missing"))
  return exact_rational(string(interval["left"])), exact_rational(string(interval["right"]))
end

function descriptor_root(descriptor)::QQBarFieldElem
  ring, variable = polynomial_ring(ZZ, "qqbar_descriptor_x")
  coefficients = descriptor["coefficients_high_to_low"]
  polynomial = descriptor_polynomial(coefficients, ring, variable)
  left, right = interval_for_descriptor(descriptor)
  left <= right || throw(ReplayFailure("descriptor isolating interval is reversed"))
  candidates = QQBarFieldElem[]
  for root_value in roots(QB, polynomial)
    if isreal(root_value) && root_value >= to_qbar(left) && root_value <= to_qbar(right)
      push!(candidates, root_value)
    end
  end
  length(candidates) == 1 || throw(ReplayFailure("isolating interval does not select exactly one real root"))
  selected = only(candidates)
  degree(selected) == degree(polynomial) || throw(ReplayFailure("descriptor polynomial is not the selected minimal polynomial"))
  minpoly(ring, selected) == polynomial || throw(ReplayFailure("descriptor polynomial normalization mismatch"))
  return selected
end

qpoint(x, y) = QPoint(to_qbar(x), to_qbar(y))
qadd(first::QPoint, second::QPoint) = QPoint(first.x + second.x, first.y + second.y)
qsub(first::QPoint, second::QPoint) = QPoint(first.x - second.x, first.y - second.y)
qscale(value::QPoint, scalar) = QPoint(value.x * to_qbar(scalar), value.y * to_qbar(scalar))
qdivide(value::QPoint, scalar) = QPoint(value.x / to_qbar(scalar), value.y / to_qbar(scalar))
qdot(first::QPoint, second::QPoint) = first.x * second.x + first.y * second.y
qcross(first::QPoint, second::QPoint) = first.x * second.y - first.y * second.x
qnorm(value::QPoint) = sqrt(qdot(value, value))

function qline(arguments...)
  if length(arguments) == 2 && arguments[1] isa QPoint && arguments[2] isa QPoint
    first, second = arguments
    value = QLine(
      first.y - second.y,
      second.x - first.x,
      first.x * second.y - second.x * first.y,
    )
  elseif length(arguments) == 3
    value = QLine(to_qbar(arguments[1]), to_qbar(arguments[2]), to_qbar(arguments[3]))
  else
    throw(ReplayFailure("unsupported Line arguments"))
  end
  iszero(value.a^2 + value.b^2) && throw(ReplayFailure("degenerate line"))
  return value
end

function qcircle(center::QPoint, radius)
  radius_value = to_qbar(radius)
  radius_value >= 0 || throw(ReplayFailure("negative circle radius"))
  return QCircle(center, radius_value)
end

function qdistance(first, second=nothing)
  if first isa QPoint && second === nothing
    return qnorm(first)
  elseif first isa QPoint && second isa QPoint
    return qnorm(qsub(first, second))
  elseif first isa QLine && second isa QPoint
    return qdistance(second, first)
  elseif first isa QPoint && second isa QLine
    return abs(second.a * first.x + second.b * first.y + second.c) / sqrt(second.a^2 + second.b^2)
  end
  throw(ReplayFailure("unsupported Distance arguments"))
end

function qmidpoint(first, second=nothing)
  if first isa QPoint && second isa QPoint
    return qdivide(qadd(first, second), 2)
  elseif first isa QArc && second === nothing
    return qarc_midpoint(first)
  elseif first isa QCircle && second === nothing
    return first.center
  end
  throw(ReplayFailure("unsupported Midpoint arguments"))
end

function qarea(points::QPoint...)
  length(points) >= 3 || throw(ReplayFailure("Area needs at least three points"))
  double = zero(QB)
  for index in eachindex(points)
    next_index = index == length(points) ? 1 : index + 1
    double += points[index].x * points[next_index].y - points[index].y * points[next_index].x
  end
  return abs(double) / 2
end

function qcircumcenter(first::QPoint, second::QPoint, third::QPoint)
  determinant = 2 * (
    first.x * (second.y - third.y) +
    second.x * (third.y - first.y) +
    third.x * (first.y - second.y)
  )
  iszero(determinant) && throw(ReplayFailure("degenerate circumcenter"))
  ux = (
    (first.x^2 + first.y^2) * (second.y - third.y) +
    (second.x^2 + second.y^2) * (third.y - first.y) +
    (third.x^2 + third.y^2) * (first.y - second.y)
  ) / determinant
  uy = (
    (first.x^2 + first.y^2) * (third.x - second.x) +
    (second.x^2 + second.y^2) * (first.x - third.x) +
    (third.x^2 + third.y^2) * (second.x - first.x)
  ) / determinant
  return QPoint(ux, uy)
end

function qcircumcircle(first::QPoint, second::QPoint, third::QPoint)
  center_value = qcircumcenter(first, second, third)
  return qcircle(center_value, qdistance(center_value, first))
end

qorthocenter(first::QPoint, second::QPoint, third::QPoint) = qsub(qadd(qadd(first, second), third), qscale(qcircumcenter(first, second, third), 2))

function qtriangle_center(first::QPoint, second::QPoint, third::QPoint; external=false, vertex="A")
  weights = QQBarFieldElem[qdistance(second, third), qdistance(third, first), qdistance(first, second)]
  if external
    index = vertex == "A" ? 1 : vertex == "B" ? 2 : vertex == "C" ? 3 : 0
    index > 0 || throw(ReplayFailure("unsupported excenter vertex"))
    weights[index] = -weights[index]
  end
  denominator_value = sum(weights)
  iszero(denominator_value) && throw(ReplayFailure("degenerate triangle center"))
  points = (first, second, third)
  x_value = sum(weights[index] * points[index].x for index in 1:3) / denominator_value
  y_value = sum(weights[index] * points[index].y for index in 1:3) / denominator_value
  return QPoint(x_value, y_value), denominator_value
end

qincenter(first_point::QPoint, second::QPoint, third::QPoint) = qtriangle_center(first_point, second, third)[1]

function qincircle(first::QPoint, second::QPoint, third::QPoint)
  center_value, perimeter = qtriangle_center(first, second, third)
  return qcircle(center_value, 2 * qarea(first, second, third) / perimeter)
end

qexcenter(first_point::QPoint, second::QPoint, third::QPoint; vertex="A") = qtriangle_center(first_point, second, third; external=true, vertex=vertex)[1]

function qfoot(first, second)
  value, axis = first isa QPoint ? (first, second) : (second, first)
  value isa QPoint && axis isa QLine || throw(ReplayFailure("unsupported FootOfPerpendicular arguments"))
  denominator_value = axis.a^2 + axis.b^2
  factor = (axis.a * value.x + axis.b * value.y + axis.c) / denominator_value
  return QPoint(value.x - axis.a * factor, value.y - axis.b * factor)
end

function qclosest(first, second)
  if first isa QPoint && second isa QLine
    return qfoot(first, second)
  elseif second isa QPoint && first isa QLine
    return qfoot(second, first)
  end
  throw(ReplayFailure("unsupported ClosestPoint arguments"))
end

function qcontact(first, second)
  if first isa QCircle && second isa QLine
    return qfoot(first.center, second)
  elseif second isa QCircle && first isa QLine
    return qfoot(second.center, first)
  end
  return qfoot(first, second)
end

function qperpendicular_line(first, second)
  axis, through = first isa QLine ? (first, second) : (second, first)
  axis isa QLine && through isa QPoint || throw(ReplayFailure("unsupported PerpendicularLine arguments"))
  return qline(axis.b, -axis.a, -(axis.b * through.x - axis.a * through.y))
end

function qparallel_line(first, second)
  axis, through = first isa QLine ? (first, second) : (second, first)
  axis isa QLine && through isa QPoint || throw(ReplayFailure("unsupported ParallelLine arguments"))
  return qline(axis.a, axis.b, -(axis.a * through.x + axis.b * through.y))
end

function qangle_bisector(first::QPoint, vertex::QPoint, third::QPoint)
  left, right = qsub(first, vertex), qsub(third, vertex)
  direction = qadd(qdivide(left, qnorm(left)), qdivide(right, qnorm(right)))
  iszero(qdot(direction, direction)) && throw(ReplayFailure("degenerate angle bisector"))
  return qline(vertex, qadd(vertex, direction))
end

function qreflect(value::QPoint, mirror::QLine)
  foot = qfoot(value, mirror)
  return qsub(qscale(foot, 2), value)
end

qpoint_on_segment(first::QPoint, second::QPoint, parameter) = qadd(first, qscale(qsub(second, first), parameter))

function qarc(value::QCircle, start::QPoint, finish::QPoint; including=nothing, excluding=nothing)
  including !== nothing && excluding !== nothing && throw(ReplayFailure("arc cannot include and exclude simultaneously"))
  return QArc(value, start, finish, including, excluding)
end

qrelative(reference::QPoint, value::QPoint) = QPoint(qdot(reference, value), qcross(reference, value))

function qangle_half(value::QPoint)
  if value.y > 0 || (iszero(value.y) && value.x >= 0)
    return 0
  end
  return 1
end

function qangle_leq(first::QPoint, second::QPoint)
  first_half, second_half = qangle_half(first), qangle_half(second)
  first_half != second_half && return first_half < second_half
  return qcross(first, second) >= 0
end

qin_ccw(value::QPoint, start::QPoint, finish::QPoint) = qangle_leq(qrelative(start, value), qrelative(start, finish))

function qarc_membership(value::QPoint, item::QArc)
  origin = item.circle.center
  start, finish, candidate = qsub(item.start, origin), qsub(item.finish, origin), qsub(value, origin)
  on_first = qin_ccw(candidate, start, finish)
  if item.including !== nothing
    use_first = qin_ccw(qsub(item.including, origin), start, finish)
  elseif item.excluding !== nothing
    use_first = !qin_ccw(qsub(item.excluding, origin), start, finish)
  else
    use_first = qcross(start, finish) >= 0
  end
  return on_first == use_first
end

function qarc_midpoint(item::QArc)
  origin = item.circle.center
  first, second = qsub(item.start, origin), qsub(item.finish, origin)
  total = qadd(first, second)
  candidate = if iszero(qdot(total, total))
    QPoint(origin.x - first.y, origin.y + first.x)
  else
    qadd(origin, qscale(total, item.circle.radius / qnorm(total)))
  end
  alternate = qsub(qscale(origin, 2), candidate)
  matches = QPoint[value for value in (candidate, alternate) if qarc_membership(value, item)]
  length(matches) == 1 || throw(ReplayFailure("arc midpoint branch is not unique"))
  return only(matches)
end

function qline_line(first::QLine, second::QLine)
  determinant = first.a * second.b - second.a * first.b
  iszero(determinant) && return QPoint[]
  return QPoint[
    QPoint(
      (first.b * second.c - second.b * first.c) / determinant,
      (second.a * first.c - first.a * second.c) / determinant,
    )
  ]
end

function qline_circle(axis::QLine, value::QCircle)
  denominator_value = axis.a^2 + axis.b^2
  signed = axis.a * value.center.x + axis.b * value.center.y + axis.c
  foot = QPoint(
    value.center.x - axis.a * signed / denominator_value,
    value.center.y - axis.b * signed / denominator_value,
  )
  height_square = value.radius^2 - signed^2 / denominator_value
  height_square < 0 && return QPoint[]
  iszero(height_square) && return QPoint[foot]
  height = sqrt(height_square / denominator_value)
  offset = QPoint(axis.b * height, -axis.a * height)
  return QPoint[qadd(foot, offset), qsub(foot, offset)]
end

function qcircle_circle(first::QCircle, second::QCircle)
  delta = qsub(second.center, first.center)
  squared_distance = qdot(delta, delta)
  iszero(squared_distance) && return QPoint[]
  distance_centers = sqrt(squared_distance)
  distance_centers > first.radius + second.radius && return QPoint[]
  distance_centers < abs(first.radius - second.radius) && return QPoint[]
  along = (first.radius^2 - second.radius^2 + squared_distance) / (2 * distance_centers)
  base = qadd(first.center, qscale(delta, along / distance_centers))
  height_square = first.radius^2 - along^2
  height_square < 0 && return QPoint[]
  iszero(height_square) && return QPoint[base]
  height = sqrt(height_square)
  unit = qdivide(delta, distance_centers)
  offset = QPoint(-unit.y * height, unit.x * height)
  return QPoint[qadd(base, offset), qsub(base, offset)]
end

function qintersection_candidates(first, second)
  first_arc = first isa QArc ? first : nothing
  second_arc = second isa QArc ? second : nothing
  first_base = first_arc === nothing ? first : first.circle
  second_base = second_arc === nothing ? second : second.circle
  candidates = if first_base isa QLine && second_base isa QLine
    qline_line(first_base, second_base)
  elseif first_base isa QLine && second_base isa QCircle
    qline_circle(first_base, second_base)
  elseif first_base isa QCircle && second_base isa QLine
    qline_circle(second_base, first_base)
  elseif first_base isa QCircle && second_base isa QCircle
    qcircle_circle(first_base, second_base)
  else
    throw(ReplayFailure("unsupported Intersect arguments"))
  end
  first_arc !== nothing && (candidates = [candidate for candidate in candidates if qarc_membership(candidate, first_arc)])
  second_arc !== nothing && (candidates = [candidate for candidate in candidates if qarc_membership(candidate, second_arc)])
  return candidates
end

function qintersect(first_value, second_value; exclude=nothing, near=nothing, far=nothing)
  candidates = qintersection_candidates(first_value, second_value)
  exclude !== nothing && (candidates = [candidate for candidate in candidates if !iszero(qdistance(candidate, exclude))])
  isempty(candidates) && throw(ReplayFailure("intersection has no selected candidate"))
  if near !== nothing || far !== nothing
    reference = near !== nothing ? near : far
    best = candidates[1]
    best_score = qdistance(best, reference)
    for candidate in Iterators.drop(candidates, 1)
      score = qdistance(candidate, reference)
      score == best_score && throw(ReplayFailure("intersection selector tie"))
      if (near !== nothing && score < best_score) || (far !== nothing && score > best_score)
        best, best_score = candidate, score
      end
    end
    return best
  end
  length(candidates) == 1 || throw(ReplayFailure("unselected multivalued intersection"))
  return only(candidates)
end

function qangle_at_pi(value::Rational)
  normalized = BigInt(numerator(value)) // BigInt(denominator(value))
  argument = to_qbar(normalized)
  return AngleExpression(cospi(argument), sinpi(argument), normalized, normalized)
end

function qangle(first::QPoint, vertex::QPoint, third::QPoint)
  left, right = qsub(first, vertex), qsub(third, vertex)
  left_norm, right_norm = qnorm(left), qnorm(right)
  if iszero(left_norm) || iszero(right_norm)
    throw(ReplayFailure("degenerate Angle"))
  end
  cosine = qdot(left, right) / (left_norm * right_norm)
  sine = abs(qcross(left, right)) / (left_norm * right_norm)
  cosine^2 + sine^2 == 1 || throw(ReplayFailure("angle unit identity failed"))
  return AngleExpression(cosine, sine, 0//1, 1//1)
end

function qangle_neg(value::AngleExpression)
  return AngleExpression(value.cosine, -value.sine, -value.upper_pi, -value.lower_pi)
end

function qangle_add(first::AngleExpression, second::AngleExpression)
  return AngleExpression(
    first.cosine * second.cosine - first.sine * second.sine,
    first.sine * second.cosine + first.cosine * second.sine,
    first.lower_pi + second.lower_pi,
    first.upper_pi + second.upper_pi,
  )
end

function as_angle(value)
  value isa AngleExpression && return value
  value isa PiMultiple && return qangle_at_pi(value.coefficient)
  if value isa Rational && value == 0
    return qangle_at_pi(0//1)
  elseif value isa QQBarFieldElem && iszero(value)
    return qangle_at_pi(0//1)
  end
  throw(ReplayFailure("scalar is not an exact angle expression"))
end

qangle_sub(first, second) = qangle_add(as_angle(first), qangle_neg(as_angle(second)))

function qangle_zero(value::AngleExpression)
  value.cosine == 1 && iszero(value.sine) || return false
  first_lift = cld(numerator(value.lower_pi), 2 * denominator(value.lower_pi))
  last_lift = fld(numerator(value.upper_pi), 2 * denominator(value.upper_pi))
  first_lift == last_lift || throw(ReplayFailure("angle equality has ambiguous full-turn lift"))
  return first_lift == 0
end

semantic_zero(value::AngleExpression) = qangle_zero(value)
semantic_zero(value::QQBarFieldElem) = iszero(value)
semantic_zero(value::Rational) = iszero(value)
semantic_zero(value::Integer) = iszero(value)

function scalar_compare(first, second)
  first_value, second_value = to_qbar(first), to_qbar(second)
  return first_value < second_value ? -1 : first_value > second_value ? 1 : 0
end

function binary_operation(name::String, first, second)
  if name == "add"
    if first isa AngleExpression || second isa AngleExpression || first isa PiMultiple || second isa PiMultiple
      return qangle_add(as_angle(first), as_angle(second))
    elseif first isa QPoint && second isa QPoint
      return qadd(first, second)
    end
    return first + second
  elseif name == "sub"
    if first isa AngleExpression || second isa AngleExpression || first isa PiMultiple || second isa PiMultiple
      return qangle_sub(first, second)
    elseif first isa QPoint && second isa QPoint
      return qsub(first, second)
    end
    return first - second
  elseif name == "mul"
    first isa QPoint && return qscale(first, second)
    second isa QPoint && return qscale(second, first)
    if first isa PiMultiple && second isa Rational
      return PiMultiple(first.coefficient * second)
    elseif second isa PiMultiple && first isa Rational
      return PiMultiple(second.coefficient * first)
    end
    return first * second
  elseif name == "div"
    first isa QPoint && return qdivide(first, second)
    if first isa PiMultiple && second isa Rational
      return PiMultiple(first.coefficient / second)
    end
    return first / second
  elseif name == "pow"
    second isa Rational && denominator(second) == 1 || throw(ReplayFailure("only integer powers are supported"))
    exponent = Int(numerator(second))
    return first^exponent
  end
  throw(ReplayFailure("unsupported binary operation"))
end

function comparison(name::String, first, second)
  value = scalar_compare(first, second)
  return name == "eq" ? value == 0 :
    name == "ne" ? value != 0 :
    name == "lt" ? value < 0 :
    name == "le" ? value <= 0 :
    name == "gt" ? value > 0 :
    name == "ge" ? value >= 0 :
    throw(ReplayFailure("unsupported comparison"))
end

function call_function(name::String, arguments, keywords)
  keyword(name_value, default=nothing) = haskey(keywords, name_value) ? keywords[name_value] : default
  if name == "Point"
    return qpoint(arguments...)
  elseif name == "Line"
    return qline(arguments...)
  elseif name == "Distance"
    return qdistance(arguments...)
  elseif name in ("Midpoint", "MidPoint")
    return qmidpoint(arguments...)
  elseif name == "Center"
    value = only(arguments)
    return value isa QCircle ? value.center : value isa QArc ? value.circle.center : throw(ReplayFailure("unsupported Center argument"))
  elseif name == "Radius"
    value = only(arguments)
    return value isa QCircle ? value.radius : value isa QArc ? value.circle.radius : throw(ReplayFailure("unsupported Radius argument"))
  elseif name == "Area"
    return qarea(arguments...)
  elseif name == "Circumcenter"
    return qcircumcenter(arguments...)
  elseif name == "Circumcircle"
    return qcircumcircle(arguments...)
  elseif name == "Orthocenter"
    return qorthocenter(arguments...)
  elseif name == "Incenter"
    return qtriangle_center(arguments...)[1]
  elseif name == "Incircle"
    return qincircle(arguments...)
  elseif name == "Excenter"
    return qtriangle_center(arguments...; external=true, vertex=keyword("vertex", "A"))[1]
  elseif name == "FootOfPerpendicular"
    return qfoot(arguments...)
  elseif name == "ClosestPoint"
    return qclosest(arguments...)
  elseif name == "ContactPoint"
    return qcontact(arguments...)
  elseif name == "PerpendicularLine"
    return qperpendicular_line(arguments...)
  elseif name == "ParallelLine"
    return qparallel_line(arguments...)
  elseif name == "AngleBisector"
    return qangle_bisector(arguments...)
  elseif name == "Reflect"
    return qreflect(arguments...)
  elseif name == "PointOnSegment"
    return qpoint_on_segment(arguments...)
  elseif name == "Arc"
    return qarc(arguments...; including=keyword("including"), excluding=keyword("excluding"))
  elseif name == "Intersect"
    return qintersect(arguments...; exclude=keyword("exclude"), near=keyword("near"), far=keyword("far"))
  elseif name in ("OnLine", "Collinear")
    value = arguments[1]
    axis = length(arguments) == 2 && arguments[2] isa QLine ? arguments[2] : qline(arguments[2], arguments[3])
    return axis.a * value.x + axis.b * value.y + axis.c
  elseif name == "OnCircle"
    return qdistance(arguments[1], arguments[2].center) - arguments[2].radius
  elseif name == "OnSegment"
    return qdistance(arguments[2], arguments[1]) + qdistance(arguments[1], arguments[3]) - qdistance(arguments[2], arguments[3])
  elseif name == "Perpendicular"
    first, second = arguments
    return first isa QLine && second isa QLine ? first.a * second.a + first.b * second.b : qdot(first, second)
  elseif name == "Angle"
    return qangle(arguments...)
  elseif name == "sqrt"
    value = to_qbar(only(arguments))
    value >= 0 || throw(ReplayFailure("sqrt argument is negative"))
    return sqrt(value)
  elseif name == "abs"
    return abs(to_qbar(only(arguments)))
  elseif name == "Assume"
    value = only(arguments)
    value isa Bool || throw(ReplayFailure("Assume argument is not Boolean"))
    return value
  elseif name == "AssumeGt"
    return scalar_compare(arguments[1], arguments[2]) > 0
  elseif name == "AssumeLt"
    return scalar_compare(arguments[1], arguments[2]) < 0
  elseif name == "AssumeNe"
    return scalar_compare(arguments[1], arguments[2]) != 0
  elseif name == "AssumeAcute"
    first, second, third = arguments
    checks = (
      qdot(qsub(second, first), qsub(third, first)),
      qdot(qsub(first, second), qsub(third, second)),
      qdot(qsub(first, third), qsub(second, third)),
    )
    return all(value > 0 for value in checks) && qarea(first, second, third) > 0
  end
  throw(ReplayFailure("unsupported DSL call: " * name))
end

function scalar_degrees(value)
  if value isa QQBarFieldElem
    return Int[degree(value)]
  elseif value isa QPoint
    return vcat(scalar_degrees(value.x), scalar_degrees(value.y))
  elseif value isa QLine
    return vcat(scalar_degrees(value.a), scalar_degrees(value.b), scalar_degrees(value.c))
  elseif value isa QCircle
    return vcat(scalar_degrees(value.center), scalar_degrees(value.radius))
  elseif value isa QArc
    result = vcat(scalar_degrees(value.circle), scalar_degrees(value.start), scalar_degrees(value.finish))
    value.including !== nothing && append!(result, scalar_degrees(value.including))
    value.excluding !== nothing && append!(result, scalar_degrees(value.excluding))
    return result
  elseif value isa AngleExpression
    return Int[degree(value.cosine), degree(value.sine)]
  end
  return Int[]
end

function replay(job)
  job["truth_used"] == false || throw(ReplayFailure("job truth flag is not false"))
  job["post_process_used"] == false || throw(ReplayFailure("job post-process flag is not false"))
  coordinates = QQBarFieldElem[descriptor_root(item) for item in job["coordinate_descriptors"]]
  target = descriptor_root(job["target_descriptor"])
  values = Any[]
  operation_counts = Dict{String, Int}()
  maximum_degree = isempty(coordinates) ? 1 : maximum(degree(value) for value in coordinates)

  for node in job["nodes"]
    operation = String(node["op"])
    operation_counts[operation] = get(operation_counts, operation, 0) + 1
    value = if operation == "coordinate"
      coordinates[Int(node["index"]) + 1]
    elseif operation == "rational"
      exact_rational(String(node["value"]))
    elseif operation == "string"
      String(node["value"])
    elseif operation == "bool"
      Bool(node["value"])
    elseif operation == "pi"
      PiMultiple(1//1)
    elseif operation in ("add", "sub", "mul", "div", "pow")
      arguments = [values[Int(index) + 1] for index in node["args"]]
      binary_operation(operation, arguments...)
    elseif operation == "neg"
      argument = values[Int(node["args"][1]) + 1]
      argument isa AngleExpression ? qangle_neg(argument) : -argument
    elseif operation == "pos"
      values[Int(node["args"][1]) + 1]
    elseif operation == "not"
      !Bool(values[Int(node["args"][1]) + 1])
    elseif operation in ("eq", "ne", "lt", "le", "gt", "ge")
      arguments = [values[Int(index) + 1] for index in node["args"]]
      comparison(operation, arguments...)
    elseif operation in ("and", "or")
      arguments = Bool[values[Int(index) + 1] for index in node["args"]]
      operation == "and" ? all(arguments) : any(arguments)
    elseif operation == "call"
      arguments = Any[values[Int(index) + 1] for index in node["args"]]
      keywords = Dict{String, Any}(
        String(name) => values[Int(index) + 1] for (name, index) in pairs(node["kwargs"])
      )
      call_function(String(node["name"]), arguments, keywords)
    else
      throw(ReplayFailure("unsupported DAG operation: " * operation))
    end
    push!(values, value)
    degrees = scalar_degrees(value)
    !isempty(degrees) && (maximum_degree = max(maximum_degree, maximum(degrees)))
  end

  for index in job["relation_roots"]
    semantic_zero(values[Int(index) + 1]) || throw(ReplayFailure("source relation failed exact replay"))
  end
  for index in job["guard_roots"]
    values[Int(index) + 1] === true || throw(ReplayFailure("source guard failed exact replay"))
  end
  for index in job["bound_roots"]
    values[Int(index) + 1] === true || throw(ReplayFailure("source bound failed exact replay"))
  end
  answer = values[Int(job["answer_root"]) + 1]
  answer_value = to_qbar(answer)
  answer_value == target || throw(ReplayFailure("raw source answer does not equal target descriptor"))

  return Dict(
    "schema_version" => "geotarget.qqbar-straight-line-replay/v1",
    "status" => "EXACT_REPLAY_ACCEPTED",
    "backend" => "FLINT_QQBAR_VIA_NEMO",
    "backend_activated" => true,
    "truth_used" => false,
    "post_process_used" => false,
    "completeness_claim_permitted" => false,
    "target_image_completeness" => "NOT_RUN",
    "source_relation_count" => length(job["relation_roots"]),
    "source_guard_count" => length(job["guard_roots"]),
    "source_bound_count" => length(job["bound_roots"]),
    "source_raw_answer_exact" => true,
    "target_link_exact" => true,
    "coordinate_count" => length(coordinates),
    "coordinate_degrees" => [degree(value) for value in coordinates],
    "maximum_intermediate_qqbar_degree" => maximum_degree,
    "dag_node_count" => length(job["nodes"]),
    "operation_counts" => operation_counts,
  )
end

function main()
  length(ARGS) == 1 || error("usage: qqbar_worker.jl JOB.json")
  result = try
    job = JSON3.read(read(ARGS[1], String))
    replay(job)
  catch error
    message = sprint(showerror, error)
    Dict(
      "schema_version" => "geotarget.qqbar-straight-line-replay/v1",
      "status" => "EXACT_REPLAY_REJECTED",
      "backend" => "FLINT_QQBAR_VIA_NEMO",
      "backend_activated" => true,
      "truth_used" => false,
      "post_process_used" => false,
      "completeness_claim_permitted" => false,
      "target_image_completeness" => "NOT_RUN",
      "error_type" => string(typeof(error)),
      "error" => first(message, min(length(message), 512)),
    )
  end
  println(JSON3.write(result))
end

main()
