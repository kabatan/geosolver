"""Stdlib-only benchmark and research safety harness for GeoTarget."""

from .bootstrap import (
    BootstrapPlan,
    BootstrapResult,
    ClusteredValue,
    PairedValue,
    family_clustered_lower_bound,
    family_clustered_paired_bootstrap,
    load_bootstrap_plan,
    make_bootstrap_plan,
    save_bootstrap_plan,
)
from .matching import RunEvaluation, evaluate_run
from .metrics import (
    AggregateMetrics,
    PrefixMonotonicity,
    StabilityReport,
    aggregate_metrics,
    prefix_monotonicity,
    stability_27_of_30,
)
from .models import CaseInput, InputError, RunInput, parse_case_input, parse_run_input
from .partitions import (
    AccessMode,
    BurnRecord,
    Partition,
    PartitionAccessError,
    PartitionRecord,
    PartitionRegistry,
    PartitionStatus,
)

__all__ = [
    "AccessMode",
    "AggregateMetrics",
    "BootstrapPlan",
    "BootstrapResult",
    "BurnRecord",
    "CaseInput",
    "ClusteredValue",
    "InputError",
    "PairedValue",
    "Partition",
    "PartitionAccessError",
    "PartitionRecord",
    "PartitionRegistry",
    "PartitionStatus",
    "PrefixMonotonicity",
    "RunEvaluation",
    "RunInput",
    "StabilityReport",
    "aggregate_metrics",
    "evaluate_run",
    "family_clustered_lower_bound",
    "family_clustered_paired_bootstrap",
    "load_bootstrap_plan",
    "make_bootstrap_plan",
    "parse_case_input",
    "parse_run_input",
    "prefix_monotonicity",
    "save_bootstrap_plan",
    "stability_27_of_30",
]
