import pytest

from qwen.answer_check import answers_equal, extract_answer, parse_numeric


@pytest.mark.parametrize(
    ("answer", "expected"),
    [
        (r"\dfrac{5\sqrt{7}}{2}", "5*sqrt(7)/2"),
        (r"\frac{2\sqrt{74}}{7}", "2*sqrt(74)/7"),
        (r"\frac{\frac{1}{2}}{\sqrt{\frac{9}{4}}}", "1/3"),
        (r"\sqrt[3]{8}", "2"),
        (r"\frac{-3+\sqrt{9}}{2}", "0"),
        (r"\left(\frac{2}{3}\right)^2", "4/9"),
        ("(9/5)√5", "9/sqrt(5)"),
        ("0.125", "1/8"),
        ("1e-5", "1/100000"),
        ("-2^2", "-4"),
        ("2^-2", "1/4"),
    ],
)
def test_exact_nested_numeric_answers(answer, expected):
    extracted = extract_answer(r"\boxed{" + answer + "}")
    assert answers_equal(extracted, expected) is True


@pytest.mark.parametrize(
    "raw",
    [
        r"<think>The intermediate result is \boxed{4}",
        r"\boxed{4} Later I revise it: \boxed{\frac{",
        r"\boxed{\unknown{4}}",
        r"\boxed{4\text{ or }5}",
        "I cannot solve this, but one length is 4.",
        "x = 4",
        r"\boxed{\sqrt{-1}}",
        r"\boxed{\frac{1}{0}}",
        r"\boxed{\frac{0}{0}}",
        r"\boxed{x}",
    ],
)
def test_unsupported_or_uncommitted_answers_are_not_guessed(raw):
    assert extract_answer(raw) is None


def test_only_committed_final_answer_counts():
    assert answers_equal(extract_answer(r"<think>\boxed{4}</think>\boxed{5}"), "5")
    assert answers_equal(extract_answer(r"\boxed{4} Therefore \boxed{5}"), "4") is False
    assert answers_equal(extract_answer("Final Answer: 5"), "5") is True


def test_no_tolerance_accepts_nonzero_as_zero():
    assert answers_equal("1e-25", "0") is False
    assert answers_equal("0.3333333333333333", "1/3") is False
    assert answers_equal("sqrt(8)/2", "sqrt(2)") is True


def test_training_reward_uses_the_same_correct_parser():
    from qwen.grpo_segment import numeric_reward

    completions = [
        [{"content": r"\boxed{\frac{5\sqrt{7}}{2}}"}],
        [{"content": r"\boxed{10\sqrt{7}}"}],
        [{"content": r"<think>Maybe \boxed{\frac{5\sqrt{7}}{2}}"}],
    ]
    assert numeric_reward(completions, ["5*sqrt(7)/2"] * 3) == [1.0, 0.0, 0.0]


def test_invalid_label_fails_instead_of_quietly_rewarding():
    with pytest.raises(ValueError):
        answers_equal("4", "unknown")
    with pytest.raises(ValueError):
        parse_numeric("__import__('os')")
