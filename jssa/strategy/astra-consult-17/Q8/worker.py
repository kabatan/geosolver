"""One bounded generation or verification job. The parent supplies DSL only."""
import argparse
import copy
import hashlib
import json
import os
from pathlib import Path
import resource
import signal
import sys
import time
import traceback

from exact_onevar import solve, Unsupported, root_from_wire, root_wire, digest
from verify_certificate import verify
import sympy as s

HERE = Path(__file__).resolve().parent


class BudgetExceeded(Exception):
    pass


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("input")
    ap.add_argument("output")
    ap.add_argument("--verify")
    args = ap.parse_args()
    inp = Path(args.input).resolve()
    output = Path(args.output).resolve()
    assert inp.is_relative_to(HERE) and output.is_relative_to(HERE)
    blocked_reads = []

    def audit(event, values):
        if event != "open" or not isinstance(values[0], (str, bytes, os.PathLike)):
            return
        path = Path(os.fsdecode(values[0])).resolve()
        # This is a provenance guard, not a security boundary.
        if any(p in path.parts for p in ("benchmarks", "difficulty", "results")) or (
            "astra-consult-17" in path.parts and not path.is_relative_to(HERE)
        ):
            blocked_reads.append(str(path))
            raise PermissionError("worker may not read references or prior outputs")

    sys.addaudithook(audit)
    data = json.loads(inp.read_text())
    assert set(data) == {"id", "dsl"}
    cert = json.loads(Path(args.verify).read_text()) if args.verify else None
    resource.setrlimit(resource.RLIMIT_AS, (2 * 1024**3, 2 * 1024**3))
    resource.setrlimit(resource.RLIMIT_FSIZE, (16 * 1024**2, 16 * 1024**2))
    stage = "start"

    def update(value):
        nonlocal stage
        stage = value

    def timeout(sig, frame):
        raise BudgetExceeded("120 second processing budget")

    signal.signal(signal.SIGALRM, timeout)
    started = time.monotonic()
    signal.setitimer(signal.ITIMER_REAL, 120)
    result = {"id": data["id"]}
    try:
        if cert is None:
            result = solve(data["dsl"], progress=update)
        else:
            update("verify_original")
            checked = verify(data["dsl"], cert)
            negatives = []
            mutations = {}
            bad = copy.deepcopy(cert)
            bad["input_sha256"] = "0" * 64
            mutations["input_hash"] = bad
            if cert["roots"]:
                bad = copy.deepcopy(cert)
                bad["roots"].pop()
                mutations["omitted_root"] = bad
            if cert["answer_set"]:
                bad = copy.deepcopy(cert)
                bad["answer_set"].pop()
                mutations["omitted_answer"] = bad
                bad = copy.deepcopy(cert)
                bad["answer_set"] = [root_wire(s.to_number_field(root_from_wire(v) + 1).to_root(radicals=False))
                                     for v in cert["answer_set"]]
                mutations["shifted_answers"] = bad
            for name, bad in mutations.items():
                update("verify_mutation:" + name)
                try:
                    verify(data["dsl"], bad)
                except ValueError as err:
                    negatives.append({"mutation": name, "detected": True, "reason": str(err)})
                else:
                    negatives.append({"mutation": name, "detected": False})
            result = {"id": data["id"], "status": "verified", "verification": checked,
                      "negative_checks": negatives,
                      "all_negative_detected": all(n["detected"] for n in negatives)}
    except BudgetExceeded as err:
        result = {"id": data["id"], "status": "timeout", "reason": str(err)}
    except Unsupported as err:
        result = {"id": data["id"], "status": "unsupported", "reason": str(err)}
    except MemoryError:
        result = {"id": data["id"], "status": "memory_limit"}
    except Exception as err:
        result = {"id": data["id"], "status": "error", "reason": repr(err),
                  "traceback": traceback.format_exc(limit=6)}
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
    result.update({"processing_seconds": time.monotonic() - started, "last_stage": stage,
                   "max_rss_kib": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
                   "blocked_reads": blocked_reads, "input_file_sha256": hashlib.sha256(inp.read_bytes()).hexdigest(),
                   "preregistration_sha256": hashlib.sha256((HERE / "preregistration.md").read_bytes()).hexdigest(),
                   "sympy_version": s.__version__})
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({k: result.get(k) for k in ("id", "status", "processing_seconds", "last_stage", "reason")},
                     ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
