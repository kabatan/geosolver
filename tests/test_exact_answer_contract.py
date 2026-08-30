from geosolver.exact import describe_exact


def test_radian_angle_is_affine_pi() -> None:
    answer = describe_exact("pi/2")

    assert answer.kind == "affine_pi"
    assert answer.pi_coefficient.minimal_polynomial == ["2", "-1"]
    assert answer.constant.minimal_polynomial == ["1", "0"]


def test_degree_conversion_is_algebraic() -> None:
    answer = describe_exact("90")

    assert answer.kind == "algebraic"
    assert answer.minimal_polynomial == ["1", "-90"]


def test_affine_pi_accepts_real_algebraic_coefficients() -> None:
    answer = describe_exact("sqrt(2) * pi + sqrt(3)")

    assert answer.kind == "affine_pi"
    assert answer.pi_coefficient.minimal_polynomial == ["1", "0", "-2"]
    assert answer.constant.minimal_polynomial == ["1", "0", "-3"]
