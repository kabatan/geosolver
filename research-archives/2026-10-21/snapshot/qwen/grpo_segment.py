"""Compatibility reward import; the exp01 TRL runner has been retired.

The archived implementation is retained under exp01/source_before_repair_20260922.
Use ``python -m qwen.grpo_run --config ... --output ...`` for validated runs.
"""

from .answer_check import answers_equal, extract_answer


def numeric_reward(completions, answer_exact, **kwargs):
    rewards = []
    for completion, expected in zip(completions, answer_exact, strict=True):
        text = completion[-1]["content"] if isinstance(completion, list) else completion
        rewards.append(float(answers_equal(extract_answer(text), expected) is True))
    return rewards


def main():
    raise SystemExit(
        "The exp01 TRL runner is retired: its normalization and BF16 synchronization "
        "were not faithful. Use python -m qwen.grpo_run --config "
        "qwen/configs/exp03_pilot.json --output qwen/.runtime/exp03_pilot . "
        "See docs/research/exp02-technical-results-2026-09-22.md."
    )


if __name__ == "__main__":
    main()
