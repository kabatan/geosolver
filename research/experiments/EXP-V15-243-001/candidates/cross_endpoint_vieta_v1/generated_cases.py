#!/usr/bin/env python3
"""Generated, truth-local fixtures for cross-endpoint Vieta D0."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, localcontext
from hashlib import sha256
from typing import Iterable

from candidate import EndpointObservation, HPRung, PolynomialProposal


SOURCE_BYTES = b'{"task":"solve","variables":{"names":["x","y"]},"answer":"x"}'
SOURCE_SHA256 = sha256(SOURCE_BYTES).hexdigest()


@dataclass(frozen=True)
class Family:
    degree: int
    radicands: tuple[int, ...]
    rational_roots: tuple[int, ...]
    expected_coefficients: tuple[int, ...]


FAMILIES = (
    Family(2, (2,), (), (1, 0, -2)),
    Family(3, (2,), (3,), (1, -3, -2, 6)),
    Family(4, (2, 3), (), (1, 0, -5, 0, 6)),
    Family(5, (2, 3), (5,), (1, -5, -5, 25, 6, -30)),
    Family(6, (2, 3, 5), (), (1, 0, -10, 0, 31, 0, -30)),
)


def _sha(label: str) -> str:
    return sha256(label.encode()).hexdigest()


def _format(value: Decimal, digits: int) -> str:
    with localcontext() as context:
        context.prec = digits
        return format(+value, "f")


def roots(family: Family, digits: int) -> list[Decimal]:
    with localcontext() as context:
        context.prec = digits
        values: list[Decimal] = []
        for radicand in family.radicands:
            root = Decimal(radicand).sqrt()
            values.extend((-root, root))
        values.extend(Decimal(value) for value in family.rational_roots)
        return sorted(values)


def endpoint_set(
    family: Family,
    *,
    source_sha256: str = SOURCE_SHA256,
    reverse: bool = False,
) -> tuple[EndpointObservation, ...]:
    low_values = roots(family, 88)
    high_values = roots(family, 132)
    observations: list[EndpointObservation] = []
    for index, (low, high) in enumerate(zip(low_values, high_values)):
        with localcontext() as context:
            context.prec = 132
            low_square = low * low
            high_square = high * high
        observations.append(
            EndpointObservation(
                source_sha256=source_sha256,
                low=HPRung(
                    precision_bits=256,
                    provenance_sha256=_sha(f"low-{family.degree}-{index}"),
                    target_decimal=_format(low, 78),
                    full_tuple_decimal=(_format(low, 78), _format(low_square, 78)),
                ),
                high=HPRung(
                    precision_bits=384,
                    provenance_sha256=_sha(f"high-{family.degree}-{index}"),
                    target_decimal=_format(high, 118),
                    full_tuple_decimal=(_format(high, 118), _format(high_square, 118)),
                ),
                opaque_tag=f"generated-{family.degree}-{index}",
            )
        )
    if reverse:
        observations.reverse()
    return tuple(observations)


class GeneratedReplay:
    """Synthetic stand-in with the same all-or-nothing callback boundary."""

    def __init__(
        self,
        *,
        expected_coefficients: tuple[int, ...],
        expected_endpoint_ids: Iterable[int],
        expected_source_sha256: str = SOURCE_SHA256,
        reject_tag: str | None = None,
    ) -> None:
        self.expected_coefficients = expected_coefficients
        self.expected_endpoint_ids = set(expected_endpoint_ids)
        self.expected_source_sha256 = expected_source_sha256
        self.reject_tag = reject_tag
        self.seen_ids: list[int] = []

    def __call__(
        self,
        endpoint: EndpointObservation,
        proposal: PolynomialProposal,
        root_ordinal: int,
    ) -> bool:
        self.seen_ids.append(id(endpoint))
        return (
            id(endpoint) in self.expected_endpoint_ids
            and endpoint.source_sha256 == self.expected_source_sha256
            and proposal.coefficients == self.expected_coefficients
            and proposal.completeness_claimed is False
            and root_ordinal in range(proposal.degree)
            and endpoint.opaque_tag != self.reject_tag
        )
