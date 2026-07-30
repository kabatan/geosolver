"""Checkpoint-genealogical adaptive multilevel splitting D0.

This module owns only an in-process trajectory genealogy.  Local numerical
transitions are delegated to the directly copied Wave-10 checkpoint kernel.
The scheduler sees source residual/violation observations and opaque local
state; it never sees a problem identity, target, truth, or expected root count.
"""

from __future__ import annotations

import copy
from dataclasses import dataclass, field, replace
import hashlib
import math
from typing import Callable, Mapping, Sequence

import numpy as np

import checkpoint_kernel as kernel


SCHEMA = "geotarget.exp-v15-243.checkpoint-genealogical-ams-d0/v1"
BASELINE_FLOOR = 0.75
SIDE_CEILING = 0.25
SCORE_FLOOR = 1.0e-300


@dataclass(frozen=True, order=True)
class PassageScore:
    """Lexicographic target-free first-passage score."""

    semantic_valid: int
    log_merit: float

    def __post_init__(self) -> None:
        if self.semantic_valid not in (0, 1):
            raise ValueError("semantic_valid must be zero or one")
        if not math.isfinite(self.log_merit):
            raise ValueError("log_merit must be finite")


@dataclass
class FirstPassage:
    score: PassageScore
    callback_ordinal: int
    accepted_generation: int
    checkpoint: kernel.CheckpointState


@dataclass
class Trajectory:
    trajectory_id: int
    root_trajectory_id: int
    parent_trajectory_id: int | None
    generation: int
    state: kernel.CheckpointState
    first_passages: list[FirstPassage] = field(default_factory=list)
    maximum_score: PassageScore = field(
        default_factory=lambda: PassageScore(0, -300.0)
    )
    last_generation_seen: int = -1
    charged_here: int = 0
    relocation_pending: bool = False


@dataclass(frozen=True)
class StartRuntime:
    case: object
    program: object
    start: np.ndarray
    scale: np.ndarray
    lower: np.ndarray
    upper: np.ndarray
    source_binding_token: bytes


@dataclass(frozen=True)
class GenealogyEvent:
    generation: int
    killed_trajectory_id: int
    parent_trajectory_id: int
    child_trajectory_id: int
    level: PassageScore
    parent_passage_callback: int
    perturbation_norm_z: float
    tangent_source: str
    rng_key_sha256: str


@dataclass(frozen=True)
class AMSResult:
    status: str
    charged_callbacks: int
    callback_budget: int
    trajectories_created: int
    genealogy: tuple[GenealogyEvent, ...]
    endpoints: tuple[np.ndarray, ...]
    replayed_safe_endpoints: tuple[np.ndarray, ...]
    maximum_scores: tuple[PassageScore, ...]
    first_passage_count: int
    invalid_or_opaque_events: int
    source_replay_rejections: int


RuntimeFactory = Callable[[int], StartRuntime]
Replay = Callable[[Sequence[float]], bool]


def split_budget(total_callbacks: int) -> tuple[int, int]:
    if total_callbacks <= 0:
        raise ValueError("total callback budget must be positive")
    baseline = math.ceil(BASELINE_FLOOR * total_callbacks)
    side = total_callbacks - baseline
    if side > math.floor(SIDE_CEILING * total_callbacks):
        raise AssertionError("AMS side exceeds its frozen ceiling")
    return baseline, side


def _copy_checkpoint(state: kernel.CheckpointState) -> kernel.CheckpointState:
    """Copy state in memory while retaining the worker-owned evaluator."""

    case = state.case
    program = state.program
    clone = copy.deepcopy(state)
    clone.case = case
    clone.program = program
    return clone


def _state_score(state: kernel.CheckpointState) -> PassageScore | None:
    current = state.current
    if current is None:
        return None
    relation = np.asarray(current.relation, dtype=float)
    if relation.ndim != 1 or not np.all(np.isfinite(relation)):
        return None
    violation = float(current.violation_inf)
    if not math.isfinite(violation) or violation < 0.0:
        return None
    merit = float(np.linalg.norm(relation)) + violation
    if not math.isfinite(merit) or merit < 0.0:
        return None
    return PassageScore(
        int(bool(current.semantics_valid)),
        float(-math.log10(merit + SCORE_FLOOR)),
    )


def _record_first_passage(trajectory: Trajectory) -> bool:
    """Record the first accepted checkpoint attaining a new maximum score."""

    state = trajectory.state
    score = _state_score(state)
    if score is None:
        return False
    if state.current_generation == trajectory.last_generation_seen:
        # The initial evaluation is a genuine first arrival, but the copied
        # Wave-10 kernel builds its local model in callback-free transitions
        # just before the next charged trial.  Preserve the first-arrival
        # ordinal and level while upgrading only its resumable in-memory
        # checkpoint once that model exists at the identical accepted point.
        # This is not a later score crossing and therefore does not create a
        # second passage or falsify the first-passage genealogy.
        if trajectory.first_passages:
            passage = trajectory.first_passages[-1]
            if (
                passage.accepted_generation == state.current_generation
                and passage.checkpoint.direct_model is None
                and state.direct_model is not None
                and passage.checkpoint.current is not None
                and state.current is not None
                and np.array_equal(
                    passage.checkpoint.current.x,
                    state.current.x,
                )
            ):
                passage.checkpoint = _copy_checkpoint(state)
        return False
    trajectory.last_generation_seen = int(state.current_generation)
    if score <= trajectory.maximum_score:
        return False
    trajectory.maximum_score = score
    trajectory.first_passages.append(
        FirstPassage(
            score,
            state.charged_callbacks,
            int(state.current_generation),
            _copy_checkpoint(state),
        )
    )
    return True


def _first_crossing(
    trajectory: Trajectory, level: PassageScore
) -> FirstPassage | None:
    for passage in trajectory.first_passages:
        if passage.score > level:
            return passage
    return None


def _genealogy_rng(
    seed: int, generation: int, parent_id: int, child_id: int
) -> tuple[np.random.Generator, str]:
    payload = (
        f"checkpoint-genealogical-ams/v1:{seed}:{generation}:"
        f"{parent_id}:{child_id}"
    ).encode("ascii")
    digest = hashlib.sha256(payload).hexdigest()
    words = np.frombuffer(bytes.fromhex(digest), dtype=np.uint32)
    return np.random.default_rng(np.random.SeedSequence(words)), digest


def _tangent_direction(
    state: kernel.CheckpointState, rng: np.random.Generator
) -> tuple[np.ndarray, str]:
    dimension = int(state.program.dimension)
    model = state.direct_model
    if isinstance(model, np.ndarray) and model.ndim == 2 and model.shape[1] == dimension:
        try:
            _u, _s, vh = np.linalg.svd(model, full_matrices=True)
            tangent = np.asarray(vh[-1], dtype=float)
            if np.all(np.isfinite(tangent)) and np.linalg.norm(tangent) > 0.0:
                tangent /= np.linalg.norm(tangent)
                if float(rng.random()) < 0.5:
                    tangent = -tangent
                return tangent, "weak-right-singular-vector"
        except np.linalg.LinAlgError:
            pass
    tangent = rng.normal(size=dimension)
    norm = float(np.linalg.norm(tangent))
    if not math.isfinite(norm) or norm == 0.0:
        tangent = np.zeros(dimension, dtype=float)
        tangent[0] = 1.0
    else:
        tangent /= norm
    return tangent, "isotropic-fallback"


def _branch_from_passage(
    passage: FirstPassage,
    *,
    seed: int,
    generation: int,
    parent_id: int,
    child_id: int,
    callback_budget: int,
    rng_pair_id: int | None = None,
    antipodal_sign: int = 1,
) -> tuple[kernel.CheckpointState, float, str, str]:
    """Clone one in-memory checkpoint and install a charged tangent trial."""

    state = _copy_checkpoint(passage.checkpoint)
    state.terminal_status = None
    state.deadline_monotonic = math.inf
    state.max_callbacks = max(
        int(state.max_callbacks), int(state.charged_callbacks + callback_budget)
    )
    if antipodal_sign not in (-1, 1):
        raise ValueError("antipodal_sign must be -1 or 1")
    rng_identity = child_id if rng_pair_id is None else rng_pair_id
    rng, digest = _genealogy_rng(seed, generation, parent_id, rng_identity)
    tangent, tangent_source = _tangent_direction(state, rng)
    tangent *= float(antipodal_sign)
    if antipodal_sign < 0:
        digest = hashlib.sha256(f"{digest}:antipode".encode("ascii")).hexdigest()

    current = state.current
    if current is None or state.direct_model is None:
        raise RuntimeError("first-passage checkpoint has no resumable local model")
    radius = max(
        0.15,
        min(0.60, 0.75 * max(1.0e-5, float(state.trust_radius))),
    )
    # A log-uniform multiplier keeps the branch scale general while avoiding
    # a hidden family-specific radius.
    multiplier = float(10.0 ** rng.uniform(-0.12, 0.10))
    delta_z = tangent * radius * multiplier
    current_z = (np.asarray(current.x, dtype=float) - state.anchor) / state.variable_scale
    trial_z = np.minimum(np.maximum(current_z + delta_z, state.lower_z), state.upper_z)
    delta_z = trial_z - current_z
    norm_z = float(np.linalg.norm(delta_z))
    if not math.isfinite(norm_z) or norm_z <= 1.0e-14:
        raise RuntimeError("tangent perturbation collapsed at source bounds")

    state.pending_step = delta_z.copy()
    state.pending_delta_z = delta_z.copy()
    state.pending_trial_x = state.anchor + state.variable_scale * trial_z
    state.pending_step_norm = norm_z
    state.phase = "trial_evaluation"
    state.consecutive_rejections = 0
    state.consecutive_linear_failures = 0
    return state, norm_z, tangent_source, digest


def _new_trajectory(
    trajectory_id: int,
    runtime: StartRuntime,
    *,
    max_callbacks: int,
    rng_seed: int,
) -> Trajectory:
    configuration = replace(kernel.REFERENCE, rng_seed=int(rng_seed))
    state = kernel.create_checkpoint(
        runtime.case,
        runtime.program,
        configuration,
        runtime.start,
        source_binding_token=runtime.source_binding_token,
        per_start_scale=runtime.scale,
        source_lower=runtime.lower,
        source_upper=runtime.upper,
        max_callbacks=max_callbacks,
        deadline_monotonic=math.inf,
    )
    return Trajectory(
        trajectory_id=trajectory_id,
        root_trajectory_id=trajectory_id,
        parent_trajectory_id=None,
        generation=0,
        state=state,
    )


def _advance_charged(trajectory: Trajectory) -> tuple[bool, bool]:
    """Advance through at most one charged callback and bound free closure."""

    for _notice in range(8):
        event = kernel.advance_one(trajectory.state)
        if event.callback_ordinal is not None:
            trajectory.charged_here += 1
            if trajectory.relocation_pending:
                trajectory.relocation_pending = False
                record = trajectory.state.callback_ledger[-1]
                if not (
                    record.kind == "trial"
                    and record.succeeded
                    and record.semantics_valid
                ):
                    # Opaque/invalid mutations are never installed as a new
                    # local state.  The copied checkpoint has already applied
                    # its ordinary fail-closed trial handling.
                    return True, False
                raw_violation = np.asarray(record.raw_violation, dtype=float)
                violation = float(
                    np.max(np.maximum(0.0, raw_violation), initial=0.0)
                )
                relocated = kernel._AD._State(
                    np.asarray(record.point, dtype=float),
                    np.asarray(record.augmented, dtype=float),
                    np.asarray(record.raw_relation, dtype=float),
                    True,
                    violation,
                )
                state = trajectory.state
                state.current = relocated
                state.current_generation += 1
                state.objectives.append(float(relocated.objective))
                state.relation_norms.append(float(relocated.relation_inf))
                state.raw_cache_generation = None
                state.raw_cache_x = None
                state.raw_cache_augmented = None
                state.raw_cache_model = None
                state.raw_cache_fd_calls = 0
                state.jacobian_build = None
                # Candidate-private mutation reason: the frozen kernel's
                # diagnostic counter accepts only its closed mature reason
                # vocabulary, so request the refresh without forging one of
                # those counters.
                state.refresh_requested = True
                state.refresh_reasons.append("ams_tangent_relocation")
                state.phase = "iteration"
                state.terminal_status = None
            new_passage = _record_first_passage(trajectory)
            return True, new_passage
        if trajectory.state.terminal:
            return False, False
    raise RuntimeError("checkpoint kernel emitted an unbounded callback-free loop")


def run_ams_side(
    make_runtime: RuntimeFactory,
    *,
    replay: Replay,
    callback_budget: int,
    seed: int,
    population: int = 4,
    breadth_callbacks: int = 8,
    branch_quantum: int = 4,
) -> AMSResult:
    """Run target-free checkpoint-genealogical AMS inside a fixed side budget."""

    if callback_budget <= 0:
        raise ValueError("callback_budget must be positive")
    if population < 3 or breadth_callbacks < 1 or branch_quantum < 1:
        raise ValueError("invalid AMS population or quantum")

    trajectories = [
        _new_trajectory(
            index,
            make_runtime(index),
            max_callbacks=max(64, callback_budget),
            rng_seed=seed * 1009 + index,
        )
        for index in range(population)
    ]
    next_id = population
    charged = 0
    generation = 0
    genealogy: list[GenealogyEvent] = []
    endpoints: list[np.ndarray] = []
    safe: list[np.ndarray] = []
    invalid = 0
    replay_rejections = 0

    def capture(trajectory: Trajectory) -> None:
        nonlocal replay_rejections
        state = trajectory.state
        seen: set[bytes] = set()
        for endpoint in (state.current, state.best):
            if endpoint is None:
                continue
            point = np.asarray(endpoint.x, dtype=float).copy()
            key = point.tobytes()
            if key in seen:
                continue
            seen.add(key)
            endpoints.append(point)
            try:
                accepted = bool(replay(point))
            except Exception:
                accepted = False
            if accepted:
                safe.append(point)
            else:
                replay_rejections += 1

    # Mandatory breadth: every trajectory receives the same first service.
    for _round in range(breadth_callbacks):
        for trajectory in trajectories:
            if charged >= callback_budget:
                break
            did_charge, _new = _advance_charged(trajectory)
            if did_charge:
                charged += 1
                capture(trajectory)
            elif trajectory.state.terminal:
                capture(trajectory)
        if charged >= callback_budget:
            break

    while charged < callback_budget:
        live = [item for item in trajectories if item.first_passages]
        if len(live) < 2:
            # No usable genealogy: spend real work on a fresh source start.
            victim = min(trajectories, key=lambda item: item.trajectory_id)
            replacement = _new_trajectory(
                next_id,
                make_runtime(next_id),
                max_callbacks=max(64, callback_budget),
                rng_seed=seed * 1009 + next_id,
            )
            next_id += 1
            trajectories[trajectories.index(victim)] = replacement
        else:
            ranked = sorted(
                live,
                key=lambda item: (
                    item.maximum_score,
                    item.generation,
                    item.trajectory_id,
                ),
            )
            # k=2 AMS mutation: an antipodal pair removes the arbitrary sign
            # of an SVD tangent and makes reflection/permutation metamorphics
            # deterministic as a set.  Each member is still one of the
            # lowest-score trajectories and is cloned from the same first
            # crossing above the killed batch's attained level.
            kill_count = min(2, len(ranked) - 1)
            killed_batch = ranked[:kill_count]
            level = killed_batch[-1].maximum_score
            killed_ids = {item.trajectory_id for item in killed_batch}
            parents = [
                item
                for item in live
                if item.trajectory_id not in killed_ids
                and _first_crossing(item, level) is not None
            ]
            if not parents:
                # Equal/opaque scores provide no valid AMS selection signal.
                victim = killed_batch[0]
                replacement = _new_trajectory(
                    next_id,
                    make_runtime(next_id),
                    max_callbacks=max(64, callback_budget),
                    rng_seed=seed * 1009 + next_id,
                )
                next_id += 1
                trajectories[trajectories.index(victim)] = replacement
            else:
                generation += 1
                selector, _selector_digest = _genealogy_rng(
                    seed, generation, killed_batch[0].trajectory_id, next_id
                )
                parent = parents[int(selector.integers(0, len(parents)))]
                passage = _first_crossing(parent, level)
                if passage is None:
                    raise AssertionError("selected parent has no level crossing")
                pair_id = next_id
                for pair_index, killed in enumerate(killed_batch):
                    child_id = next_id
                    try:
                        child_state, norm_z, tangent_source, rng_digest = (
                            _branch_from_passage(
                                passage,
                                seed=seed,
                                generation=generation,
                                parent_id=parent.trajectory_id,
                                child_id=child_id,
                                callback_budget=callback_budget,
                                rng_pair_id=pair_id,
                                antipodal_sign=1 if pair_index == 0 else -1,
                            )
                        )
                    except (
                        ArithmeticError,
                        RuntimeError,
                        ValueError,
                        np.linalg.LinAlgError,
                    ):
                        invalid += 1
                        child = _new_trajectory(
                            child_id,
                            make_runtime(child_id),
                            max_callbacks=max(64, callback_budget),
                            rng_seed=seed * 1009 + child_id,
                        )
                    else:
                        child = Trajectory(
                            trajectory_id=child_id,
                            root_trajectory_id=parent.root_trajectory_id,
                            parent_trajectory_id=parent.trajectory_id,
                            generation=generation,
                            state=child_state,
                            first_passages=[
                                FirstPassage(
                                    item.score,
                                    item.callback_ordinal,
                                    item.accepted_generation,
                                    _copy_checkpoint(item.checkpoint),
                                )
                                for item in parent.first_passages
                                if item.score <= passage.score
                            ],
                            maximum_score=passage.score,
                            last_generation_seen=int(child_state.current_generation),
                            relocation_pending=True,
                        )
                        genealogy.append(
                            GenealogyEvent(
                                generation,
                                killed.trajectory_id,
                                parent.trajectory_id,
                                child_id,
                                level,
                                passage.callback_ordinal,
                                norm_z,
                                tangent_source,
                                rng_digest,
                            )
                        )
                    next_id += 1
                    trajectories[trajectories.index(killed)] = child

        # All active descendants receive a small post-branch continuation.
        for _round in range(branch_quantum):
            for trajectory in tuple(trajectories):
                if charged >= callback_budget:
                    break
                if trajectory.state.terminal:
                    continue
                did_charge, _new = _advance_charged(trajectory)
                if did_charge:
                    charged += 1
                    capture(trajectory)
                elif trajectory.state.terminal:
                    capture(trajectory)
            if charged >= callback_budget:
                break

        # If every descendant is terminal, the next loop will create fresh
        # source work rather than using padding callbacks.

    first_passage_count = sum(len(item.first_passages) for item in trajectories)
    return AMSResult(
        status="UNKNOWN",
        charged_callbacks=charged,
        callback_budget=callback_budget,
        trajectories_created=next_id,
        genealogy=tuple(genealogy),
        endpoints=tuple(endpoints),
        replayed_safe_endpoints=tuple(safe),
        maximum_scores=tuple(item.maximum_score for item in trajectories),
        first_passage_count=first_passage_count,
        invalid_or_opaque_events=invalid,
        source_replay_rejections=replay_rejections,
    )


def configuration_manifest() -> Mapping[str, object]:
    return {
        "schema_version": SCHEMA,
        "baseline_callback_floor": BASELINE_FLOOR,
        "ams_side_callback_ceiling": SIDE_CEILING,
        "score": "semantic-validity then max first-passage -log10(norm(F)+violation+floor)",
        "genealogy_state": [
            "parent/root trajectory ids",
            "RNG key digest",
            "first checkpoint crossing each attained level",
        ],
        "branch": (
            "k=2 clone of a survivor's same-level first-passage checkpoint; "
            "charge an antipodal scaled weak-right-singular tangent mutation, "
            "install only semantic-valid relocation, then rebuild the local model"
        ),
        "checkpoint_serialization": False,
        "common_checkpoint_or_scheduler_framework": False,
        "problem_family_truth_target_count_routing": False,
        "final_source_replay_required": True,
    }
