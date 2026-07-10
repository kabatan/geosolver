"""Author the open-world plugin example as canonical GeoTarget problem JSON."""

from __future__ import annotations

import argparse
from collections.abc import Sequence
from pathlib import Path

from geotarget import PluginLock, ProblemBuilder, ProblemSpecV1

GEOMETRY_PLUGIN_ID = "5cba7841-765c-4ef1-987e-27fcb9985e3d/builtin_geometry"
GEOMETRY_CONTENT_HASH = (
    "sha256:819a583438dc13c64bab4f413b559687dc01577bc513b4b64a6f6cba89a50831"
)
BLACK_BOX_PLUGIN_ID = "2f8f6d72-565e-43fe-865b-a3c497a211ef/black_box_circle"
# Kept in lockstep with BLACK_BOX_CIRCLE_CONTENT_HASH in BlackBoxCirclePlugin.jl.
BLACK_BOX_CONTENT_HASH = (
    "sha256:96d65df1a9589d8c4a8d13acf53fcce5c4f089c9c8430c20d21e09c296f6a646"
)

SCALAR = f"{GEOMETRY_PLUGIN_ID}::scalar"
HIDDEN_POINT = f"{BLACK_BOX_PLUGIN_ID}::hidden_point2"
UNIT_CIRCLE = f"{BLACK_BOX_PLUGIN_ID}::unit_circle"


def build_problem() -> ProblemSpecV1:
    """Build x-coordinate targets for intersections of y=0 and an opaque unit circle."""
    builder = ProblemBuilder(
        plugins=(
            PluginLock(
                plugin_id=GEOMETRY_PLUGIN_ID,
                version="0.1.2",
                core_abi="1.0.0",
                content_hash=GEOMETRY_CONTENT_HASH,
            ),
            PluginLock(
                plugin_id=BLACK_BOX_PLUGIN_ID,
                version="0.1.0",
                core_abi="1.0.0",
                content_hash=BLACK_BOX_CONTENT_HASH,
            ),
        )
    )
    x = builder.variable(
        "x", type_id=SCALAR, origin=1.0, scale=0.25, lower=0.5, upper=1.5
    )
    zero = builder.literal(0.0, type_id=SCALAR, node_id="zero")
    point = builder.call(HIDDEN_POINT, x, zero, node_id="point")
    incidence = builder.call(UNIT_CIRCLE, point, node_id="on_unit_circle")
    return builder.relation(incidence).target(x).build()


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output", type=Path, default=Path(__file__).with_name("problem.json")
    )
    args = parser.parse_args(argv)
    problem = build_problem()
    args.output.write_text(problem.canonical_json(), encoding="utf-8")
    print(problem.content_hash())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
