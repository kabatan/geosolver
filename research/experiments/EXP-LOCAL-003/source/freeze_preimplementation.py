"""Create the single closed EXP-LOCAL-003 C0 lock on a clean source commit.

This script is itself part of C0.  It has no force/overwrite/output options and
does not materialize candidate or Gold inputs.
"""

from __future__ import annotations

import os
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
        raise RuntimeError("C0 freeze requires exact `python -I -B -S`")
    blocked = sorted(
        name
        for name in os.environ
        if name.upper().startswith(_BLOCKED_ENVIRONMENT_PREFIXES)
    )
    if blocked:
        raise RuntimeError(f"C0 freeze has injection environment: {blocked}")
    if any("site-packages" in value.casefold() for value in sys.path):
        raise RuntimeError("site-packages was active before the C0 freeze")
    expected = Path(__file__).resolve(strict=True)
    main_file = getattr(sys.modules.get("__main__"), "__file__", None)
    if (
        Path(sys.argv[0]).resolve(strict=True) != expected
        or not isinstance(main_file, str)
        or Path(main_file).resolve(strict=True) != expected
        or Path.cwd().resolve(strict=True) != REPOSITORY_ROOT.resolve(strict=True)
    ):
        raise RuntimeError("C0 freeze must execute directly at repository root")
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
        raise RuntimeError("C0 freeze is not using the fixed project venv")
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
import authority  # noqa: E402


def _git(*arguments: str) -> str:
    return contract._run_git(*arguments)


def freeze() -> Path:
    contract._python_execution_record()
    contract._reject_source_bytecode()
    if contract.LOCK_PATH.exists():
        raise contract.MaterializationError("preimplementation lock already exists")
    contract.verify_frozen_environment()
    if _git("status", "--porcelain=v1", "--untracked-files=all"):
        raise contract.MaterializationError(
            "C0 freeze requires a completely clean worktree"
        )
    if _git("branch", "--show-current") != "main":
        raise contract.MaterializationError("C0 freeze must run directly on main")
    if any(
        path.exists()
        for path in (
            contract.ATTEMPT_PATH,
            contract.CANDIDATE_OUTPUT_PATH,
            contract.VAULT_OUTPUT_PATH,
            contract.PRIVATE_VAULT_OUTPUT_PATH,
            contract.VAULT_ANCHOR_PATH,
            contract.PRIVATE_VAULT_ANCHOR_PATH,
        )
    ):
        raise contract.MaterializationError("C1 evidence exists before C0 freeze")
    for relative in contract.FORBIDDEN_MECHANISM_PATHS:
        if (REPOSITORY_ROOT / relative).exists():
            raise contract.MaterializationError(
                f"candidate mechanism exists before C1: {relative}"
            )
    required = contract._required_c0_files()
    source_commit = _git("rev-parse", "HEAD")
    source_tree = _git("rev-parse", "HEAD^{tree}")
    environment = contract._load_object(contract.ENVIRONMENT_LOCK_PATH)
    tools = environment.get("tools")
    if not isinstance(tools, dict):
        raise contract.MaterializationError("environment lock has no Git authority")
    try:
        git = authority.pin_git_executable(
            Path(tools["git_executable"]), tools["git_sha256"]
        )
        repository = authority.GitObjectRepository(REPOSITORY_ROOT, git)
        index = repository.tree_index(source_commit)
    except (KeyError, TypeError, authority.AuthorityError) as error:
        raise contract.MaterializationError(
            f"cannot resolve immutable C0 inventory: {error}"
        ) from error
    missing = required - set(index)
    if missing:
        raise contract.MaterializationError(
            f"required C0 files are missing from HEAD: {sorted(missing)}"
        )
    committed_payloads: dict[str, bytes] = {}
    for relative in sorted(required):
        blob = repository.blob_at(source_commit, relative)
        path = REPOSITORY_ROOT / relative
        if (
            blob.mode not in ("100644", "100755")
            or not path.is_file()
            or path.is_symlink()
            or path.read_bytes() != blob.data
        ):
            raise contract.MaterializationError(
                f"working C0 file differs from regular HEAD blob: {relative}"
            )
        committed_payloads[relative] = blob.data
    closed_roots = (
        contract.SOURCE_ROOT,
        REPOSITORY_ROOT / "schemas",
        REPOSITORY_ROOT / "python" / "src" / "geotarget",
        REPOSITORY_ROOT / "julia" / "GeoTargetBase" / "src",
        REPOSITORY_ROOT / "julia" / "GeoTargetCore" / "src",
        REPOSITORY_ROOT / "julia" / "GeoTargetGeometry" / "src",
    )
    live_closed = {
        path.relative_to(REPOSITORY_ROOT).as_posix()
        for root in closed_roots
        for path in root.rglob("*")
        if path.is_file()
    }
    prefixes = tuple(
        root.relative_to(REPOSITORY_ROOT).as_posix() for root in closed_roots
    )
    committed_closed = {
        relative
        for relative in index
        if any(
            relative == prefix or relative.startswith(f"{prefix}/")
            for prefix in prefixes
        )
    }
    if live_closed != committed_closed:
        raise contract.MaterializationError(
            "closed C0 roots differ from HEAD: "
            f"untracked={sorted(live_closed - committed_closed)}, "
            f"missing={sorted(committed_closed - live_closed)}"
        )
    source_prefix = contract.SOURCE_ROOT.relative_to(REPOSITORY_ROOT).as_posix()
    source_files = sorted(
        relative for relative in required if relative.startswith(f"{source_prefix}/")
    )
    document = {
        "schema_version": "exp-local-003-preimplementation-lock/v1",
        "experiment_id": "EXP-LOCAL-003",
        "status": "frozen-before-one-shot-development-materialization",
        "card_sha256": contract.CARD_SHA256,
        "c0_source_commit": source_commit,
        "c0_source_tree": source_tree,
        "files": {
            relative: contract._sha256_bytes(committed_payloads[relative])
            for relative in sorted(required)
        },
        "experiment_source_files": source_files,
        "forbidden_mechanism_paths": list(contract.FORBIDDEN_MECHANISM_PATHS),
        "environment_lock_sha256": contract._sha256_path(
            contract.ENVIRONMENT_LOCK_PATH
        ),
        "local_options_sha256": contract._local_options_sha256(),
    }
    contract._exclusive_write_json(contract.LOCK_PATH, document)
    return contract.LOCK_PATH


def main() -> int:
    if len(sys.argv) != 1:
        raise contract.MaterializationError("freeze script accepts no options")
    print(f"created {freeze()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
