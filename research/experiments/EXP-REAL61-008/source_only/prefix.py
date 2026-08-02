"""Identity-blind, full-support proposal prefix for source-only experiments."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import math
import struct
from typing import Sequence

import numpy as np
from scipy.stats import qmc


SCHEMA = "geotarget.exp-real61-008.source-only-prefix/v1"
CAUCHY_PERIOD = 4
DYADIC_EXPONENTS = (0, 1, -1, 2, -2, 3, -3, 4, -4, 6, -6, 8, -8, 10, -10)
OPEN_LOW = np.nextafter(0.0, 1.0)
OPEN_HIGH = np.nextafter(1.0, 0.0)


@dataclass(frozen=True)
class Prefix:
    points: tuple[np.ndarray, ...]
    sources: tuple[str, ...]
    scale_exponents: tuple[int, ...]
    sha256: str


def _counter_seed(seed: int, ordinal: int, lane: str) -> int:
    payload = struct.pack("<qQ", int(seed), int(ordinal)) + lane.encode("ascii")
    return int.from_bytes(hashlib.sha256(payload).digest()[:16], "little")


def _open(values: np.ndarray) -> np.ndarray:
    # This protects the mathematical chart's open endpoints; it does not clip
    # any emitted problem coordinate or introduce a search envelope.
    return np.minimum(np.maximum(values, OPEN_LOW), OPEN_HIGH)


def _scale_exponent(index: int) -> int:
    return DYADIC_EXPONENTS[index % len(DYADIC_EXPONENTS)]


def _map_axis(
    unit: float,
    lower: float,
    upper: float,
    *,
    scale: float,
    chart: str,
) -> float:
    if math.isfinite(lower) and math.isfinite(upper):
        return lower + unit * (upper - lower)
    if math.isfinite(lower):
        return lower + scale * unit / (1.0 - unit)
    if math.isfinite(upper):
        return upper - scale * unit / (1.0 - unit)
    if chart == "cauchy":
        return scale * math.tan(math.pi * (unit - 0.5))
    signed = 2.0 * unit - 1.0
    return scale * signed / (1.0 - abs(signed))


def _map_point(
    units: np.ndarray,
    lower: np.ndarray,
    upper: np.ndarray,
    *,
    exponent: int,
    chart: str,
) -> np.ndarray:
    scale = math.ldexp(1.0, int(exponent))
    point = np.asarray(
        [
            _map_axis(float(unit), float(lo), float(hi), scale=scale, chart=chart)
            for unit, lo, hi in zip(units, lower, upper, strict=True)
        ],
        dtype=float,
    )
    if not np.all(np.isfinite(point)):
        raise FloatingPointError("full-support chart emitted a non-finite Float64 point")
    return point


def prefix_digest(points: Sequence[np.ndarray]) -> str:
    digest = hashlib.sha256(b"geotarget.exp-real61-008.source-only-prefix-f8/v1\0")
    digest.update(struct.pack("<Q", len(points)))
    for point in points:
        values = np.asarray(point, dtype="<f8")
        digest.update(struct.pack("<Q", values.size))
        digest.update(values.tobytes(order="C"))
    return digest.hexdigest()


def generate_prefix(
    lower: Sequence[float],
    upper: Sequence[float],
    *,
    count: int,
    seed: int,
) -> Prefix:
    lower_array = np.asarray(lower, dtype=float)
    upper_array = np.asarray(upper, dtype=float)
    if lower_array.ndim != 1 or upper_array.shape != lower_array.shape:
        raise ValueError("source-bound vectors have incompatible shapes")
    if np.any(np.isnan(lower_array)) or np.any(np.isnan(upper_array)):
        raise ValueError("source bounds contain NaN")
    if np.any(lower_array >= upper_array):
        raise ValueError("source bounds are not ordered")
    if count < 1:
        raise ValueError("proposal count must be positive")
    dimension = int(lower_array.size)
    if dimension == 0:
        points = tuple(np.empty(0, dtype=float) for _ in range(count))
        sources = tuple(
            "counter_product_cauchy"
            if ordinal % CAUCHY_PERIOD == 0
            else "scrambled_sobol_rational"
            for ordinal in range(count)
        )
        exponents = tuple(
            _scale_exponent(
                ordinal // CAUCHY_PERIOD
                if ordinal % CAUCHY_PERIOD == 0
                else ordinal - 1 - ordinal // CAUCHY_PERIOD
            )
            for ordinal in range(count)
        )
        return Prefix(points, sources, exponents, prefix_digest(points))
    sobol = qmc.Sobol(
        dimension,
        scramble=True,
        seed=_counter_seed(seed, 0, "sobol") & 0xFFFFFFFF,
    )
    exponent = max(0, (count - 1).bit_length())
    sobol_units = (
        _open(sobol.random_base2(exponent))
        if count > 1
        else _open(sobol.random(1))
    )
    points: list[np.ndarray] = []
    sources: list[str] = []
    exponents: list[int] = []
    cauchy_index = 0
    rational_index = 0
    for ordinal in range(count):
        if ordinal % CAUCHY_PERIOD == 0:
            generator = np.random.Generator(
                np.random.Philox(_counter_seed(seed, ordinal, "cauchy"))
            )
            units = _open(generator.random(dimension))
            scale_exponent = _scale_exponent(cauchy_index)
            cauchy_index += 1
            source = "counter_product_cauchy"
            chart = "cauchy"
        else:
            units = sobol_units[ordinal]
            scale_exponent = _scale_exponent(rational_index)
            rational_index += 1
            source = "scrambled_sobol_rational"
            chart = "rational"
        point = _map_point(
            units,
            lower_array,
            upper_array,
            exponent=scale_exponent,
            chart=chart,
        )
        points.append(point)
        sources.append(source)
        exponents.append(scale_exponent)
    for length in range(1, count + 1):
        insurance = sum(item == "counter_product_cauchy" for item in sources[:length])
        if CAUCHY_PERIOD * insurance < length:
            raise AssertionError("Cauchy insurance fell below the prefix-wide floor")
    return Prefix(
        points=tuple(points),
        sources=tuple(sources),
        scale_exponents=tuple(exponents),
        sha256=prefix_digest(points),
    )


def frozen_configuration() -> dict[str, object]:
    return {
        "schema_version": SCHEMA,
        "cauchy_period": CAUCHY_PERIOD,
        "cauchy_fraction_floor": 0.25,
        "cauchy_rng": "NumPy Philox keyed by seed and ordinal",
        "cauchy_chart": "scale*tan(pi*(u-1/2))",
        "qmc": "scrambled Sobol",
        "qmc_chart": "scale*t/(1-|t|), t=2u-1",
        "dyadic_exponents": list(DYADIC_EXPONENTS),
        "unbounded_origin": 0.0,
        "bounded_axis_mapping": "explicit source interval only",
        "proposal_coordinate_clipping": False,
        "finite_search_envelope": False,
        "case_family_truth_routing": False,
    }


__all__ = ["Prefix", "frozen_configuration", "generate_prefix", "prefix_digest"]
