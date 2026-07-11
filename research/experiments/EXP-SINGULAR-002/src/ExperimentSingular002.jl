module ExperimentSingular002

using LinearAlgebra

export InvariantDiagnosticOptions,
       JacobianPairEvidence,
       RankCertificate,
       ProjectorStability,
       TensorCertificate,
       CovariantLineCertificate,
       ContractedLineEvidence,
       CrossPrecisionLineEvidence,
       CrossPrecisionContractionEvidence,
       NullTrial,
       EndpointReconciliation,
       acquire_normalized_jacobian_pair,
       certify_weyl_rank,
       certify_covariant_lines,
       certify_contracted_lines,
       contracted_operator,
       covariant_contraction,
       cross_precision_contractions,
       cross_precision_lines,
       declared_metric_maps,
       normalized_jacobian,
       paper_two_step_null_trials,
       projected_hessian_tensor,
       projector_stability,
       reconcile_signed_endpoints,
       symmetric_projected_operator,
       certify_projected_tensor

include("invariant_diagnostics.jl")

end
