"""Continue the frozen SFT recipe from update 32 to fixed update 128.

Only extends the permitted update count; the original trainer performs all
checkpoint, optimizer, data-order, gradient and serialization checks.
"""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
ORIGINAL = HERE.parent / "program-self-training-2026-09-26/train_sft.py"
EXPECTED_SHA = "f525e7626bae22109753cd5a8deac47b94cd13f4bd4dcc13960543b4607b9857"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--preflight", action="store_true")
    args = ap.parse_args()
    assert hashlib.sha256(ORIGINAL.read_bytes()).hexdigest() == EXPECTED_SHA
    sys.path.insert(0, str(ORIGINAL.parent))
    spec = importlib.util.spec_from_file_location("frozen_sft_trainer", ORIGINAL)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    original_parameters = module.parameters

    def extended_parameters(config):
        if config.get("updates") != 128 or not config.get("prior_checkpoint"):
            raise ValueError("This extension requires fixed 128 updates from a saved checkpoint")
        prior = json.loads((Path(config["prior_checkpoint"]) / "receipt.json").read_text())
        if prior["global_updates"] != 32:
            raise ValueError("This study continues only update 32")
        return original_parameters(dict(config, updates=32))

    module.parameters = extended_parameters
    module.run(args)


if __name__ == "__main__":
    main()
