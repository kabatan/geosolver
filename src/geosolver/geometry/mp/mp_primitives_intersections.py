"""Intersection helpers extracted from mp_primitives."""

from __future__ import annotations

from contextlib import contextmanager
import contextvars
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Optional, Union

from mpmath import mp, mpf, sqrt as mp_sqrt

if TYPE_CHECKING:
    from geosolver.geometry.mp.mp_impl import MPArc, MPCircle, MPLine, MPPoint


INTERSECTION_TOLERANCE_DPS_RATIO = mpf("0.8")


@dataclass(frozen=True)
class SelectorBranchEntry:
    branch_index: int
    margin: mpf
    kind: str


@dataclass
class SelectorTrace:
    entries: list[SelectorBranchEntry] = field(default_factory=list)
    min_margin: mpf = mp.inf

    @property
    def has_entries(self) -> bool:
        return bool(self.entries)

    def record(self, *, branch_index: int, margin: mpf, kind: str) -> None:
        entry = SelectorBranchEntry(
            branch_index=int(branch_index),
            margin=margin,
            kind=str(kind),
        )
        self.entries.append(entry)
        if mp.isfinite(entry.margin):
            self.min_margin = min(self.min_margin, entry.margin)


_SELECTOR_TRACE: contextvars.ContextVar[SelectorTrace | None] = contextvars.ContextVar(
    "_SELECTOR_TRACE",
    default=None,
)
_FROZEN_SELECTOR_ENTRIES: contextvars.ContextVar[tuple[SelectorBranchEntry, ...] | None] = (
    contextvars.ContextVar("_FROZEN_SELECTOR_ENTRIES", default=None)
)
_SELECTOR_CALL_INDEX: contextvars.ContextVar[int] = contextvars.ContextVar(
    "_SELECTOR_CALL_INDEX",
    default=0,
)


def _intersection_tolerance(scale: mpf = mpf("1")) -> mpf:
    exponent = -mp.mpf(mp.dps) * INTERSECTION_TOLERANCE_DPS_RATIO
    return mp.power(mpf(10), exponent) * scale


def _selector_scale(candidates: list["MPPoint"], reference: "MPPoint" | None = None) -> mpf:
    scale = mpf("1")
    for point in candidates:
        scale = max(scale, abs(point.x), abs(point.y))
    if reference is not None:
        scale = max(scale, abs(reference.x), abs(reference.y))
    return scale


def _selector_margin(value: mpf) -> mpf:
    if mp.isfinite(value):
        return abs(value)
    return mp.inf


def _record_selector_branch(branch_index: int, margin: mpf, kind: str) -> None:
    trace = _SELECTOR_TRACE.get()
    if trace is None:
        return
    trace.record(branch_index=int(branch_index), margin=_selector_margin(margin), kind=kind)


def _next_frozen_selector_entry() -> SelectorBranchEntry | None:
    frozen_entries = _FROZEN_SELECTOR_ENTRIES.get()
    if not frozen_entries:
        return None
    index = _SELECTOR_CALL_INDEX.get()
    _SELECTOR_CALL_INDEX.set(index + 1)
    if index >= len(frozen_entries):
        return None
    return frozen_entries[index]


@contextmanager
def capture_selector_trace() -> SelectorTrace:
    trace = SelectorTrace()
    token_trace = _SELECTOR_TRACE.set(trace)
    token_frozen = _FROZEN_SELECTOR_ENTRIES.set(None)
    token_index = _SELECTOR_CALL_INDEX.set(0)
    try:
        yield trace
    finally:
        _SELECTOR_CALL_INDEX.reset(token_index)
        _FROZEN_SELECTOR_ENTRIES.reset(token_frozen)
        _SELECTOR_TRACE.reset(token_trace)


@contextmanager
def freeze_selector_trace(entries: list[SelectorBranchEntry] | tuple[SelectorBranchEntry, ...]) -> None:
    frozen = tuple(entries)
    token_trace = _SELECTOR_TRACE.set(None)
    token_frozen = _FROZEN_SELECTOR_ENTRIES.set(frozen)
    token_index = _SELECTOR_CALL_INDEX.set(0)
    try:
        yield
    finally:
        _SELECTOR_CALL_INDEX.reset(token_index)
        _FROZEN_SELECTOR_ENTRIES.reset(token_frozen)
        _SELECTOR_TRACE.reset(token_trace)


def _select_original_candidate(
    candidates: list["MPPoint"],
    *,
    exclude: Optional["MPPoint"],
    near: Optional["MPPoint"],
    far: Optional["MPPoint"],
) -> Union[list["MPPoint"], "MPPoint", None]:
    if not candidates:
        return None
    if exclude is None and near is None and far is None:
        if len(candidates) == 1:
            return candidates[0]
        return candidates

    frozen_entry = _next_frozen_selector_entry()
    if frozen_entry is not None and 0 <= int(frozen_entry.branch_index) < len(candidates):
        return candidates[int(frozen_entry.branch_index)]

    active: list[tuple[int, "MPPoint"]] = list(enumerate(candidates))
    margin = mp.inf
    selector_kind = "exclude" if exclude is not None else ("near" if near is not None else "far")

    if exclude is not None:
        tolerance = _intersection_tolerance(_selector_scale(candidates, exclude))
        distances = [point.distance_to(exclude) for _, point in active]
        matched = [
            distance
            for distance in distances
            if distance <= tolerance
        ]
        survivor_distances = [
            distance
            for distance in distances
            if distance > tolerance
        ]
        if len(matched) == 1 and survivor_distances:
            # The selector decision is separated by the geometric gap between
            # the uniquely excluded root and its nearest survivor.  The old
            # distance-to-tolerance margin shrank as precision increased and
            # therefore made every valid exact exclusion look unstable.
            exclusion_gap = min(survivor_distances) - matched[0]
            margin = min(margin, _selector_margin(exclusion_gap))
        else:
            # No unique excluded root (or no survivor) is not a validated
            # selector decision.  Preserve the existing selection behavior,
            # where possible, but make high-precision authority fail closed.
            margin = mpf("0")
        active = [
            (index, point)
            for (index, point), distance in zip(active, distances)
            if distance > tolerance
        ]
        if not active:
            return None

    if near is not None or far is not None:
        reference = near if near is not None else far
        assert reference is not None
        scored = [
            (point.distance_to(reference), index, point)
            for index, point in active
        ]
        scored.sort(
            key=lambda item: (item[0], item[1]),
            reverse=bool(far is not None),
        )
        if len(scored) > 1:
            margin = min(margin, _selector_margin(scored[1][0] - scored[0][0]))
        chosen_index = int(scored[0][1])
        _record_selector_branch(chosen_index, margin, selector_kind)
        return candidates[chosen_index]

    if exclude is not None and len(active) > 1:
        # Exclusion alone does not distinguish multiple survivors.
        margin = mpf("0")
    chosen_index = int(active[0][0])
    _record_selector_branch(chosen_index, margin, selector_kind)
    return candidates[chosen_index]


def _process_intersection_selection(
    result: Union[list["MPPoint"], "MPPoint", None],
    *,
    exclude: Optional["MPPoint"],
    near: Optional["MPPoint"],
    far: Optional["MPPoint"],
) -> Union[list["MPPoint"], "MPPoint", None]:
    if result is None:
        return None
    candidates = result if isinstance(result, list) else [result]
    return _select_original_candidate(
        list(candidates),
        exclude=exclude,
        near=near,
        far=far,
    )


def mp_circle_circle_intersection(
    c1: "MPCircle",
    c2: "MPCircle",
    exclude: Optional["MPPoint"] = None,
) -> Union[list["MPPoint"], "MPPoint", None]:
    d = c1.center.distance_to(c2.center)
    r1 = c1.radius
    r2 = c2.radius
    scale = max(
        abs(c1.center.x),
        abs(c1.center.y),
        abs(c2.center.x),
        abs(c2.center.y),
        abs(r1),
        abs(r2),
        mpf(1),
    )
    tolerance = _intersection_tolerance(scale)
    if d > r1 + r2 + tolerance or d < abs(r1 - r2) - tolerance:
        return None
    if abs(d - (r1 + r2)) < tolerance or abs(d - abs(r1 - r2)) < tolerance:
        t = r1 / d if d > 0 else mpf("0.5")
        point = type(c1.center)(
            c1.center.x + t * (c2.center.x - c1.center.x),
            c1.center.y + t * (c2.center.y - c1.center.y),
        )
        if exclude is not None:
            scale_ex = max(abs(point.x), abs(point.y), abs(exclude.x), abs(exclude.y), mpf(1))
            exclude_tol = _intersection_tolerance(scale_ex)
            if point.distance_to(exclude) < exclude_tol:
                return None
        return [point]

    a = (r1**2 - r2**2 + d**2) / (2 * d)
    h_sq = r1**2 - a**2
    if h_sq < 0:
        h_sq = mpf(0)
    h = mp_sqrt(h_sq)
    px = c1.center.x + a * (c2.center.x - c1.center.x) / d
    py = c1.center.y + a * (c2.center.y - c1.center.y) / d
    dx = (c2.center.x - c1.center.x) / d
    dy = (c2.center.y - c1.center.y) / d
    p1 = type(c1.center)(px + h * (-dy), py + h * dx)
    p2 = type(c1.center)(px - h * (-dy), py - h * dx)
    if exclude is not None:
        dist1 = p1.distance_to(exclude)
        dist2 = p2.distance_to(exclude)
        return p1 if dist1 > dist2 else p2
    return [p1, p2]


def mp_line_circle_intersection(
    line: "MPLine",
    circle: "MPCircle",
    exclude: Optional["MPPoint"] = None,
) -> Union[list["MPPoint"], "MPPoint", None]:
    center = circle.center
    radius = circle.radius
    distance = line.distance_to_point(center)
    scale = max(abs(center.x), abs(center.y), abs(radius), mpf(1))
    tolerance = _intersection_tolerance(scale)
    if distance > radius + tolerance:
        return None

    t = -(line.a * center.x + line.b * center.y + line.c)
    foot_x = center.x + t * line.a
    foot_y = center.y + t * line.b
    if abs(distance - radius) < tolerance:
        point = type(center)(foot_x, foot_y)
        if exclude is not None:
            scale_ex = max(abs(point.x), abs(point.y), abs(exclude.x), abs(exclude.y), mpf(1))
            exclude_tol = _intersection_tolerance(scale_ex)
            if point.distance_to(exclude) < exclude_tol:
                return None
        return [point]

    h_sq = radius * radius - distance * distance
    if h_sq < 0:
        h_sq = mpf(0)
    h = mp_sqrt(h_sq)
    ux = line.b
    uy = -line.a
    p1 = type(center)(foot_x + h * ux, foot_y + h * uy)
    p2 = type(center)(foot_x - h * ux, foot_y - h * uy)
    if exclude is not None:
        dist1 = p1.distance_to(exclude)
        dist2 = p2.distance_to(exclude)
        return p1 if dist1 > dist2 else p2
    return [p1, p2]


def mp_intersect(
    obj1: object,
    obj2: object,
    exclude: Optional["MPPoint"] = None,
    near: Optional["MPPoint"] = None,
    far: Optional["MPPoint"] = None,
    **kwargs: object,
) -> Union[list["MPPoint"], "MPPoint", None]:
    from geosolver.geometry.mp.mp_primitives import _is_point_on_arc

    _ = kwargs
    is_arc1 = type(obj1).__name__ == "MPArc"
    is_arc2 = type(obj2).__name__ == "MPArc"
    result: Union[list["MPPoint"], "MPPoint", None] = None

    if is_arc1 or is_arc2:
        if is_arc1 and is_arc2:
            points = mp_circle_circle_intersection(obj1.circle, obj2.circle, None)
            if points:
                result = [point for point in points if _is_point_on_arc(point, obj1) and _is_point_on_arc(point, obj2)]
        elif is_arc1:
            if type(obj2).__name__ == "MPLine":
                points = mp_line_circle_intersection(obj2, obj1.circle, None)
            elif type(obj2).__name__ == "MPCircle":
                points = mp_circle_circle_intersection(obj1.circle, obj2, None)
            else:
                return None
            if points:
                result = [point for point in points if _is_point_on_arc(point, obj1)]
        else:
            if type(obj1).__name__ == "MPLine":
                points = mp_line_circle_intersection(obj1, obj2.circle, None)
            elif type(obj1).__name__ == "MPCircle":
                points = mp_circle_circle_intersection(obj1, obj2.circle, None)
            else:
                return None
            if points:
                result = [point for point in points if _is_point_on_arc(point, obj2)]
    else:
        if type(obj1).__name__ == "MPLine" and type(obj2).__name__ == "MPLine":
            from geosolver.geometry.mp.mp_impl import mp_line_line_intersection

            result = mp_line_line_intersection(obj1, obj2)
        elif type(obj1).__name__ == "MPLine" and type(obj2).__name__ == "MPCircle":
            result = mp_line_circle_intersection(obj1, obj2, None)
        elif type(obj1).__name__ == "MPCircle" and type(obj2).__name__ == "MPLine":
            result = mp_line_circle_intersection(obj2, obj1, None)
        elif type(obj1).__name__ == "MPCircle" and type(obj2).__name__ == "MPCircle":
            result = mp_circle_circle_intersection(obj1, obj2, None)
        else:
            raise TypeError(f"Unsupported types for intersection: {type(obj1)}, {type(obj2)}")

    return _process_intersection_selection(result, exclude=exclude, near=near, far=far)
