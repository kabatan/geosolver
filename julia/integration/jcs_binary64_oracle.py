"""Generate/check the fixed RFC 8785 binary64 differential corpus."""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import struct
from pathlib import Path

import rfc8785

FORMAT = "geotarget-jcs-binary64-v1"
ORACLE_VERSION = "0.1.4"
SEED = 0x6A09_E667_F3BC_C909
COUNT = 10_000
MASK64 = (1 << 64) - 1


class SplitMix64:
    """Small fully specified generator; output is independent of Python's random module."""

    def __init__(self, seed: int) -> None:
        self.state = seed & MASK64

    def next(self) -> int:
        self.state = (self.state + 0x9E37_79B9_7F4A_7C15) & MASK64
        value = self.state
        value = ((value ^ (value >> 30)) * 0xBF58_476D_1CE4_E5B9) & MASK64
        value = ((value ^ (value >> 27)) * 0x94D0_49BB_1331_11EB) & MASK64
        return (value ^ (value >> 31)) & MASK64


def _float_from_bits(bits: int) -> float:
    return struct.unpack(">d", bits.to_bytes(8, byteorder="big"))[0]


def generate_corpus() -> bytes:
    installed = importlib.metadata.version("rfc8785")
    if installed != ORACLE_VERSION:
        raise RuntimeError(f"expected rfc8785=={ORACLE_VERSION}, found {installed}")

    lines = [
        f"# format={FORMAT}",
        f"# oracle=rfc8785=={ORACLE_VERSION}",
        "# generator=splitmix64",
        f"# seed=0x{SEED:016x}",
        f"# finite_count={COUNT}",
    ]
    generator = SplitMix64(SEED)
    accepted = 0
    while accepted < COUNT:
        bits = generator.next()
        if ((bits >> 52) & 0x7FF) == 0x7FF:
            continue
        canonical = rfc8785.dumps(_float_from_bits(bits)).decode("ascii")
        lines.append(f"{bits:016x}\t{canonical}")
        accepted += 1
    return ("\n".join(lines) + "\n").encode("ascii")


def main() -> int:
    parser = argparse.ArgumentParser()
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--write", type=Path)
    action.add_argument("--check", type=Path)
    args = parser.parse_args()

    corpus = generate_corpus()
    digest = hashlib.sha256(corpus).hexdigest()
    if args.write is not None:
        args.write.parent.mkdir(parents=True, exist_ok=True)
        args.write.write_bytes(corpus)
    else:
        stored = args.check.read_bytes()
        if stored != corpus:
            actual = hashlib.sha256(stored).hexdigest()
            raise SystemExit(f"corpus mismatch: stored={actual}, oracle={digest}")
    print(f"sha256:{digest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
