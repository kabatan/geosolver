import sympy as sp

import run_real_census as census


def test_exact_sos_search_recovers_direct_and_square_miss():
    x, y = sp.symbols("x y", real=True)
    equations = (x**2 + y**2,)
    basis = sp.groebner(equations, x, y, order="grevlex", domain=sp.QQ)
    assert census._zero(basis.reduce(x)[1]) is False
    assert census._zero(basis.reduce(x**2)[1]) is False
    found = census._search((x, y), equations, x, sp.Rational(0), basis)
    assert found is not None
    m, gram = found
    assert m == 1
    assert census._psd_exact(gram)


def test_aggregate_output_has_no_individual_evidence_fields():
    result = census._summarize([])
    assert set(result) == {
        "schema_version", "counts", "anonymous_identity_typed_static_signature_count",
        "gate", "authority", "target_release", "individual_records_emitted",
    }
    payload = str(result).lower()
    assert all(word not in payload for word in ("source_path", "witness", "reason", "target_q"))
    assert result["authority"] is False
    assert result["target_release"] is False
