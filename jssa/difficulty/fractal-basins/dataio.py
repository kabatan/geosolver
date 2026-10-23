"""Read exact JSON evidence, whether plain or losslessly gzip-compressed."""
import gzip
import json
from pathlib import Path


def exists(path):
    path=Path(path)
    return path.exists() or Path(str(path)+'.gz').exists()


def read(path):
    path=Path(path)
    if path.exists():
        return json.loads(path.read_text())
    return json.loads(gzip.decompress(Path(str(path)+'.gz').read_bytes()))


def paths(folder,pattern='*.json'):
    folder=Path(folder)
    plain=set(folder.glob(pattern))
    plain.update(Path(str(p)[:-3]) for p in folder.glob(pattern+'.gz'))
    return sorted(plain)
