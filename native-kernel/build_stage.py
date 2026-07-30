#!/usr/bin/env python3
"""Build the PyO3 arm into immutable external staging with a hash sidecar."""

from __future__ import annotations

import argparse
import hashlib
import os
import subprocess
import tempfile
import zipfile
from collections.abc import Sequence
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPOSITORY = HERE.parent


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while block := handle.read(1024 * 1024):
            digest.update(block)
    return digest.hexdigest()


def build(output: Path) -> tuple[Path, Path]:
    output = output.expanduser().resolve()
    if output.exists():
        raise ValueError(f"refusing existing staging directory: {output}")
    if output == REPOSITORY or REPOSITORY in output.parents:
        raise ValueError("native staging must be outside the repository")
    output.mkdir(parents=True)
    subprocess.run(
        [
            "maturin",
            "build",
            "--release",
            "--locked",
            "--manifest-path",
            str(HERE / "Cargo.toml"),
            "--out",
            str(output),
        ],
        cwd=REPOSITORY,
        check=True,
    )
    wheels = tuple(output.glob("*.whl"))
    if len(wheels) != 1:
        raise RuntimeError("maturin did not produce exactly one wheel")
    with tempfile.TemporaryDirectory(prefix="geotarget-native-stage-") as temporary:
        unpacked = Path(temporary)
        with zipfile.ZipFile(wheels[0]) as archive:
            archive.extractall(unpacked)
        extensions = tuple((unpacked / "geotarget").glob("_native_kernel*.so"))
        if len(extensions) != 1:
            raise RuntimeError("wheel does not contain exactly one native extension")
        destination = output / extensions[0].name
        destination.write_bytes(extensions[0].read_bytes())
        os.chmod(destination, 0o755)
    sidecar = destination.with_name(destination.name + ".sha256")
    sidecar.write_text(_sha256(destination) + "\n", encoding="ascii")
    return destination, sidecar


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    arguments = parser.parse_args(argv)
    extension, sidecar = build(arguments.output)
    print(extension)
    print(sidecar)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
