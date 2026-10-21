"""Isolated Linux environment for the unmodified upstream GMB (not a benchmark runner)."""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import importlib.util
import json
import math
import os
import platform
import re
import runpy
import signal
import subprocess
import sys
import sysconfig
import tempfile
import time
from contextlib import ExitStack, suppress
from pathlib import Path

ROOT = Path(__file__).resolve().parent
RUNTIME = ROOT / ".runtime"
SOURCE = RUNTIME / "source"
PYTHON = RUNTIME / "venv/bin/python"
LOCK = ROOT / "requirements.lock"
UPSTREAM = "https://github.com/rkruegs123/geo-model-builder.git"
COMMIT = "f070afe18ed874b3a31db519ea6f593f40a1be00"
PYTHON_VERSION = "3.8.20"
THREAD_VARIABLES = (
    "OMP_NUM_THREADS",
    "OPENBLAS_NUM_THREADS",
    "MKL_NUM_THREADS",
    "NUMEXPR_NUM_THREADS",
    "TF_NUM_INTRAOP_THREADS",
    "TF_NUM_INTEROP_THREADS",
    "VECLIB_MAXIMUM_THREADS",
)


def command(args, **kwargs):
    return subprocess.run(args, check=True, **kwargs)


def source_identity():
    def git(*args):
        return subprocess.check_output(["git", "-C", str(SOURCE), *args], text=True).strip()

    if git("rev-parse", "HEAD") != COMMIT:
        raise RuntimeError("GMB source is not at the pinned upstream commit")
    if git("status", "--porcelain", "--untracked-files=all"):
        raise RuntimeError("GMB source has local changes; refusing to run")
    if git("remote", "get-url", "origin") != UPSTREAM:
        raise RuntimeError("unexpected GMB origin")
    return COMMIT


def setup():
    RUNTIME.mkdir(parents=True, exist_ok=True)
    if not SOURCE.exists():
        command(["git", "init", str(SOURCE)])
        command(["git", "-C", str(SOURCE), "remote", "add", "origin", UPSTREAM])
        command(["git", "-C", str(SOURCE), "fetch", "--depth", "1", "origin", COMMIT])
        command(["git", "-C", str(SOURCE), "checkout", "--detach", "FETCH_HEAD"])
    source_identity()
    if not PYTHON.exists():
        command(
            [
                "uv",
                "venv",
                "--no-project",
                "--no-config",
                "--python",
                PYTHON_VERSION,
                str(RUNTIME / "venv"),
            ]
        )
    actual = subprocess.check_output(
        [str(PYTHON), "-c", "import platform; print(platform.python_version())"], text=True
    ).strip()
    if actual != PYTHON_VERSION:
        raise RuntimeError(f"unexpected GMB Python version: {actual}")
    command(
        [
            "uv",
            "pip",
            "sync",
            "--python",
            str(PYTHON),
            "--require-hashes",
            "--only-binary",
            ":all:",
            str(LOCK),
        ]
    )
    command(["uv", "pip", "check", "--python", str(PYTHON)])


def child_environment(directory):
    env = os.environ.copy()
    for key in ("PYTHONPATH", "PYTHONHOME"):
        env.pop(key, None)
    env.update({key: "1" for key in THREAD_VARIABLES})
    env.update(
        {
            "VIRTUAL_ENV": str(RUNTIME / "venv"),
            "PATH": str(PYTHON.parent) + os.pathsep + env.get("PATH", ""),
            "PYTHONNOUSERSITE": "1",
            "PYTHONDONTWRITEBYTECODE": "1",
            "CUDA_VISIBLE_DEVICES": "-1",
            "MPLBACKEND": "Agg",
            "MPLCONFIGDIR": str(directory / "matplotlib"),
            "TF_CPP_MIN_LOG_LEVEL": "2",
        }
    )
    return env


def choose_cpu(requested):
    allowed = os.sched_getaffinity(0)
    cpu = min(allowed) if requested is None else requested
    if cpu not in allowed:
        raise ValueError(f"CPU {cpu} is outside the current affinity")
    return cpu


def terminate_group(process):
    try:
        os.killpg(process.pid, signal.SIGTERM)
    except ProcessLookupError:
        return
    with suppress(subprocess.TimeoutExpired):
        process.wait(timeout=2)
    with suppress(ProcessLookupError):
        os.killpg(process.pid, signal.SIGKILL)
    process.wait()


def launch(mode, cpu=None, timeout=180.0, extra=()):
    source_identity()
    if not PYTHON.is_file():
        raise RuntimeError("run setup first")
    cpu = choose_cpu(cpu)
    if not math.isfinite(timeout) or timeout <= 0:
        raise ValueError("timeout must be a positive finite number")
    runs = RUNTIME / "runs"
    runs.mkdir(exist_ok=True)
    directory = Path(tempfile.mkdtemp(prefix=mode + "-", dir=runs))
    print(f"GMB run directory: {directory}", flush=True)
    args = [str(PYTHON), "-B", str(Path(__file__).resolve()), "_child", mode, str(cpu), *extra]
    started = time.monotonic()
    timed_out = False
    with ExitStack() as stack:
        stdout = stack.enter_context((directory / "stdout.log").open("w"))
        stderr = stack.enter_context((directory / "stderr.log").open("w"))
        process = subprocess.Popen(
            args,
            cwd=directory,
            env=child_environment(directory),
            stdout=stdout,
            stderr=stderr,
            start_new_session=True,
        )
        try:
            code = process.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            timed_out = True
            terminate_group(process)
            code = 124
        except BaseException:
            terminate_group(process)
            raise
    record = {
        "purpose": "environment-check-or-manual-run-not-performance-evaluation",
        "mode": mode,
        "source_commit": COMMIT,
        "python": PYTHON_VERSION,
        "requirements_sha256": hashlib.sha256(LOCK.read_bytes()).hexdigest(),
        "cpu": cpu,
        "gpu_enabled": False,
        "timeout_seconds": timeout,
        "elapsed_seconds": time.monotonic() - started,
        "timed_out": timed_out,
        "returncode": code,
        "arguments": list(extra),
    }
    (directory / "run.json").write_text(json.dumps(record, indent=2) + "\n")
    print((directory / "stdout.log").read_text(errors="replace"), end="")
    if code:
        print((directory / "stderr.log").read_text(errors="replace"), file=sys.stderr)
    print(f"exit={code}; logs and environment record: {directory}")
    return code


def doctor():
    import tensorflow as tf
    from packaging.requirements import Requirement
    from packaging.utils import canonicalize_name

    expected = {
        canonicalize_name(name): version
        for name, version in re.findall(r"^([\w.-]+)==([^\s\\]+)", LOCK.read_text(), re.M)
    }
    installed = {
        canonicalize_name(item.metadata["Name"]): item.version
        for item in importlib.metadata.distributions(path=[sysconfig.get_path("purelib")])
    }
    if installed != expected:
        raise RuntimeError(f"installed packages do not match requirements.lock: {installed}")
    for line in (SOURCE / "requirements.txt").read_text().splitlines():
        requirement = Requirement(line)
        if installed[canonicalize_name(requirement.name)] not in requirement.specifier:
            raise RuntimeError(f"upstream requirement is not satisfied: {line}")
    if importlib.util.find_spec("geosolver") is not None:
        raise RuntimeError("GeoSolver leaked into the GMB environment")
    if tf.config.get_visible_devices("GPU"):
        raise RuntimeError("GMB must run CPU-only")
    import builder
    import flask

    print(
        json.dumps(
            {
                "ok": True,
                "python": platform.python_version(),
                "prefix": sys.prefix,
                "source_commit": COMMIT,
                "builder": builder.__file__,
                "flask": flask.__version__,
                "tensorflow": tf.__version__,
                "packages": installed,
                "cpu_affinity": sorted(os.sched_getaffinity(0)),
                "visible_gpus": [],
                "geosolver_importable": False,
            },
            indent=2,
            sort_keys=True,
        )
    )


def smoke():
    from builder import build
    from util import DEFAULTS

    opts = dict(DEFAULTS, problem=str(ROOT / "smoke.smt2"), verbosity=-1, plot_freq=-1)
    models = build(opts, show_plot=False, save_plot=False, encode_fig=False)
    if len(models) != 1:
        raise RuntimeError(f"synthetic smoke produced {len(models)} models, expected 1")
    points = {str(k): (float(p.x), float(p.y)) for k, p in models[0].named_points.items()}
    if not all(math.isfinite(v) for point in points.values() for v in point):
        raise RuntimeError("non-finite smoke coordinates")

    def distance(a, b):
        return math.hypot(points[a][0] - points[b][0], points[a][1] - points[b][1])

    ab, ac, bc = distance("A", "B"), distance("A", "C"), distance("B", "C")
    a, b, c = points["A"], points["B"], points["C"]
    area2 = abs((b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0]))
    if min(ab, ac, bc) <= 0 or area2 <= 1e-10 * max(ab, ac, bc) ** 2:
        raise RuntimeError("degenerate smoke triangle")
    # Loose numerical smoke check consistent with upstream's default loss tolerance;
    # this is deliberately NOT the common validator for the future comparison.
    if abs(ab - ac) / max(ab, ac) > 0.05:
        raise RuntimeError("smoke isosceles constraint is not satisfied")
    if abs(distance("B", "M") - distance("M", "C")) > 1e-12 * bc:
        raise RuntimeError("smoke midpoint construction is incorrect")
    print(json.dumps({"ok": True, "models": 1, "points": points, "benchmark": False}, indent=2))


def child(mode, cpu, extra):
    if Path(sys.prefix).resolve() != PYTHON.parent.parent.resolve():
        raise RuntimeError("child must use the isolated GMB interpreter")
    if platform.python_version() != PYTHON_VERSION:
        raise RuntimeError("unexpected child Python")
    os.sched_setaffinity(0, {int(cpu)})
    sys.path.insert(0, str(SOURCE / "src"))
    if mode == "doctor":
        doctor()
    elif mode == "smoke":
        smoke()
    elif mode == "run":
        sys.argv = [str(SOURCE / "src/builder_cli.py"), *extra]
        runpy.run_path(sys.argv[0], run_name="__main__")
    else:
        raise ValueError(mode)
    return 0


def main():
    if sys.platform != "linux" or platform.machine() != "x86_64":
        raise RuntimeError("this pinned GMB environment supports Linux x86-64 only")
    if len(sys.argv) > 1 and sys.argv[1] == "_child":
        return child(sys.argv[2], sys.argv[3], sys.argv[4:])
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--cpu", type=int, help="one allowed logical CPU; default: first allowed CPU"
    )
    parser.add_argument("--timeout", type=float, default=180)
    commands = parser.add_subparsers(dest="mode", required=True)
    for mode in ("setup", "doctor", "smoke"):
        commands.add_parser(mode)
    run = commands.add_parser("run", help="headless upstream CLI; not a performance harness")
    run.add_argument("problem", type=Path)
    run.add_argument("options", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    if args.mode == "setup":
        setup()
        return launch("doctor", args.cpu, args.timeout)
    extra = []
    if args.mode == "run":
        if not args.problem.is_file():
            parser.error("problem file does not exist")
        options = args.options[1:] if args.options[:1] == ["--"] else args.options
        if any(
            x.split("=")[0] in {"--problem", "-p", "--dir", "-d", "--experiment"} for x in options
        ):
            parser.error("supply exactly one problem; directory/experiment modes are not supported")
        extra = ["--problem", str(args.problem.resolve()), "--plot_freq", "-1", *options]
    return launch(args.mode, args.cpu, args.timeout, extra)


if __name__ == "__main__":
    raise SystemExit(main())
