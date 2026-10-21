#!/usr/bin/env python3
"""Merge a trained LoRA adapter into the base Qwen3-4B snapshot in FP32.

The output must also be loaded in FP32. The legacy diagnostics BF16 loader
does not preserve the measured adapter signal. Prefer grpo_evaluate --adapter
for formal comparisons, which does not need a standalone merged directory.
"""

import argparse
import json
import os
import sys
from pathlib import Path

os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
sys.path.insert(0, str(REPO))

from qwen.models import locked_models  # noqa: E402


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--adapter", required=True, help="LoRA adapter directory")
    parser.add_argument("--output", required=True, help="merged model output directory")
    args = parser.parse_args()

    import torch
    from peft import PeftModel
    from transformers import AutoModelForCausalLM, AutoTokenizer

    snapshot = locked_models()["qwen3_4b"]["snapshot_path"]
    out = Path(args.output)
    if out.exists() and any(out.iterdir()):
        raise ValueError("Refusing to overwrite an existing model directory")
    model = AutoModelForCausalLM.from_pretrained(
        snapshot, dtype=torch.float32, local_files_only=True
    )
    model = PeftModel.from_pretrained(model, args.adapter)
    model = model.merge_and_unload(safe_merge=True)

    out.mkdir(parents=True, exist_ok=True)
    model.save_pretrained(str(out))
    tokenizer = AutoTokenizer.from_pretrained(snapshot, local_files_only=True)
    tokenizer.save_pretrained(str(out))
    print(json.dumps({"merged": str(out), "adapter": args.adapter}))


if __name__ == "__main__":
    main()
