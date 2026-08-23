from geosolver.exact import describe_exact


def test_radian_angle_is_affine_pi() -> None:
    answer = describe_exact("pi/2")

    assert answer.kind == "affine_pi"
    assert answer.pi_coefficient == "1/2"
    assert answer.constant == "0"


def test_degree_conversion_is_algebraic() -> None:
    answer = describe_exact("90")

    assert answer.kind == "algebraic"
    assert answer.minimal_polynomial == ["1", "-90"]
