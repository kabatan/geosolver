import hashlib

import pytest

from candidate import prove_multi_target_identity, squarefree_product


def _sha(label: str) -> str:
    return hashlib.sha256(label.encode()).hexdigest()


def test_squarefree_product_deduplicates_factors() -> None:
    assert squarefree_product([[2, -2], [1, 1]]) == (1, 0, -1)


def test_duplicate_or_scaled_equivalent_factors_reject() -> None:
    with pytest.raises(ValueError, match="distinct primitive factors"):
        squarefree_product([[1, -1], [2, -2]])


def test_product_proves_all_components_where_one_factor_does_not() -> None:
    result = prove_multi_target_identity(
        variables=["x"],
        active_equations=["(x-1)*(x**2-2)"],
        all_equations=["(x-1)*(x**2-2)"],
        target_expression="x",
        factors_high_to_low=[[1, -1], [1, 0, -2]],
        descriptor_artifact_sha256s=[_sha("rational"), _sha("quadratic")],
        source_sha256=_sha("source-positive"),
    )
    assert result["status"] == "IDENTITY_VERIFIED"
    assert result["proposal_authority"] is False
    assert result["target_set_completeness_claim"] is False


def test_missing_component_fails_closed() -> None:
    result = prove_multi_target_identity(
        variables=["x"],
        active_equations=["(x-1)*(x**2-2)"],
        all_equations=["(x-1)*(x**2-2)"],
        target_expression="x",
        factors_high_to_low=[[1, 0, -2], [1, -3]],
        descriptor_artifact_sha256s=[_sha("quadratic"), _sha("wrong-linear")],
        source_sha256=_sha("source-negative"),
    )
    assert result["status"] == "NOT_PROVED"
    assert result["exact_identity_verified"] is False
