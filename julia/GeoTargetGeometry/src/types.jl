"""A numeric-generic Cartesian point."""
struct Point2{T<:Real}
    x::T
    y::T
end

function Point2(x::Real, y::Real)
    promoted_x, promoted_y = promote(x, y)
    return Point2{typeof(promoted_x)}(promoted_x, promoted_y)
end

"""An unnormalized directed line represented by an anchor and direction."""
struct Line2{T<:Real}
    anchor::Point2{T}
    direction::Point2{T}
end

"""A circle. Radius validity remains a separate domain/guard semantic."""
struct Circle2{T<:Real}
    center::Point2{T}
    radius::T
end

point2(x::Real, y::Real) = Point2(x, y)

function line_through(first::Point2, second::Point2)
    first_x, first_y, second_x, second_y =
        promote(first.x, first.y, second.x, second.y)
    anchor = Point2(first_x, first_y)
    return Line2(anchor, Point2(second_x - first_x, second_y - first_y))
end

function circle2(center::Point2, radius::Real)
    center_x, center_y, promoted_radius = promote(center.x, center.y, radius)
    return Circle2(Point2(center_x, center_y), promoted_radius)
end
