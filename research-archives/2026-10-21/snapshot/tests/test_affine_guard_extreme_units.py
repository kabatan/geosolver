"""Optional affine proposals stay stable under very small or large units."""

import math

import pytest

from geosolver.engine.standard.search.sampling.affine_guards import affine_interior_points


@pytest.mark.parametrize("factor", ["1e-300", "1", "1e300"])
def test_affine_inequalities_keep_same_interior_at_extreme_units(factor):
    points = affine_interior_points(
        variables=("u", "v"),
        constructions=(),
        guards=(f"AssumeGt(({factor})*(u-v),0)", f"AssumeGt(({factor})*v,0)"),
        bounds=((0, 2), (0, 2)),
        count=12,
        seed=19,
    )
    assert len(points) == 12
    assert all(0 < v < u < 2 and all(math.isfinite(x) for x in (u, v)) for u, v in points)
