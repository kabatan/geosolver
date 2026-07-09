module GeoTargetCore

using GeoTargetBase
using LinearAlgebra

const CORE_ABI_VERSION = v"1.0.0"

include("errors.jl")
include("registry.jl")
include("validation.jl")
include("oracle.jl")
include("reference_interpreter.jl")
include("local_solver.jl")

"""Return the stable plugin ABI version understood by this Core build."""
abi_version() = CORE_ABI_VERSION

export CORE_ABI_VERSION,
    abi_version,
    CoreError,
    RegistryError,
    ProblemValidationError,
    RegistryBuilder,
    FrozenPluginRegistry,
    register!,
    freeze,
    registered_plugins,
    resolve_type,
    resolve_operation,
    resolve_selector,
    OperationRole,
    ROLE_PRIMITIVE,
    ROLE_RELATION,
    ROLE_GUARD,
    ROLE_DOMAIN,
    ROLE_BRANCH,
    ValidationIssue,
    ValidationReport,
    validate_problem,
    require_valid_problem,
    node_type,
    RelationObservation,
    GuardObservation,
    DomainObservation,
    BranchObservation,
    OracleObservation,
    residual_values,
    scaled_residual_values,
    canonical_feasible,
    evaluate_reference,
    LocalSolveStatus,
    LOCAL_CONVERGED,
    LOCAL_MAX_ITERATIONS,
    LOCAL_MAX_EVALUATIONS,
    LOCAL_DEADLINE,
    LOCAL_CANCELLED,
    LOCAL_NO_PROGRESS,
    LOCAL_EVALUATION_FAILED,
    LocalSolveOptions,
    LocalTracePoint,
    LocalAttempt,
    solve_local

end
