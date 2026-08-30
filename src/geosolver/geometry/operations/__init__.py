"""Geometry Operations"""

from geosolver.geometry.operations.basic import (
    Angle,
    Area,
    AreConcyclic,
    Circumference,
    Distance,
    Dot,
    IsTangent,
    Length,
    Midpoint,
    OnCircle,
    OnLine,
    OnSegment,
    Parallel,
    ParallelismMeasure,
    Perimeter,
    Perpendicular,
    Radius,
    Slope,
    Vector,
)
from geosolver.geometry.operations.constructions import (
    AngleBisector,
    CircleThroughPoint,
    CircleThroughThreePoints,
    FootOfPerpendicular,
    InscribedPolygonVertices,
    ParallelLine,
    PerpendicularBisector,
    PerpendicularLine,
    PointOnCircle,
    PointOnLine,
    PointOnSegment,
    Tangent,
)

# Aliases
TangentLine = Tangent
from geosolver.geometry.operations.advanced import (
    Polar,
    Pole,
    PowerOfPoint,
    RadicalAxis,
)
from geosolver.geometry.operations.aliases import Center, Collinear, ContactPoint
from geosolver.geometry.operations.arc import (
    Arc,
    PointOnArc,
)
from geosolver.geometry.operations.constructions import (
    InscribedPolygon,
    RegularPolygon,
)
from geosolver.geometry.operations.intersections import (
    ClosestPoint,
    Intersect,
    IntersectCircles,
    IntersectLineCircle,
    IntersectLines,
)
from geosolver.geometry.operations.numeric import Degrees, IsInteger, IsPrime
from geosolver.geometry.operations.transforms import (
    Reflect,
    Rotate,
)
from geosolver.geometry.operations.triangle import (
    Centroid,
    Circumcenter,
    Circumcircle,
    Excenter,
    Excircle,
    FermatPoint,
    FeuerbachPoint,
    GergonnePoint,
    Incenter,
    Incircle,
    IncircleContactPoint,
    IsodynamicPoint,
    Mittenpunkt,
    NagelPoint,
    NinePointCenter,
    NinePointCircle,
    Orthocenter,
    SpiekerCenter,
    SymmedianPoint,
    TriangleCenter,
)

__all__ = [
    # basic
    "Distance",
    "Midpoint",
    "Angle",
    "Radius",
    "Area",
    "Vector",
    "Dot",
    "OnLine",
    "OnSegment",
    "IsTangent",
    "Perpendicular",
    "Parallel",
    "Slope",
    "Length",
    "Perimeter",
    "Circumference",
    "ParallelismMeasure",
    "AreConcyclic",
    "OnCircle",
    # constructions
    "AngleBisector",
    "PerpendicularLine",
    "ParallelLine",
    "PerpendicularBisector",
    "FootOfPerpendicular",
    "PointOnLine",
    "PointOnSegment",
    "PointOnCircle",
    "CircleThroughPoint",
    "CircleThroughThreePoints",
    "RegularPolygon",
    "InscribedPolygon",
    "InscribedPolygonVertices",
    "TangentLine",
    "Tangent",
    # intersections
    "Intersect",
    "IntersectLines",
    "IntersectLineCircle",
    "IntersectCircles",
    "ClosestPoint",
    # transforms
    "Rotate",
    "Reflect",
    # triangle
    "Centroid",
    "Incenter",
    "Circumcenter",
    "Orthocenter",
    "Incircle",
    "Circumcircle",
    "Excenter",
    "Excircle",
    "NinePointCircle",
    "TriangleCenter",
    "NinePointCenter",
    "SymmedianPoint",
    "GergonnePoint",
    "NagelPoint",
    "Mittenpunkt",
    "SpiekerCenter",
    "FeuerbachPoint",
    "FermatPoint",
    "IsodynamicPoint",
    "IncircleContactPoint",
    # arc
    "Arc",
    "PointOnArc",
    # polygon
    # advanced
    "PowerOfPoint",
    "Polar",
    "Pole",
    "RadicalAxis",
    # numeric
    "Degrees",
    "IsInteger",
    "IsPrime",
    "Center",
    "Collinear",
    "ContactPoint",
]
