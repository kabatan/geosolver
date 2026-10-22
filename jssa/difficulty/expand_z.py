"""Build offset variants: the same extra variables as expand_k, but in offset coordinates.

For each of the first k eligible constructions N = h(...), keep the construction under
the name NZC and define N = NZC + (ofsx_N, ofsy_N) with the equations ofsx_N = 0, ofsy_N = 0.
The extra variables and equations have the same count as in expand_k (2 each), but the
Jacobian is [[J_R, B], [0, I]] instead of [[A, B], [-H, I]].  With --zero-prefix ofs
(probe_basins) the offsets start at 0, i.e. at the constructed position.

Usage: python expand_z.py OUT_DIR IDS_FILE   (IDS_FILE lines: <case>.k<k>, k >= 1)
"""

from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from expand_k import ROOT, eligible  # noqa: E402


def expand_offset(dsl: dict, k: int, picks) -> dict:
    new = copy.deepcopy(dsl)
    new_vars = list(new.get("variables", []))
    cons = new["constructions"]
    inserts = []
    for i, name, _rule in picks[:k]:
        zx, zy = f"ofsx_{name}", f"ofsy_{name}"
        new_vars += [zx, zy]
        base = f"{name}ZC"
        cons[i] = {"name": base, "expression": cons[i]["expression"]}
        inserts.append((i, {"name": name, "expression":
                            f"Point(Vector(ORIGINZ, {base}).x + {zx}, Vector(ORIGINZ, {base}).y + {zy})"}))
        new["conditions"] += [{"left": zx, "operator": "=", "right": "0"},
                              {"left": zy, "operator": "=", "right": "0"}]
    for i, c in sorted(inserts, key=lambda t: -t[0]):
        cons.insert(i + 1, c)
    cons.insert(0, {"name": "ORIGINZ", "expression": "Point(0, 0)"})
    new["variables"] = new_vars
    new["id"] = f"{dsl.get('id', '')}.z{k}"
    return new


def main() -> None:
    out = Path(sys.argv[1])
    out.mkdir(parents=True, exist_ok=True)
    cases = {}
    for line in (ROOT / "benchmarks" / "cases.jsonl").open():
        c = json.loads(line)
        cases[c["id"]] = c["dsl"]
    for vid in Path(sys.argv[2]).read_text().split():
        cid, k = vid.rsplit(".k", 1)
        dsl = cases[cid]
        variant = expand_offset(dsl, int(k), eligible(dsl))
        (out / f"{cid}.z{k}.json").write_text(json.dumps(variant, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
