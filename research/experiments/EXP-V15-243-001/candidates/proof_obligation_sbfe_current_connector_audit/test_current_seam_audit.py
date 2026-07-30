from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

import current_seam_audit as seam


class ProofObligationCurrentSeamAuditTest(unittest.TestCase):
    def test_hash_bound_current_seam_stops_before_connector(self) -> None:
        result = seam.audit()
        self.assertTrue(result["hash_binding_valid"])
        self.assertEqual(result["decision"], "STOP_BEFORE_CONNECTOR")
        self.assertFalse(result["connector_created"])
        self.assertFalse(result["generated_or_dry_connector_integration_run"])
        self.assertFalse(result["rung_cache_species_order_changed"])

    def test_exact_outer_is_sequential_compound_not_predispatch_or(self) -> None:
        exact = seam.audit()["exact_outer"]
        self.assertTrue(exact["ordinary_runs_before_fallback_selection"])
        self.assertTrue(exact["confirm_all_ready_requires_exact_fallback"])
        self.assertTrue(exact["execution_caps_present"])
        self.assertTrue(exact["terminal_outcome_available_only_after_dispatch"])
        self.assertFalse(exact["predispatch_proof_graph_abi_present"])
        self.assertFalse(exact["heterogeneous_or_exposed_before_ordinary_work"])

    def test_hp_and_cross_endpoint_do_not_export_proof_graph(self) -> None:
        result = seam.audit()
        hp = result["hp_lock"]
        cross = result["cross_endpoint"]
        self.assertTrue(hp["resource_lease_only"])
        self.assertTrue(hp["terminal_evidence_is_posthoc"])
        self.assertFalse(hp["predispatch_proof_graph_abi_present"])
        self.assertTrue(cross["endpoint_fifo"])
        self.assertTrue(cross["one_runner_one_backend_chain_per_dispatch"])
        self.assertTrue(cross["terminal_outcome_is_posthoc"])
        self.assertFalse(cross["descriptor_obligation_in_rung_request"])
        self.assertFalse(cross["proof_route_costs_exported"])
        self.assertFalse(cross["shared_prerequisites_exported"])
        self.assertFalse(cross["bound_into_current_exact_worker"])

    def test_only_two_route_artifact_is_noncurrent_prototype(self) -> None:
        routes = seam.audit()["alternate_route_audit"]
        self.assertTrue(routes["generated_prototype_has_coordinate_and_source_link_routes"])
        self.assertTrue(routes["breadth_worker_declares_only_one_current_route"])
        self.assertFalse(routes["prototype_is_current_exact_outer_backend"])
        self.assertEqual(routes["current_callable_heterogeneous_or_route_count"], 0)

    def test_budget_fails_but_canonical_and_zero_authority_are_intact(self) -> None:
        result = seam.audit()
        budget = result["budget_and_first_service"]
        authority = result["authority"]
        self.assertTrue(
            budget[
                "current_search_has_25_percent_original_order_and_25_percent_cauchy_insurance"
            ]
        )
        self.assertFalse(
            budget["that_search_insurance_is_a_75_percent_byte_identical_authority_queue"]
        )
        self.assertFalse(budget["baseline_byte_identity_and_first_service_hook_present"])
        self.assertTrue(authority["canonical_exact_outer_worker_present"])
        self.assertTrue(authority["zero_dimensional_object_and_route_identity_preserved"])
        self.assertFalse(authority["scheduler_would_emit_authority_directly"])
        self.assertEqual(result["activation"]["observed_anonymous_structural_strata"], 0)
        self.assertFalse(result["activation"]["problem_sources_or_results_opened"])

    def test_hash_tamper_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as name:
            changed = Path(name) / "changed.py"
            changed.write_text("# changed\n", encoding="utf-8")
            paths = dict(seam.PATHS)
            paths["exact_outer"] = changed
            result = seam.audit(paths)
        self.assertFalse(result["hash_binding_valid"])
        self.assertEqual(result["decision"], "STOP_BEFORE_CONNECTOR")


if __name__ == "__main__":
    unittest.main()
