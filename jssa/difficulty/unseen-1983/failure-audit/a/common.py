"""Q29a audit helpers. Original DSL and frozen src are never modified."""
from pathlib import Path
import hashlib
import json
import os
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[4]
CORPUS = HERE.parents[1]
sys.path[:0] = [str(ROOT / "src"), str(ROOT)]
sys.dont_write_bytecode = True
sys.setrecursionlimit(10000)
os.environ["PYTHONDONTWRITEBYTECODE"] = "1"
os.environ["PYTHONPATH"] = os.pathsep.join([str(ROOT / "src"), str(ROOT)])
for name in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS"):
    os.environ[name] = "1"

IDS = ("AIME-1983-12", "AIME-1985-09", "AIME-1991-12", "AIME-1991-14", "AIME-1995-09")
EXPECTED = dict(zip(IDS, (65, 49, 677, 384, 616)))
FROZEN = "60db4b679b04167175c51c479c87c22fa663fda0"
SOURCE_HASH = "sha256:d8fd9bb8392ad2984276bab3386e033669246ee79586317917c322d31b4541f5"

def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def save(path, value):
    content = json.dumps(value, ensure_ascii=False, indent=2, default=str, allow_nan=False) + "\n"
    if len(content.encode()) >= 4_800_000:
        content = json.dumps(value, ensure_ascii=False, separators=(",", ":"), default=str, allow_nan=False) + "\n"
    if len(content.encode()) >= 4_800_000 and isinstance(value, dict) and 'solver_result' in value:
        # Keep public answers, timings, feasibility and process receipts. Large
        # duplicate candidate telemetry is not needed to score these diagnostics.
        value = dict(value)
        result = dict(value['solver_result'])
        diagnostics = dict(result.get('diagnostics') or {})
        omitted = {}
        for key in ('pipeline_summary', 'candidate_records'):
            if key in diagnostics:
                payload = json.dumps(diagnostics.pop(key), ensure_ascii=False,
                                     separators=(',', ':'), default=str).encode()
                omitted[key] = dict(bytes=len(payload), sha256=hashlib.sha256(payload).hexdigest())
        result['diagnostics'] = diagnostics
        value['solver_result'] = result
        value['large_duplicate_telemetry_not_stored'] = omitted
        content = json.dumps(value, ensure_ascii=False, indent=2, default=str, allow_nan=False) + "\n"
    assert len(content.encode()) < 4_900_000
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)

def problem(cid):
    from geosolver.problem.models import GeometryProblem
    return GeometryProblem.model_validate_json((CORPUS / "dsl" / f"{cid}.json").read_text())

def witness(cid):
    """Analytic coordinates from the statement; evaluate at caller's mp precision."""
    from mpmath import mp
    if cid == IDS[0]:
        return dict(a=mp.mpf(6), b=mp.mpf(5), h=mp.mpf(33)/2, p=mp.mpf(33), q=mp.mpf(2))
    if cid == IDS[1]:
        return dict(r=8/mp.sqrt(15), y2=7/mp.sqrt(15), y3=11/(2*mp.sqrt(15)),
                    y4=2/mp.sqrt(15), alpha=mp.acos(mp.mpf(17)/32),
                    beta=mp.acos(-mp.mpf(7)/128), m=mp.mpf(17), n=mp.mpf(32),
                    u=mp.mpf(-15), v=mp.mpf(8))
    if cid == IDS[2]:
        return dict(w=mp.mpf(192)/5, h=mp.mpf(144)/5, rx=mp.mpf(15), sy=mp.mpf(44)/5,
                    m=mp.mpf(672), n=mp.mpf(5), u=mp.mpf(-2), v=mp.mpf(269))
    if cid == IDS[3]:
        return dict(cx=mp.mpf(175)/2, cy=385/(2*mp.sqrt(11)), dx=mp.mpf(56), dy=40*mp.sqrt(11),
                    ex=mp.mpf(-25), ey=40*mp.sqrt(11), fx=-mp.mpf(113)/2, fy=385/(2*mp.sqrt(11)))
    if cid == IDS[4]:
        return dict(s=mp.mpf(11)/2, a=mp.mpf(11), b=mp.mpf(605))
    raise KeyError(cid)

def identity():
    import subprocess
    import importlib.metadata as metadata
    from geosolver.runtime.integrity import source_tree_hash, verify_engine_lock
    assert not subprocess.check_output(["git", "diff", FROZEN, "--", "src"], cwd=ROOT)
    assert source_tree_hash() == SOURCE_HASH
    assert verify_engine_lock()[0]
    return dict(frozen_commit=FROZEN, src_hash=SOURCE_HASH, src_diff_empty=True,
                python=sys.version, dependencies={k: metadata.version(k) for k in
                ("numpy", "scipy", "mpmath", "sympy", "pydantic", "PyNomadBBO")},
                input_sha256={cid: sha(CORPUS / "dsl" / f"{cid}.json") for cid in IDS},
                assessment_sha256=sha(CORPUS / "prereg/q19-scored/assessment.jsonl"))
