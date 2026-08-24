"""Julia sidecar-compatible BoxSolverPort implementation."""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from pathlib import Path

from mpmath import mp

from geosolver.engine.standard.contracts.branch_box import BranchBox
from geosolver.engine.standard.contracts.candidate_record import (
    RefinedCandidate,
    RefinementBatchResult,
)
from geosolver.engine.standard.contracts.evaluator_port import EvaluatorPort
from geosolver.engine.standard.contracts.problem_bundle import ProblemBundle
from geosolver.engine.standard.precision.type_guards.mp_types import MPFloat

from ...contracts.box_solver_port import BoxSolverPort, TaskKind

_BOX_SOLVER_NAME = "julia_box_solver"
_PROTOCOL_VERSION = 1
_ALLOWED_TERMINATIONS = {
    "box_solved",
    "box_enumerated",
    "box_timeout",
    "box_invalid",
    "box_infeasible",
    "box_degenerate",
    "box_error",
}


def _to_mpf_from_text(value: object, *, field_name: str) -> MPFloat:
    if not isinstance(value, str):
        raise ValueError(f"{field_name} must be str, got {type(value).__name__}")
    if value.strip() == "":
        raise ValueError(f"{field_name} must not be empty")
    return mp.mpf(value)


def _to_optional_mpf_from_text(value: object, *, field_name: str) -> MPFloat | None:
    if value is None:
        return None
    if isinstance(value, str) and value.strip() == "":
        return None
    return _to_mpf_from_text(value, field_name=field_name)


@dataclass(frozen=True)
class JuliaBoxSolver(BoxSolverPort):
    """Box solver adapter with Julia-JSON contract and compatibility fallback."""

    precision_dps: int = 120
    time_budget_sec: float = 20.0
    command: tuple[str, ...] | None = None
    project_dir: str | None = None
    entry_script: str | None = None

    def _build_payload(
        self,
        *,
        bundle: ProblemBundle,
        boxes: tuple[BranchBox, ...],
        task_kind: TaskKind,
    ) -> dict[str, object]:
        return {
            "protocol_version": _PROTOCOL_VERSION,
            "task": task_kind,
            "problem_id": bundle.problem_id,
            "variables": list(bundle.var_names),
            "boxes": [
                {
                    "box_id": int(box.box_id),
                    "lower": [str(value) for value in box.lower_bounds],
                    "upper": [str(value) for value in box.upper_bounds],
                    "priority": float(box.priority),
                    "stage": box.stage,
                    "source_candidate_ids": [int(value) for value in box.source_candidate_ids],
                }
                for box in boxes
            ],
            "precision_dps": int(self.precision_dps),
            "time_budget_sec": float(self.time_budget_sec),
            "spec": {},
            "hard_checks": [],
        }

    def _build_command(self) -> list[str]:
        if self.command is not None:
            return list(self.command)
        command: list[str] = ["julia"]
        project = self.project_dir or str(Path(__file__).resolve().parents[3] / "julia")
        command.append(f"--project={project}")
        if self.entry_script is not None and self.entry_script.strip():
            command.append(self.entry_script)
        return command

    def _run_sidecar(self, payload: dict[str, object]) -> dict[str, object]:
        process = subprocess.run(
            self._build_command(),
            input=json.dumps(payload, ensure_ascii=False),
            capture_output=True,
            text=True,
            timeout=max(1, int(self.time_budget_sec)),
            check=False,
        )
        if process.returncode != 0:
            stderr = process.stderr.strip()
            raise RuntimeError(
                f"Julia sidecar failed: returncode={process.returncode}, stderr={stderr}"
            )
        if process.stdout.strip() == "":
            raise RuntimeError("Julia sidecar returned empty stdout")
        parsed = json.loads(process.stdout)
        if not isinstance(parsed, dict):
            raise RuntimeError("Julia sidecar response must be a JSON object")
        return parsed

    def _parse_response(
        self,
        *,
        response: dict[str, object],
        attempted_box_count: int,
    ) -> RefinementBatchResult:
        if str(response.get("status")) != "ok":
            raise RuntimeError(f"Julia sidecar status is not ok: {response.get('status')!r}")
        response_candidates = response.get("candidates")
        if not isinstance(response_candidates, list):
            raise RuntimeError("Julia sidecar response must include candidates list")
        refined_candidates: list[RefinedCandidate] = []
        for index, candidate_raw in enumerate(response_candidates, start=1):
            if not isinstance(candidate_raw, dict):
                raise RuntimeError("candidate entry must be object")
            box_id = int(candidate_raw["box_id"])
            x_raw = candidate_raw.get("x")
            if not isinstance(x_raw, list):
                raise RuntimeError("candidate.x must be list[str]")
            x_hp = tuple(
                _to_mpf_from_text(value, field_name=f"candidate[{index}].x[{dim}]")
                for dim, value in enumerate(x_raw)
            )
            residual_hp = _to_mpf_from_text(
                candidate_raw.get("residual"),
                field_name=f"candidate[{index}].residual",
            )
            answer_hp = _to_optional_mpf_from_text(
                candidate_raw.get("answer"),
                field_name=f"candidate[{index}].answer",
            )
            validity_margin_hp = _to_optional_mpf_from_text(
                candidate_raw.get("validity_margin"),
                field_name=f"candidate[{index}].validity_margin",
            )
            hard_feasible = bool(candidate_raw.get("hard_feasible", False))
            termination = str(candidate_raw.get("termination", "box_error"))
            if termination not in _ALLOWED_TERMINATIONS:
                raise RuntimeError(f"unsupported termination: {termination!r}")
            candidate_id = box_id * 1_000_000 + index
            refined_candidates.append(
                RefinedCandidate(
                    x_hp=x_hp,
                    residual_norm_hp=residual_hp,
                    answer_hp=answer_hp,
                    refinement_status=termination,
                    phase_history=(f"julia:{termination}",),
                    source=None,
                    candidate_id=candidate_id,
                    hard_feasible=hard_feasible,
                    hard_violation_tags=() if hard_feasible else ("box_solver_infeasible",),
                    validity_margin_hp=validity_margin_hp,
                )
            )
        diagnostics = response.get("diagnostics")
        completed_box_count = attempted_box_count
        if isinstance(diagnostics, dict) and "completed_box_count" in diagnostics:
            completed_box_count = int(diagnostics["completed_box_count"])
        converged_count = sum(
            1 for candidate in refined_candidates if candidate.refinement_status == "box_solved"
        )
        hard_feasible_count = sum(1 for candidate in refined_candidates if candidate.hard_feasible)
        return RefinementBatchResult(
            candidates=tuple(refined_candidates),
            converged_count=converged_count,
            attempted_count=len(refined_candidates),
            solver_name=_BOX_SOLVER_NAME,
            hard_feasible_count=hard_feasible_count,
            attempted_box_count=completed_box_count,
        )

    def solve_boxes(
        self,
        *,
        bundle: ProblemBundle,
        evaluator: EvaluatorPort,
        boxes: tuple[BranchBox, ...],
        task_kind: TaskKind,
    ) -> RefinementBatchResult:
        if not boxes:
            return RefinementBatchResult(
                candidates=(),
                converged_count=0,
                attempted_count=0,
                solver_name=_BOX_SOLVER_NAME,
                hard_feasible_count=0,
                attempted_box_count=0,
            )
        if self.entry_script is None:
            raise RuntimeError(
                "JuliaBoxSolver requires entry_script for solve_boxes() (no silent fallback)."
            )
        payload = self._build_payload(bundle=bundle, boxes=boxes, task_kind=task_kind)
        response = self._run_sidecar(payload)
        _ = evaluator
        return self._parse_response(
            response=response,
            attempted_box_count=len(boxes),
        )
