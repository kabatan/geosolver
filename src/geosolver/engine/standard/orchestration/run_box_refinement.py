"""Phase B orchestration for box-solver backend."""

from __future__ import annotations

import re

from geosolver.engine.standard.contracts.branch_box import (
    STAGE_SEARCH_COMPACT,
    BranchBox,
)
from geosolver.engine.standard.contracts.box_solver_port import BoxSolverPort
from geosolver.engine.standard.contracts.candidate_record import (
    RefinementBatchResult,
    SearchBatchResult,
)
from geosolver.engine.standard.contracts.evaluator_port import EvaluatorPort
from geosolver.engine.standard.contracts.external_pipeline_config import ExternalPipelineConfig
from geosolver.engine.standard.contracts.problem_bundle import ProblemBundle
from geosolver.engine.standard.search.select_rescue_boxes import (
    _axis_radius_from_neighbor_distance,
    _clamp_box_to_global_bounds,
    _nearest_representative_distance,
)


def _solver_name_from_instance(box_solver: BoxSolverPort) -> str:
    name = box_solver.__class__.__name__
    snake = re.sub(r"(?<!^)(?=[A-Z])", "_", name).lower()
    return snake


def _build_compact_boxes(
    *,
    search_result: SearchBatchResult,
    bounds: list[tuple[float, float]],
    pipeline_config: ExternalPipelineConfig,
) -> tuple[BranchBox, ...]:
    candidates = tuple(search_result.candidates)
    boxes: list[BranchBox] = []
    for index, candidate in enumerate(candidates, start=1):
        neighbor_distance = _nearest_representative_distance(
            candidate=candidate,
            representatives=candidates,
            bounds=bounds,
        )
        axis_radii = tuple(
            _axis_radius_from_neighbor_distance(
                global_width=(high - low),
                neighbor_distance=neighbor_distance,
                pipeline_config=pipeline_config,
            )
            for low, high in bounds
        )
        center, lower_bounds, upper_bounds = _clamp_box_to_global_bounds(
            center=candidate.x_float,
            axis_radii=axis_radii,
            bounds=bounds,
        )
        boxes.append(
            BranchBox(
                box_id=index,
                center=center,
                lower_bounds=lower_bounds,
                upper_bounds=upper_bounds,
                source_candidate_ids=(int(candidate.candidate_id),),
                priority=float(candidate.score),
                stage=STAGE_SEARCH_COMPACT,
            )
        )
    return tuple(boxes)


def _reindex_rescue_boxes(
    *,
    rescue_boxes: tuple[BranchBox, ...],
    start_box_id: int,
) -> tuple[BranchBox, ...]:
    reindexed: list[BranchBox] = []
    for offset, box in enumerate(rescue_boxes):
        reindexed.append(
            BranchBox(
                box_id=start_box_id + offset,
                center=tuple(box.center),
                lower_bounds=tuple(box.lower_bounds),
                upper_bounds=tuple(box.upper_bounds),
                source_candidate_ids=tuple(box.source_candidate_ids),
                priority=float(box.priority),
                stage=box.stage,
            )
        )
    return tuple(reindexed)


def run_box_refinement(
    *,
    bundle: ProblemBundle,
    evaluator: EvaluatorPort,
    bounds: list[tuple[float, float]],
    search_result: SearchBatchResult,
    pipeline_config: ExternalPipelineConfig,
    box_solver: BoxSolverPort,
    rescue_boxes: tuple[BranchBox, ...] = (),
) -> RefinementBatchResult:
    """Run phase B box-solver path from compact + rescue branch boxes."""
    _ = pipeline_config
    compact_boxes = _build_compact_boxes(
        search_result=search_result,
        bounds=bounds,
        pipeline_config=pipeline_config,
    )
    rescue_reindexed = _reindex_rescue_boxes(
        rescue_boxes=rescue_boxes,
        start_box_id=len(compact_boxes) + 1,
    )
    requested_boxes = tuple(compact_boxes) + tuple(rescue_reindexed)
    if not requested_boxes:
        return RefinementBatchResult(
            candidates=(),
            converged_count=0,
            attempted_count=0,
            solver_name=_solver_name_from_instance(box_solver),
            hard_feasible_count=0,
            attempted_box_count=0,
        )
    solved = box_solver.solve_boxes(
        bundle=bundle,
        evaluator=evaluator,
        boxes=requested_boxes,
        task_kind="solve",
    )
    return RefinementBatchResult(
        candidates=tuple(solved.candidates),
        converged_count=int(solved.converged_count),
        attempted_count=int(solved.attempted_count),
        solver_name=(
            solved.solver_name
            if solved.solver_name
            else _solver_name_from_instance(box_solver)
        ),
        hard_feasible_count=int(solved.hard_feasible_count),
        attempted_box_count=max(int(solved.attempted_box_count), len(requested_boxes)),
    )
