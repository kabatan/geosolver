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

function line_through(first::Point2{T}, second::Point2{T}) where {T<:Real}
    return Line2(first, Point2(second.x - first.x, second.y - first.y))
end

circle2(center::Point2{T}, radius::T) where {T<:Real} = Circle2(center, radius)
