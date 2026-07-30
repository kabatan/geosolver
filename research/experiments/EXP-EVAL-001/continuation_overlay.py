"""Monkey-patch seam for evaluating EXP-EVAL-001 against pinned product code."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from incremental_reservoir import FrozenChampionAdapter, incremental_candidates


def install(continuation_module: Any) -> None:
    """Replace only ``continuation._all_candidates``.

    The overlay is intentionally candidate-local.  It leaves canonical replay,
    HP service, exactification, scheduling, search and public result generation
    untouched.  A v1/unknown checkpoint is a clean miss and therefore receives
    one frozen full replay before a v2 checkpoint is committed.
    """

    if getattr(continuation_module, "_exp_eval_001_installed", False):
        return
    original = continuation_module._all_candidates

    def append_aware_all_candidates(
        base: Any,
        source_document: dict[str, Any],
        search: dict[str, Any],
        deadline: float,
        *,
        source_sha256: str | None = None,
        checkpoint_input: Path | None = None,
        checkpoint_output: Path | None = None,
    ):
        if source_sha256 is None:
            return original(
                base,
                source_document,
                search,
                deadline,
                source_sha256=source_sha256,
                checkpoint_input=checkpoint_input,
                checkpoint_output=checkpoint_output,
            )
        adapter = FrozenChampionAdapter(base)
        outcome = incremental_candidates(
            adapter=adapter,
            source_document=source_document,
            search=search,
            source_sha256=source_sha256,
            checkpoint_input=checkpoint_input,
            checkpoint_output=checkpoint_output,
            hard_deadline=min(
                deadline,
                __import__("time").monotonic() + base.SELECTION_RESERVE_SECONDS,
            ),
            candidate_type=adapter.candidate_type,
            reservoir_type=adapter.reservoir_type,
        )
        base._geotarget_incremental_reservoir_telemetry = {
            "schema_version": "geotarget.exp-eval-001-telemetry/v1",
            "mode": outcome.mode,
            "covered_endpoint_count": outcome.covered_endpoint_count,
            "semantic_replay_count": outcome.semantic_replay_count,
            "reused_verified_count": outcome.reused_verified_count,
            "retried_backlog_count": outcome.retried_backlog_count,
            "retried_unobserved_count": outcome.retried_unobserved_count,
            "exact_authority_modified": False,
        }
        return outcome.reservoir

    continuation_module._all_candidates = append_aware_all_candidates
    continuation_module._exp_eval_001_installed = True
