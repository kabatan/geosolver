"""Lazy Julia kernel session with fallback-safe unavailable responses."""

from __future__ import annotations

import os
import shutil
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from .protocol import KernelError, KernelResponse, dumps_request

ENV_JULIA_BINDIR = "GEOSOLVER_JULIA_BINDIR"
ENV_JULIA_PROJECT = "GEOSOLVER_JULIA_PROJECT"
ENV_ENABLE_JULIA_KERNEL = "GEOSOLVER_ENABLE_JULIA_KERNEL"
JULIA_KERNEL_UNAVAILABLE = "JULIA_KERNEL_UNAVAILABLE"
DEFAULT_JULIA_VERSION = "1.12.6"
DEFAULT_JULIA_BINDIR = str(
    Path.home() / ".local" / "share" / "geosolver" / f"julia-{DEFAULT_JULIA_VERSION}" / "bin"
)


def _default_project() -> str:
    path = Path(__file__).resolve()
    try:
        return str(path.parents[5] / "julia" / "GeoSolverKernel")
    except IndexError:
        return "julia/GeoSolverKernel"


DEFAULT_JULIA_PROJECT = _default_project()


def _env_enabled() -> bool:
    value = os.environ.get(ENV_ENABLE_JULIA_KERNEL, "")
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _julia_executable_from_bindir(bindir: str) -> str | None:
    if not bindir.strip():
        return None
    candidate = Path(bindir).expanduser() / "julia"
    if candidate.is_file() and os.access(candidate, os.X_OK):
        return str(candidate)
    return None


@dataclass
class JuliaKernelSession:
    """Lazily initializes Julia only when explicitly enabled."""

    enabled: bool | None = None
    bindir: str | None = None
    project: str | None = None

    def __post_init__(self) -> None:
        self._initialized = False
        self._main = None
        self._unavailable: KernelResponse | None = None

    @property
    def effective_enabled(self) -> bool:
        return _env_enabled() if self.enabled is None else bool(self.enabled)

    @property
    def effective_bindir(self) -> str:
        return self.bindir or os.environ.get(ENV_JULIA_BINDIR, DEFAULT_JULIA_BINDIR)

    @property
    def effective_project(self) -> str:
        return self.project or os.environ.get(ENV_JULIA_PROJECT, DEFAULT_JULIA_PROJECT)

    def _metadata(self, *, reason: str) -> dict[str, object]:
        return {
            "enabled": bool(self.effective_enabled),
            "reason": reason,
            "bindir": self.effective_bindir,
            "project": self.effective_project,
        }

    def _unavailable_response(
        self,
        *,
        reason: str,
        message: str,
        elapsed_sec: float = 0.0,
    ) -> KernelResponse:
        return KernelResponse.unavailable(
            code=JULIA_KERNEL_UNAVAILABLE,
            message=message,
            metadata=self._metadata(reason=reason),
            elapsed_sec=elapsed_sec,
        )

    def _resolve_julia_executable(self) -> str | None:
        from_bindir = _julia_executable_from_bindir(self.effective_bindir)
        if from_bindir is not None:
            return from_bindir
        return shutil.which("julia")

    def _ensure_initialized(self) -> KernelResponse | None:
        if self._initialized:
            return self._unavailable
        started = time.monotonic()
        self._initialized = True
        if not self.effective_enabled:
            self._unavailable = self._unavailable_response(
                reason="disabled_by_feature_flag",
                message=f"{ENV_ENABLE_JULIA_KERNEL} is not enabled",
                elapsed_sec=time.monotonic() - started,
            )
            return self._unavailable
        executable = self._resolve_julia_executable()
        if executable is None:
            self._unavailable = self._unavailable_response(
                reason="julia_executable_not_found",
                message="Julia executable was not found in GEOSOLVER_JULIA_BINDIR or PATH",
                elapsed_sec=time.monotonic() - started,
            )
            return self._unavailable
        os.environ.setdefault("PYTHON_JULIACALL_EXE", executable)
        os.environ.setdefault("PYTHON_JULIACALL_PROJECT", self.effective_project)
        os.environ.setdefault("JULIA_PROJECT", self.effective_project)
        try:
            from juliacall import Main  # type: ignore  # noqa: PLC0415
        except Exception as exc:
            self._unavailable = self._unavailable_response(
                reason="juliacall_import_failed",
                message=f"juliacall could not be imported: {exc}",
                elapsed_sec=time.monotonic() - started,
            )
            return self._unavailable
        try:
            Main.seval('import Pkg; Pkg.activate(ENV["JULIA_PROJECT"])')
            Main.seval("using GeoSolverKernel")
        except Exception as exc:
            self._unavailable = self._unavailable_response(
                reason="julia_package_init_failed",
                message=f"GeoSolverKernel could not be initialized: {exc}",
                elapsed_sec=time.monotonic() - started,
            )
            return self._unavailable
        self._main = Main
        self._unavailable = None
        return None

    def _call_json(self, function_name: str, payload: dict[str, object]) -> KernelResponse:
        started = time.monotonic()
        unavailable = self._ensure_initialized()
        if unavailable is not None:
            return unavailable
        try:
            assert self._main is not None
            function: Callable[[str], str] = self._main.seval(
                f"GeoSolverKernel.{function_name}"
            )
            raw = function(dumps_request(payload))
        except Exception as exc:
            return KernelResponse(
                ok=False,
                error=KernelError(
                    code="JULIA_KERNEL_CALL_FAILED",
                    message=str(exc),
                ),
                metadata=self._metadata(reason="call_failed"),
                elapsed_sec=time.monotonic() - started,
            )
        return KernelResponse.from_json(
            str(raw),
            metadata=self._metadata(reason="ok"),
            elapsed_sec=time.monotonic() - started,
        )

    def version_info(self) -> KernelResponse:
        return self._call_json("version_info", {})

    def compile_json(self, payload: dict[str, object]) -> KernelResponse:
        return self._call_json("compile_json", payload)

    def solve_json(self, payload: dict[str, object]) -> KernelResponse:
        return self._call_json("solve_json", payload)

    def refine_json(self, payload: dict[str, object]) -> KernelResponse:
        return self._call_json("refine_json", payload)

    def verify_json(self, payload: dict[str, object]) -> KernelResponse:
        return self._call_json("verify_json", payload)


_SESSION: JuliaKernelSession | None = None


def get_julia_kernel_session(*, reset: bool = False) -> JuliaKernelSession:
    global _SESSION  # noqa: PLW0603
    if reset or _SESSION is None:
        _SESSION = JuliaKernelSession()
    return _SESSION
