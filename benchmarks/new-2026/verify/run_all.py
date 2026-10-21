# ruff: noqa: E501, SIM115
"""Run check_dsl.py on every 2026 case with per-case sampling boxes."""
import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
U = (0, 1)
BOXES = {
    "HMMT-2026-FEB-GEO-01": {"tw": U, "tx": U, "yx": (0, 12), "yy": (0, 12), "zx": (0, 12), "zy": (0, 12)},
    "HMMT-2026-FEB-GEO-02": {"rx": (-10, 60), "ry": (0, 60), "sx": (-10, 60), "sy": (0, 60), "ex": (-10, 60), "ey": (0, 60)},
    "HMMT-2026-FEB-GEO-03": {"tw": U, "tx": U, "ty": U, "tz": U},
    "HMMT-2026-FEB-GEO-04": {"ax": (0, 12), "ay": (0, 8), "t": U},
    "HMMT-2026-FEB-GEO-05": {"x2": (-9, 9), "y2": (-9, 9), "x3": (-9, 9), "y3": (-9, 9),
                             "a1": U, "b1": U, "a2": U, "b2": U, "a3": U, "b3": U},
    "HMMT-2026-FEB-GEO-06": {"ax": (-15, 15), "ay": (0, 15), "p": U, "q": U},
    "HMMT-2026-FEB-GEO-07": {"cx": (-1, 1), "cy": (0, 1), "s1": U, "u1": U, "s2": U, "u2": U},
    "HMMT-2026-FEB-GEO-08": {"ax": (-10, 17), "ay": (0, 20)},
    "HMMT-2026-FEB-GEO-09": {"a": (2, 12), "ax": (-5, 5), "ay": (0, 5), "zx": (-10, 15), "zy": (-10, 15), "rho": (0, 5)},
    "HMMT-2026-FEB-GEO-10": {"a": (2, 24), "ax": (-11, 11), "ay": (0, 11)},
    "HMMT-2026-FEB-GUTS-03": {"t": U},
    "HMMT-2026-FEB-GUTS-05": {"c": (5, 30), "t": U},
    "HMMT-2026-FEB-GUTS-09": {"w": (0, 8), "h": (0, 8)},
    "HMMT-2026-FEB-GUTS-16": {"b": (0, 10), "ax": (-10, 10), "ay": (0, 10)},
    "HMMT-2026-FEB-GUTS-18": {"b": (0, 40), "cx": (-20, 60), "dx": (-20, 60), "h": (0, 30)},
    "HMMT-2026-FEB-GUTS-28": {"px": (-10, 40), "py": (-10, 40)},
    "HMMT-2026-FEB-GUTS-30": {"ax": (-10, 70), "ay": (0, 70)},
    "JMO-2026-PRE-03": {"R": (0.5, 15), "tb": U, "tc": U, "td": U, "te": U},
    "JMO-2026-PRE-06": {"b": (0, 15), "dx": (-15, 15), "dy": (0, 15), "e": U},
    "JMO-2026-PRE-09": {"ax": (0, 21), "ay": (0, 40), "d": U, "e": U, "f": U},
}

only = [a for a in sys.argv[1:2] if a]
starts = sys.argv[2] if len(sys.argv) > 2 else "300"
seed = sys.argv[3] if len(sys.argv) > 3 else "0"
for line in open(ROOT / "cases.jsonl", encoding="utf-8"):
    row = json.loads(line)
    if only and row["id"] != only[0]:
        continue
    cmd = [sys.executable, str(HERE / "check_dsl.py"), str(ROOT / row["dsl_path"]), "--starts", starts, "--seed", seed]
    for a in row["answer"]:
        cmd += ["--answer", a]
    for name, (lo, hi) in BOXES[row["id"]].items():
        cmd += ["--var", name, str(lo), str(hi)]
    out = subprocess.run(cmd, capture_output=True, text=True)
    print(out.stdout + out.stderr[-1500:], flush=True)
