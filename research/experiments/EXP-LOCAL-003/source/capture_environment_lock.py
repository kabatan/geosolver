"""Capture the single machine/runtime record required before the C0 source commit."""

from __future__ import annotations

import os
import platform
import shutil
import stat
import subprocess
import sys
from pathlib import Path


SOURCE_ROOT = Path(__file__).resolve().parent
REPOSITORY_ROOT = SOURCE_ROOT.parents[3]
PYTHON_SOURCE = REPOSITORY_ROOT / "python" / "src"
_BLOCKED_ENVIRONMENT_PREFIXES = (
    "COVERAGE_",
    "COV_CORE_",
    "PYTEST_",
    "PYTHON",
    "DD_",
    "OTEL_",
    "NEW_RELIC_",
    "SENTRY_",
    "PYDEVD_",
)


def _verify_preimport_hygiene() -> None:
    if (
        sys.flags.isolated != 1
        or sys.flags.ignore_environment != 1
        or sys.flags.no_user_site != 1
        or sys.flags.safe_path is not True
        or sys.flags.dont_write_bytecode != 1
        or sys.flags.no_site != 1
        or sys.flags.optimize != 0
        or "site" in sys.modules
    ):
        raise RuntimeError("environment capture requires exact `python -I -B -S`")
    blocked = sorted(
        name
        for name in os.environ
        if name.upper().startswith(_BLOCKED_ENVIRONMENT_PREFIXES)
    )
    if blocked:
        raise RuntimeError(f"environment capture has injection environment: {blocked}")
    if any("site-packages" in value.casefold() for value in sys.path):
        raise RuntimeError("site-packages was active before environment capture")
    expected = Path(__file__).resolve(strict=True)
    main_file = getattr(sys.modules.get("__main__"), "__file__", None)
    if (
        Path(sys.argv[0]).resolve(strict=True) != expected
        or not isinstance(main_file, str)
        or Path(main_file).resolve(strict=True) != expected
        or Path.cwd().resolve(strict=True) != REPOSITORY_ROOT.resolve(strict=True)
    ):
        raise RuntimeError(
            "environment capture must execute directly at repository root"
        )
    for root in (SOURCE_ROOT, PYTHON_SOURCE):
        for current, directories, files in os.walk(root, followlinks=False):
            if "__pycache__" in directories or any(
                name.casefold().endswith((".pyc", ".pyo")) for name in files
            ):
                raise RuntimeError(f"stale project bytecode exists under {current}")


def _activate_formal_import_paths() -> None:
    executable = Path(sys.executable).resolve(strict=True)
    venv = (REPOSITORY_ROOT / "python" / ".venv").resolve(strict=True)
    if executable.parent.parent != venv or executable.name.casefold() != "python.exe":
        raise RuntimeError("environment capture is not using the fixed project venv")
    site_packages = venv / "Lib" / "site-packages"
    if not site_packages.is_dir():
        raise RuntimeError("fixed project venv site-packages is unavailable")
    for path in reversed((SOURCE_ROOT, PYTHON_SOURCE, site_packages)):
        if str(path) not in sys.path:
            sys.path.insert(0, str(path))


if __name__ == "__main__":
    _verify_preimport_hygiene()
    _activate_formal_import_paths()
else:
    for path in (PYTHON_SOURCE, SOURCE_ROOT):
        if str(path) not in sys.path:
            sys.path.insert(0, str(path))

import materialize_development as contract  # noqa: E402


def _reject_reparse_ancestry(path: Path) -> None:
    reparse = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
    for entry in (path.absolute(), *path.absolute().parents):
        try:
            metadata = entry.lstat()
        except FileNotFoundError:
            continue
        if (
            stat.S_ISLNK(metadata.st_mode)
            or getattr(metadata, "st_file_attributes", 0) & reparse
        ):
            raise contract.MaterializationError(
                f"formal capture path traverses a reparse point: {entry}"
            )


def _discovery_environment(git_path: Path) -> dict[str, str]:
    system_root = Path(os.environ.get("SystemRoot", r"C:\Windows"))
    environment = {
        "SystemRoot": str(system_root),
        "WINDIR": str(system_root),
        "COMSPEC": str(system_root / "System32" / "cmd.exe"),
        "PATH": os.pathsep.join((str(git_path.parent), str(system_root / "System32"))),
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_CONFIG_GLOBAL": os.devnull,
        "GIT_CONFIG_SYSTEM": os.devnull,
        "GIT_ATTR_NOSYSTEM": "1",
        "GIT_NO_REPLACE_OBJECTS": "1",
        "GIT_TERMINAL_PROMPT": "0",
        "LC_ALL": "C",
        "LANG": "C",
    }
    for name in ("TEMP", "TMP"):
        if value := os.environ.get(name):
            environment[name] = value
    return environment


def _git_read(git_path: Path, *arguments: str, binary: bool = False) -> str | bytes:
    completed = subprocess.run(
        [
            str(git_path),
            "--no-replace-objects",
            "-c",
            f"core.hooksPath={os.devnull}",
            "-c",
            "core.autocrlf=false",
            "-c",
            f"core.attributesFile={os.devnull}",
            "-c",
            "core.fsmonitor=false",
            "-c",
            "core.untrackedCache=false",
            *arguments,
        ],
        cwd=contract.REPOSITORY_ROOT,
        env=_discovery_environment(git_path),
        check=False,
        capture_output=True,
    )
    if completed.returncode != 0:
        raise contract.MaterializationError(
            "pre-capture Git check failed: "
            + completed.stderr.decode("utf-8", "replace").strip()
        )
    if binary:
        return completed.stdout
    try:
        return completed.stdout.decode("utf-8", "strict").strip()
    except UnicodeDecodeError as error:
        raise contract.MaterializationError(
            "pre-capture Git output is not UTF-8"
        ) from error


def _verify_pre_capture_repository(git_path: Path) -> None:
    contract._reject_source_bytecode()
    if Path.cwd().resolve() != contract.REPOSITORY_ROOT.resolve():
        raise contract.MaterializationError(
            "environment capture must run from the repository root"
        )
    if (
        Path(str(_git_read(git_path, "rev-parse", "--show-toplevel"))).resolve()
        != contract.REPOSITORY_ROOT.resolve()
    ):
        raise contract.MaterializationError("environment capture Git root differs")
    if _git_read(git_path, "branch", "--show-current") != "main":
        raise contract.MaterializationError("environment capture requires main")
    if _git_read(git_path, "status", "--porcelain=v1", "--untracked-files=all"):
        raise contract.MaterializationError(
            "environment capture requires a completely clean worktree"
        )
    for relative in contract.FORBIDDEN_MECHANISM_PATHS:
        if os.path.lexists(contract.REPOSITORY_ROOT / relative):
            raise contract.MaterializationError(
                f"candidate mechanism exists before C1: {relative}"
            )

    tracked_lines = str(
        _git_read(git_path, "ls-tree", "-r", "--full-tree", "HEAD")
    ).splitlines()
    tracked: dict[str, tuple[str, str]] = {}
    for line in tracked_lines:
        metadata, separator, relative = line.partition("\t")
        fields = metadata.split()
        if not separator or len(fields) != 3 or relative in tracked:
            raise contract.MaterializationError("Git tree inventory is malformed")
        mode, kind, _object_id = fields
        tracked[relative] = (mode, kind)
    required = contract._required_c0_files() - {
        contract.ENVIRONMENT_LOCK_PATH.relative_to(contract.REPOSITORY_ROOT).as_posix()
    }
    missing = required - set(tracked)
    if missing:
        raise contract.MaterializationError(
            f"C0 source commit omits required files: {sorted(missing)}"
        )
    for relative in sorted(required):
        mode, kind = tracked[relative]
        if kind != "blob" or mode not in ("100644", "100755"):
            raise contract.MaterializationError(
                f"C0 source is not a regular Git blob: {relative}"
            )
        committed = _git_read(git_path, "show", f"HEAD:{relative}", binary=True)
        path = contract.REPOSITORY_ROOT / relative
        if not path.is_file() or path.is_symlink() or path.read_bytes() != committed:
            raise contract.MaterializationError(
                f"working C0 source differs from HEAD: {relative}"
            )

    closed_roots = (
        contract.SOURCE_ROOT,
        contract.REPOSITORY_ROOT / "schemas",
        contract.REPOSITORY_ROOT / "python" / "src" / "geotarget",
        contract.REPOSITORY_ROOT / "julia" / "GeoTargetBase" / "src",
        contract.REPOSITORY_ROOT / "julia" / "GeoTargetCore" / "src",
        contract.REPOSITORY_ROOT / "julia" / "GeoTargetGeometry" / "src",
    )
    live_closed = {
        path.relative_to(contract.REPOSITORY_ROOT).as_posix()
        for root in closed_roots
        for path in root.rglob("*")
        if path.is_file()
    }
    tracked_closed = {
        relative
        for relative in tracked
        if any(
            relative == root.relative_to(contract.REPOSITORY_ROOT).as_posix()
            or relative.startswith(
                f"{root.relative_to(contract.REPOSITORY_ROOT).as_posix()}/"
            )
            for root in closed_roots
        )
    }
    if live_closed != tracked_closed:
        raise contract.MaterializationError(
            "closed C0 source roots differ from HEAD: "
            f"untracked={sorted(live_closed - tracked_closed)}, "
            f"missing={sorted(tracked_closed - live_closed)}"
        )
    for path in (
        contract.ENVIRONMENT_LOCK_PATH,
        contract.FORMAL_JULIA_DEPOT_PATH,
        contract.VAULT_OUTPUT_PATH,
        contract.PRIVATE_VAULT_OUTPUT_PATH,
    ):
        _reject_reparse_ancestry(path.parent)
    for root in contract.FORMAL_OUTCOME_NAMESPACE_ROOTS:
        if os.path.lexists(root):
            raise contract.MaterializationError(
                f"formal outcome namespace already exists before C0 capture: {root}"
            )
        _reject_reparse_ancestry(root.parent)


def capture() -> Path:
    contract._python_execution_record()
    git_path = Path(shutil.which("git") or "")
    if not git_path.is_file():
        raise contract.MaterializationError("Git is unavailable for C0 preflight")
    _verify_pre_capture_repository(git_path)
    if contract.ENVIRONMENT_LOCK_PATH.exists():
        raise contract.MaterializationError("environment lock already exists")
    if contract.FORMAL_JULIA_DEPOT_PATH.exists():
        raise contract.MaterializationError(
            f"isolated Julia depot already exists: {contract.FORMAL_JULIA_DEPOT_PATH}"
        )
    contract.FORMAL_JULIA_DEPOT_PATH.mkdir(parents=True)
    discovery_environment = {
        name: value
        for name in (
            "SystemRoot",
            "WINDIR",
            "PATH",
            "PATHEXT",
            "TEMP",
            "TMP",
            "USERPROFILE",
            "LOCALAPPDATA",
            "APPDATA",
        )
        if (value := os.environ.get(name)) is not None
    }
    discovery_environment.update(
        {
            "JULIA_NUM_THREADS": "1",
            "OPENBLAS_NUM_THREADS": "1",
            "OMP_NUM_THREADS": "1",
            "MKL_NUM_THREADS": "1",
        }
    )
    discovered = subprocess.run(
        [
            contract._julia_executable(),
            "+1.12.6",
            "--startup-file=no",
            "--history-file=no",
            "-e",
            'print(VERSION, "\\n", joinpath(Sys.BINDIR, "julia.exe"))',
        ],
        check=False,
        capture_output=True,
        text=True,
        env=discovery_environment,
    )
    discovered_lines = discovered.stdout.splitlines()
    if (
        discovered.returncode != 0
        or len(discovered_lines) != 2
        or discovered_lines[0] != "1.12.6"
    ):
        raise contract.MaterializationError(
            f"Julia 1.12.6 discovery failed: {discovered.stderr.strip()}"
        )
    julia_runtime = Path(discovered_lines[1])
    if not julia_runtime.is_file():
        raise contract.MaterializationError("discovered Julia runtime is unavailable")
    julia_environment = contract._formal_julia_environment(julia_runtime)
    provisioning_environment = dict(julia_environment)
    provisioning_environment.pop("JULIA_PKG_OFFLINE")
    instantiate = subprocess.run(
        [
            str(julia_runtime),
            "--startup-file=no",
            "--history-file=no",
            "--compiled-modules=no",
            "--pkgimages=no",
            f"--project={REPOSITORY_ROOT / 'julia'}",
            "-e",
            "using Pkg; Pkg.instantiate()",
        ],
        check=False,
        capture_output=True,
        text=True,
        env=provisioning_environment,
    )
    if instantiate.returncode != 0:
        raise contract.MaterializationError(
            f"isolated Julia instantiate failed: {instantiate.stderr.strip()}"
        )
    smoke = subprocess.run(
        [
            str(julia_runtime),
            "--startup-file=no",
            "--history-file=no",
            "--compiled-modules=no",
            "--pkgimages=no",
            f"--project={REPOSITORY_ROOT / 'julia'}",
            "-e",
            (
                "using Pkg, GeoTargetCore; "
                '@assert LOAD_PATH == ["@", "@stdlib"]; '
                '@assert LocalSolveOptions().max_iterations == 250; print("ok")'
            ),
        ],
        check=False,
        capture_output=True,
        text=True,
        env=julia_environment,
    )
    if smoke.returncode != 0 or smoke.stdout != "ok":
        raise contract.MaterializationError(
            f"formal Julia load-path smoke test failed: {smoke.stderr.strip()}"
        )
    contract._verify_numeric_runtime(julia_runtime, julia_environment)
    completed = subprocess.run(
        [
            str(julia_runtime),
            "--startup-file=no",
            "--history-file=no",
            "--compiled-modules=no",
            "--pkgimages=no",
            "-e",
            'print(VERSION, "\\n", joinpath(Sys.BINDIR, "julia.exe"), "\\n", Threads.nthreads(), "\\n", Sys.CPU_NAME)',
        ],
        check=False,
        capture_output=True,
        text=True,
        env=julia_environment,
    )
    lines = completed.stdout.splitlines()
    if completed.returncode != 0 or len(lines) != 4 or lines[2] != "1":
        raise contract.MaterializationError("Julia 1-thread runtime capture failed")
    uv_path = Path(shutil.which("uv") or "")
    if not julia_runtime.is_file() or not uv_path.is_file() or not git_path.is_file():
        raise contract.MaterializationError(
            "required runtime executable is unavailable"
        )
    runtime_root = julia_runtime.parent.parent
    if (
        not (contract.FORMAL_JULIA_DEPOT_PATH / "packages").is_dir()
        or not (contract.FORMAL_JULIA_DEPOT_PATH / "registries").is_dir()
    ):
        raise contract.MaterializationError("isolated Julia depot is incomplete")
    # Python 3.12 deliberately leaves ``sys.prefix`` at the base runtime under
    # ``-S``.  Resolve the already-verified project venv from sys.executable.
    python_root = contract._fixed_python_environment_root()
    for root in contract.FORMAL_OUTCOME_NAMESPACE_ROOTS:
        try:
            root.mkdir(parents=True, exist_ok=False)
        except OSError as error:
            raise contract.MaterializationError(
                f"cannot create formal outcome namespace {root}: {error}"
            ) from error
        _reject_reparse_ancestry(root)
    document = {
        "schema_version": "exp-local-003-environment-lock/v1",
        "card_sha256": contract.CARD_SHA256,
        "platform": {
            "system": platform.system(),
            "release": platform.release(),
            "machine": platform.machine(),
            "processor": platform.processor(),
            "processor_identifier": os.environ.get("PROCESSOR_IDENTIFIER"),
        },
        "julia": {
            "version": lines[0],
            "runtime_executable": str(julia_runtime),
            "runtime_sha256": contract._sha256_path(julia_runtime),
            "project_sha256": contract._sha256_path(
                REPOSITORY_ROOT / "julia" / "Project.toml"
            ),
            "manifest_sha256": contract._sha256_path(
                REPOSITORY_ROOT / "julia" / "Manifest.toml"
            ),
            "threads": 1,
            "cpu_name": lines[3],
            "runtime_tree": contract._environment_tree_record(
                runtime_root,
                included=(".",),
                require_sandbox_safe=True,
            ),
            "depot_tree": contract._environment_tree_record(
                contract.FORMAL_JULIA_DEPOT_PATH,
                included=(".",),
                excluded_parts=frozenset(("compiled", "logs", "formal-tmp")),
                require_sandbox_safe=True,
            ),
        },
        "python": {
            "version": platform.python_version(),
            "runtime_executable": str(Path(sys.executable)),
            "runtime_sha256": contract._sha256_path(Path(sys.executable)),
            "pyproject_sha256": contract._sha256_path(
                REPOSITORY_ROOT / "python" / "pyproject.toml"
            ),
            "uv_lock_sha256": contract._sha256_path(
                REPOSITORY_ROOT / "python" / "uv.lock"
            ),
            "environment_tree": contract._environment_tree_record(
                python_root,
                included=(".",),
            ),
            "base_runtime_tree": contract._environment_tree_record(
                Path(sys.base_prefix),
                included=contract._python_base_runtime_included(Path(sys.base_prefix)),
                excluded_parts=frozenset(("site-packages",)),
            ),
        },
        "tools": {
            "uv_version": subprocess.run(
                [str(uv_path), "--version"], check=True, capture_output=True, text=True
            ).stdout.strip(),
            "uv_executable": str(uv_path),
            "uv_sha256": contract._sha256_path(uv_path),
            "git_version": subprocess.run(
                [str(git_path), "--version"], check=True, capture_output=True, text=True
            ).stdout.strip(),
            "git_executable": str(git_path),
            "git_sha256": contract._sha256_path(git_path),
        },
        "execution": {
            "julia_num_threads": 1,
            "openblas_num_threads": 1,
            "omp_num_threads": 1,
            "mkl_num_threads": 1,
            "julia_depot_path": str(contract.FORMAL_JULIA_DEPOT_PATH),
            "julia_environment": julia_environment,
            "julia_compiled_modules": False,
            "julia_pkgimages": False,
            "python": contract._python_execution_record(),
            "float_mode": "IEEE-754 binary64 roundTiesToEven with Base.fma",
            "formal_outcome_namespace_roots": [
                str(path) for path in contract.FORMAL_OUTCOME_NAMESPACE_ROOTS
            ],
        },
        "numeric_fixture_sha256": contract._sha256_path(contract.NUMERIC_DOMAIN_PATH),
    }
    contract._exclusive_write_json(contract.ENVIRONMENT_LOCK_PATH, document)
    return contract.ENVIRONMENT_LOCK_PATH


def main() -> int:
    if len(sys.argv) != 1:
        raise contract.MaterializationError("environment capture accepts no options")
    print(f"created {capture()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
