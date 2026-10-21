"""Bounded OS-isolated numeric execution and deterministic program extraction.

The Python import policy is convenience hardening. The actual isolation boundary
is bubblewrap namespaces, minimal read-only mounts, seccomp and process limits.
Only program text and one givens object enter a candidate process; answers do not.
"""
from __future__ import annotations

import argparse
import ast
import dataclasses
import hashlib
import json
import math
import os
from pathlib import Path
import platform
import re
import resource
import selectors
import shutil
import signal
import struct
import subprocess
import sys
import sysconfig
import tempfile
import time

ALLOWED_MODULES = ("math", "statistics", "fractions", "decimal", "cmath", "itertools", "functools")
FORBIDDEN_REFLECTION = {"eval", "exec", "compile", "getattr", "setattr", "delattr", "hasattr", "globals", "locals", "vars", "mro"}
EXTRACTION_RULE = "last parse-valid closed python/py/unlabelled fence with top-level synchronous solve(givens); preserve whole fence; last solve definition wins"


def digest_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def json_hash(value) -> str:
    return digest_bytes(json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode())


def validate_program(code: str) -> ast.Module:
    if len(code.encode()) > 131072:
        raise ValueError("program exceeds 128 KiB")
    tree = ast.parse(code)
    functions = [x for x in tree.body if isinstance(x, (ast.FunctionDef, ast.AsyncFunctionDef)) and x.name == "solve"]
    if not functions or isinstance(functions[-1], ast.AsyncFunctionDef):
        raise ValueError("a top-level synchronous solve(givens) definition is required")
    args = functions[-1].args
    if len(args.posonlyargs + args.args) != 1 or (args.posonlyargs + args.args)[0].arg != "givens" or args.vararg or args.kwarg or args.kwonlyargs:
        raise ValueError("solve must have exactly one positional parameter named givens")
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name not in ALLOWED_MODULES:
                    raise ValueError(f"module not allowed: {alias.name}")
        if isinstance(node, ast.ImportFrom) and (node.level or node.module not in ALLOWED_MODULES):
            raise ValueError(f"module not allowed: {node.module}")
        values = []
        if isinstance(node, ast.Name):
            values.append(node.id)
        if isinstance(node, ast.Attribute):
            values.append(node.attr)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            values.append(node.name)
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            values.append(node.value)
        if any(v.startswith("__") and v.endswith("__") for v in values):
            raise ValueError("semantic dunder use is not accepted")
        if isinstance(node, (ast.Name, ast.Attribute)) and any(v in FORBIDDEN_REFLECTION for v in values):
            raise ValueError("eval/exec/dynamic reflection is not accepted")
    compile(tree, "<candidate>", "exec")
    return tree


def extract_program(answer: str, finish_reason: str) -> dict:
    if finish_reason != "stop":
        raise ValueError(f"generation is not a completed answer: {finish_reason!r}")
    raw_answer_hash = digest_bytes(answer.encode())
    eos = re.search(r"<\|im_end\|>\s*$", answer)
    if eos:
        answer = answer[:eos.start()].rstrip() + "\n"
    fences = list(re.finditer(r"^```(?:python|py)?[ \t]*\n(.*?)^```[ \t]*$", answer, re.M | re.S))
    skipped = []
    for index in range(len(fences) - 1, -1, -1):
        code = fences[index].group(1).strip() + "\n"
        try:
            tree = validate_program(code)
        except (SyntaxError, ValueError) as exc:
            skipped.append({"fence_index": index, "error": str(exc)})
            continue
        normalized = normalize_program(code)
        return {"status": "extracted", "code": code, "code_sha256": digest_bytes(code.encode()),
                "normalized_code": normalized, "normalized_sha256": digest_bytes(normalized.encode()),
                "answer_sha256": raw_answer_hash, "stripped_one_trailing_assistant_eos": bool(eos), "finish_reason": finish_reason,
                "extraction_rule": EXTRACTION_RULE, "selected_fence_index": index,
                "closed_program_fences": len(fences), "skipped_later_fences": skipped,
                "solve_definitions": sum(isinstance(n, ast.FunctionDef) and n.name == "solve" for n in tree.body)}
    raise ValueError(f"no complete valid fenced solve(givens) program; rejected fences: {skipped}")


def normalize_program(code: str) -> str:
    tree = validate_program(code)
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            if node.body and isinstance(node.body[0], ast.Expr) and isinstance(node.body[0].value, ast.Constant) and isinstance(node.body[0].value.value, str):
                node.body.pop(0)
                if not node.body:
                    node.body.append(ast.Pass())
    normalized = ast.unparse(ast.fix_missing_locations(tree)) + "\n"
    validate_program(normalized)
    return normalized


@dataclasses.dataclass(frozen=True)
class Limits:
    wall_seconds: float = 2.0
    cpu_seconds: int = 1
    memory_bytes: int = 256 * 1024**2
    output_bytes: int = 16384
    tmp_bytes: int = 16 * 1024**2
    input_bytes: int = 196608


def seccomp_filter() -> bytes:
    if platform.machine() != "x86_64":
        raise RuntimeError("seccomp syscall table audited only for x86_64")
    # classic BPF: fail closed on wrong architecture or x32 ABI. Block child
    # processes/threads and namespace changes. Network is separately unshared.
    statements = [(0x20, 0, 0, 4), (0x15, 1, 0, 0xC000003E), (0x06, 0, 0, 0x80000000),
                  (0x20, 0, 0, 0), (0x35, 0, 1, 0x40000000), (0x06, 0, 0, 0x80000000)]
    for number in (56, 57, 58, 101, 165, 166, 272, 298, 308, 321, 435):
        statements.extend([(0x15, 0, 1, number), (0x06, 0, 0, 0x00050001)])
    statements.append((0x06, 0, 0, 0x7FFF0000))
    return b"".join(struct.pack("HBBI", *row) for row in statements)


def sandbox_command(seccomp_fd: int, limits: Limits, python_args: list[str]) -> list[str]:
    if not shutil.which("bwrap"):
        raise RuntimeError("bubblewrap unavailable; refusing unisolated execution")
    stdlib = Path(sysconfig.get_paths()["stdlib"])
    # Use only the system interpreter, not an environment containing models or
    # experiment data. This runtime has no site-packages or repo import path.
    if not str(stdlib).startswith("/usr/lib/python") or Path(sys.executable).resolve().parent != Path("/usr/bin"):
        raise RuntimeError("launch harness using /usr/bin/python3")
    command = ["bwrap", "--unshare-all", "--unshare-user", "--disable-userns", "--assert-userns-disabled",
               "--die-with-parent", "--new-session", "--cap-drop", "ALL", "--clearenv",
               "--setenv", "PATH", "/usr/bin", "--setenv", "LANG", "C.UTF-8",
               "--dir", "/usr", "--dir", "/usr/bin", "--dir", "/usr/lib",
               "--ro-bind", str(Path(sys.executable).resolve()), "/usr/bin/python3",
               "--ro-bind", str(stdlib), str(stdlib),
               "--ro-bind", "/usr/lib/x86_64-linux-gnu", "/usr/lib/x86_64-linux-gnu",
               "--symlink", "/usr/lib", "/lib", "--dir", "/lib64",
               "--ro-bind", "/lib64/ld-linux-x86-64.so.2", "/lib64/ld-linux-x86-64.so.2",
               "--proc", "/proc", "--dev", "/dev", "--size", str(limits.tmp_bytes),
               "--tmpfs", "/tmp", "--chdir", "/tmp", "--seccomp", str(seccomp_fd),
               "/usr/bin/python3", "-I", "-S", "-B", *python_args]
    return command


def _resource_limits(limits: Limits):
    resource.setrlimit(resource.RLIMIT_CPU, (limits.cpu_seconds, limits.cpu_seconds + 1))
    resource.setrlimit(resource.RLIMIT_AS, (limits.memory_bytes, limits.memory_bytes))
    resource.setrlimit(resource.RLIMIT_FSIZE, (limits.output_bytes, limits.output_bytes))
    resource.setrlimit(resource.RLIMIT_NOFILE, (32, 32))
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))


def run_isolated(python_args: list[str], payload: bytes, limits: Limits) -> dict:
    """Trusted runner primitive, also used by OS-boundary smoke tests."""
    if len(payload) > limits.input_bytes:
        return {"status": "input_limit", "elapsed_seconds": 0}
    started = time.monotonic()
    with os.fdopen(os.memfd_create("candidate-seccomp", flags=os.MFD_CLOEXEC), "w+b") as filt:
        filt.write(seccomp_filter()); filt.flush(); filt.seek(0)
        cmd = sandbox_command(filt.fileno(), limits, python_args)
        process = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                   pass_fds=(filt.fileno(),), close_fds=True, start_new_session=True,
                                   preexec_fn=lambda: _resource_limits(limits))
        stdout, stderr = bytearray(), bytearray()
        status = None
        selector = selectors.DefaultSelector()
        for stream, name in [(process.stdout, "stdout"), (process.stderr, "stderr")]:
            os.set_blocking(stream.fileno(), False); selector.register(stream, selectors.EVENT_READ, name)
        # Payload is small and stdin is consumed before any candidate code runs.
        # A nonblocking writer keeps wall bounds even if runtime startup fails.
        os.set_blocking(process.stdin.fileno(), False)
        selector.register(process.stdin, selectors.EVENT_WRITE, "stdin")
        offset = 0
        try:
            while selector.get_map():
                if time.monotonic() - started > limits.wall_seconds:
                    status = "wall_timeout"; break
                for key, _ in selector.select(timeout=min(0.05, limits.wall_seconds)):
                    if key.data == "stdin":
                        try:
                            offset += os.write(key.fd, payload[offset:])
                        except BrokenPipeError:
                            offset = len(payload)
                        if offset == len(payload):
                            selector.unregister(key.fileobj); key.fileobj.close()
                    else:
                        block = os.read(key.fd, 4096)
                        if not block:
                            selector.unregister(key.fileobj); key.fileobj.close(); continue
                        (stdout if key.data == "stdout" else stderr).extend(block)
                        if len(stdout) + len(stderr) > limits.output_bytes:
                            status = "output_limit"; break
                if status:
                    break
        finally:
            if status or process.poll() is None:
                try:
                    os.killpg(process.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
            process.wait(timeout=1)
            selector.close()
            for stream in [process.stdin, process.stdout, process.stderr]:
                if not stream.closed:
                    stream.close()
        return {"status": status or ("process_ok" if process.returncode == 0 else "cpu_timeout" if process.returncode in (-signal.SIGXCPU,128+signal.SIGXCPU) else "process_error"),
                "returncode": process.returncode, "stdout": bytes(stdout[:limits.output_bytes]).decode(errors="replace"),
                "stderr": bytes(stderr[:limits.output_bytes]).decode(errors="replace"),
                "elapsed_seconds": time.monotonic() - started}


BOOTSTRAP = r'''
import builtins, contextlib, json, math, numbers, sys
import math, statistics, fractions, decimal, cmath, itertools, functools
payload = json.load(sys.stdin)
allowed = {"math", "statistics", "fractions", "decimal", "cmath", "itertools", "functools"}
original_import = builtins.__import__
def limited_import(name, globals=None, locals=None, fromlist=(), level=0):
    if level or name not in allowed:
        raise ImportError("candidate module not allowed: " + name)
    return original_import(name, globals, locals, fromlist, level)
candidate_builtins = dict(vars(builtins))
candidate_builtins["__import__"] = limited_import
namespace = {"__builtins__": candidate_builtins}
try:
    with contextlib.redirect_stdout(sys.stderr):
        exec(compile(payload["program"], "<candidate>", "exec"), namespace)
        value = namespace["solve"](payload["givens"])
    if isinstance(value, bool) or not isinstance(value, (numbers.Real, decimal.Decimal)):
        raise ValueError("solve must return one scalar real number (not bool, string, sequence or complex)")
    value = float(value)
    if not math.isfinite(value):
        raise ValueError("solve returned a nonfinite number")
    print(json.dumps({"status": "ok", "value": value}, allow_nan=False))
except BaseException as exc:
    print(json.dumps({"status": "runtime_error", "error_type": type(exc).__name__, "error": str(exc)[:2000]}))
'''


def execute_program(code: str, givens: dict, limits: Limits = Limits()) -> dict:
    try:
        validate_program(code)
        if not isinstance(givens, dict):
            raise ValueError("givens must be a JSON object")
        if any(type(v) not in (int,float) or not math.isfinite(v) for v in givens.values()):
            raise ValueError("givens values must be finite scalar JSON numbers")
        payload = json.dumps({"program": code, "givens": givens}, allow_nan=False).encode()
    except (ValueError, SyntaxError, TypeError, OverflowError) as exc:
        return {"status": "invalid_program_or_input", "error": str(exc)}
    result = run_isolated(["-c", BOOTSTRAP], payload, limits)
    if result["status"] != "process_ok":
        return result
    try:
        reply = json.loads(result["stdout"])
        if not isinstance(reply, dict) or reply.get("status") not in {"ok", "runtime_error"}:
            raise ValueError("invalid runner reply")
        if reply["status"] == "ok" and (type(reply.get("value")) not in (int, float) or not math.isfinite(reply["value"])):
            raise ValueError("invalid scalar reply")
    except (json.JSONDecodeError, ValueError) as exc:
        result.update(status="invalid_output", error=str(exc)); return result
    result.update(reply)
    return result


def evaluate_candidate(code: str, cases: list[dict], limits: Limits = Limits(), abs_tol: float = 1e-7, rel_tol: float = 1e-6) -> dict:
    if abs_tol < 0 or rel_tol < 0:
        raise ValueError("tolerances must be nonnegative")
    identifiers = [case["case_id"] for case in cases]
    if len(identifiers) != len(set(identifiers)):
        raise ValueError("duplicate case IDs")
    events = []
    for case in cases:
        answer = case["answer"]
        if isinstance(answer, bool) or not isinstance(answer, (int, float)) or not math.isfinite(answer):
            raise ValueError("oracle answer must be finite real JSON numeric value")
        result = execute_program(code, case["givens"], limits)
        value = result.get("value")
        error = abs(value - answer) if result["status"] == "ok" else None
        overflowed_error = error is not None and not math.isfinite(error)
        if overflowed_error:
            error = None
        threshold = abs_tol + rel_tol * abs(answer)
        events.append({"case_id": case["case_id"], "source_id": case["source_id"], "split": case["split"],
                       "givens_sha256": json_hash(case["givens"]), "answer": answer, "execution": result,
                       "absolute_error": error, "absolute_error_overflowed": overflowed_error,
                       "tolerance": threshold, "passed": error is not None and error <= threshold})
    return {"status": "complete", "code_sha256": digest_bytes(code.encode()), "cases_sha256": json_hash(cases),
            "limits": dataclasses.asdict(limits), "abs_tol": abs_tol, "rel_tol": rel_tol,
            "isolation": "bwrap user/PID/network/mount namespaces; minimal readonly system Python; no host data; seccomp forbids fork/clone and namespace changes",
            "seccomp_sha256": digest_bytes(seccomp_filter()), "bootstrap_sha256": digest_bytes(BOOTSTRAP.encode()),
            "n_cases": len(cases), "n_passed": sum(x["passed"] for x in events),
            "all_passed": bool(cases) and all(x["passed"] for x in events), "events": events}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    extract = sub.add_parser("extract"); extract.add_argument("--input", type=Path, required=True); extract.add_argument("--out", type=Path, required=True)
    check = sub.add_parser("check"); check.add_argument("--candidate", type=Path, required=True); check.add_argument("--cases", type=Path, required=True); check.add_argument("--out", type=Path, required=True)
    check.add_argument("--normalize", action="store_true")
    args = parser.parse_args()
    if args.out.exists():
        raise FileExistsError(args.out)
    if args.command == "extract":
        row = json.loads(args.input.read_text()); answer = row['final_text'] if 'final_text' in row else row['answer']
        result = extract_program(answer, row["finish_reason"])
        result["input_sha256"] = digest_bytes(args.input.read_bytes())
    else:
        row = json.loads(args.candidate.read_text()); raw = row["code"]
        code = normalize_program(raw) if args.normalize else raw
        case_text = args.cases.read_text()
        try:
            cases = json.loads(case_text)
        except json.JSONDecodeError:
            cases = [json.loads(line) for line in case_text.splitlines() if line.strip()]
        result = evaluate_candidate(code, cases)
        result.update(candidate_file_sha256=digest_bytes(args.candidate.read_bytes()), raw_code_sha256=digest_bytes(raw.encode()), normalized=args.normalize)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False) + "\n")
    print(json.dumps({k: v for k, v in result.items() if k not in {"code", "normalized_code", "events"}}, ensure_ascii=False))


if __name__ == "__main__":
    main()
