from __future__ import annotations
import hashlib
import json
from pathlib import Path
import sys
from datetime import datetime, timezone

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
PYTHON = "/home/kabatan/work/solver/.venv/bin/python"
sys.dont_write_bytecode = True
sys.path[:0] = [str(ROOT), str(ROOT / "src"), str(HERE / "hook")]

def now():
    return datetime.now(timezone.utc).isoformat()

def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def dump(path, value):
    path = Path(path)
    path.resolve().relative_to(HERE)
    content = json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
    if len(content.encode()) > 20_000_000:
        raise RuntimeError("20 MB artifact limit")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".writing")
    temporary.write_text(content, encoding="utf-8")
    temporary.replace(path)

def read(path):
    return json.loads(Path(path).read_text())

def verify_lock():
    from benchmarks import research_runner as research
    from geosolver.runtime.integrity import verify_engine_lock
    lock = read(HERE / "execution-lock.json")
    for name, digest in lock["files"].items():
        if sha(ROOT / name) != digest:
            raise RuntimeError(f"registered file changed: {name}")
    valid, actual = verify_engine_lock()
    if not valid or actual != lock["runtime"]["source_hash"]:
        raise RuntimeError(f"source lock mismatch: {actual}")
    if research.runtime_fingerprint()["issues"]:
        raise RuntimeError("runtime dependency mismatch")
    return lock

def audit_summary(path, raw=None):
    embedded = ((raw or {}).get("solver_result") or {}).get("diagnostics", {}).get("q13_role_audit")
    if embedded is not None:
        return dict(embedded, separate_log_present=Path(path).exists())
    events, malformed = [], 0
    if Path(path).is_file():
        for line in Path(path).read_text().splitlines():
            try:
                events.append(json.loads(line))
            except json.JSONDecodeError:
                malformed += 1
    installed = [e for e in events if e["event"] == "installed"]
    counts = events[-1].get("counts", {}) if events else {}
    identity_ok = all(e.get("final_evaluator_unchanged", True) for e in events)
    return dict(installed=len(installed), verified=len(installed) == 1 and not malformed and identity_ok,
                final_evaluator_unchanged=identity_ok, malformed=malformed, counts=counts,
                exited=any(e["event"] == "exit" for e in events),
                condition=installed[0]["condition"] if installed else None)
