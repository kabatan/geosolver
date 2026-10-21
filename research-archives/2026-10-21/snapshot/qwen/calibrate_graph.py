"""Bounded CUDA-graph candidate probe, preserving the production engine settings."""

import sys
from pathlib import Path
from unittest.mock import patch


def main():
    import vllm

    from .common import write_json
    from .grpo_stage import main as stage_main

    real_llm = vllm.LLM
    output = Path(sys.argv[sys.argv.index("--output") + 1])

    def candidate(**kwargs):
        kwargs["enforce_eager"] = False
        kwargs["compilation_config"] = {
            "mode": 0,
            "cudagraph_mode": "FULL_DECODE_ONLY",
            "cudagraph_capture_sizes": [1, 2, 4],
        }
        write_json(output / "effective_engine_settings.json", kwargs)
        return real_llm(**kwargs)

    with patch("vllm.LLM", candidate):
        stage_main()


if __name__ == "__main__":
    main()
