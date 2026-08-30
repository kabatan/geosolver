"""High-precision polygon with the same geometric interface as Polygon."""

from mpmath import mp


class MPPolygon(tuple):
    def __new__(cls, vertices):
        vertices = tuple(vertices)
        if len(vertices) < 3:
            raise ValueError("Polygon must have at least 3 vertices")
        return super().__new__(cls, vertices)

    @property
    def vertices(self):
        return list(self)

    @property
    def perimeter(self):
        return mp.fsum(self[i].distance_to(self[(i + 1) % len(self)]) for i in range(len(self)))

    @property
    def area(self):
        return (
            abs(
                mp.fsum(
                    self[i].x * self[(i + 1) % len(self)].y
                    - self[i].y * self[(i + 1) % len(self)].x
                    for i in range(len(self))
                )
            )
            / 2
        )
