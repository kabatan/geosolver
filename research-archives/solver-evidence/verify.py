"""Verify the compact archive without importing or running GeoSolver."""

import hashlib
import json
from pathlib import Path
import tarfile

ROOT = Path(__file__).resolve().parent


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    manifest = json.loads((ROOT / "import-manifest.json").read_text(encoding="utf-8"))
    checks = {entry["path"]: entry["sha256"] for entry in manifest["files"]}
    checks.update(manifest["publication_files"])
    for relative, expected in checks.items():
        path = (ROOT / relative).resolve()
        if not path.is_relative_to(ROOT) or not path.is_file() or sha256(path) != expected:
            raise ValueError(f"missing or changed archive file: {relative}")

    snapshots = ROOT / manifest["source_snapshots"]
    index = json.loads(snapshots.read_text(encoding="utf-8"))
    archive_path = snapshots.parent / index["archive"]
    if sha256(archive_path) != index["sha256"]:
        raise ValueError("source snapshot archive hash mismatch")
    with tarfile.open(archive_path) as archive:
        for entry in index["files"]:
            stream = archive.extractfile(entry["path"])
            if stream is None or hashlib.sha256(stream.read()).hexdigest() != entry["sha256"]:
                raise ValueError(f"source snapshot mismatch: {entry['path']}")
    print(json.dumps({"valid": True, "files": len(checks), "source_files": len(index["files"])}))


if __name__ == "__main__":
    main()
