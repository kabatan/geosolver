"""Geometry Operations"""

from geosolver.geometry.operations.basic import (
    Distance,
    Midpoint,
    Angle,
    Radius,
    Area,
    Vector,
    Dot,
    OnSegment,
    OnLine,
    OnCircle,
    IsTangent,
    Perpendicular,
    Parallel,
    Slope,
    Length,
    Perimeter,
    Circumference,
    AreConcyclic,
    ParallelismMeasure,
)
from geosolver.geometry.operations.constructions import (
    AngleBisector,
    PerpendicularLine,
    ParallelLine,
    PerpendicularBisector,
    FootOfPerpendicular,
    PointOnLine,
    PointOnSegment,
    PointOnCircle,
    Tangent,
    CircleThroughPoint,
    CircleThroughThreePoints,
    InscribedPolygonVertices,
)
# Aliases
TangentLine = Tangent
from geosolver.geometry.operations.intersections import (
    Intersect,
    IntersectLines,
    IntersectLineCircle,
    IntersectCircles,
    ClosestPoint,
)
from geosolver.geometry.operations.triangle import (
    Centroid,
    Incenter,
    Circumcenter,
    Orthocenter,
    Incircle,
    Circumcircle,
    Excenter,
    Excircle,
    NinePointCircle,
    TriangleCenter,
    NinePointCenter,
    SymmedianPoint,
    GergonnePoint,
    NagelPoint,
    Mittenpunkt,
    SpiekerCenter,
    FeuerbachPoint,
    FermatPoint,
    IsodynamicPoint,
    IncircleContactPoint,
)
from geosolver.geometry.operations.transforms import (
    Rotate,
    Reflect,
)
from geosolver.geometry.operations.advanced import (
    PowerOfPoint,
    Polar,
    Pole,
    RadicalAxis,
)
from geosolver.geometry.operations.arc import (
    Arc,
    PointOnArc,
)
from geosolver.geometry.operations.constructions import (
    RegularPolygon,
    InscribedPolygon,
)

from geosolver.geometry.operations.numeric import IsInteger, IsPrime
from geosolver.geometry.operations.compat_aliases import Center, Collinear, ContactPoint

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
    "IsInteger",
    "IsPrime",
    "Center",
    "Collinear",
    "ContactPoint",
]
