"""Map text-only HF PEFT names to vLLM's conditional-generation wrapper."""
import argparse
import json
from pathlib import Path

from safetensors import safe_open
from safetensors.torch import save_file

from qwen.common import file_hash, now, write_json

OLD = "base_model.model.model.layers."
NEW = "base_model.model.model.language_model.layers."


def main(args):
    source = Path(args.source)
    target = Path(args.target)
    target.mkdir(parents=True, exist_ok=False)
    input_path = source / "adapter_model.safetensors"
    tensors = {}
    with safe_open(input_path, framework="pt", device="cpu") as handle:
        metadata = handle.metadata()
        for key in handle.keys():
            assert key.startswith(OLD), key
            mapped = NEW + key[len(OLD):]
            assert mapped not in tensors
            tensors[mapped] = handle.get_tensor(key)
    assert len(tensors) == 400
    save_file(tensors, target / "adapter_model.safetensors", metadata=metadata)
    (target / "adapter_config.json").write_bytes((source / "adapter_config.json").read_bytes())
    write_json(target / "mapping-receipt.json", dict(created_utc=now(), source=str(source),
               source_sha256=file_hash(input_path), mapped_sha256=file_hash(target / "adapter_model.safetensors"),
               n_tensors=len(tensors), old_prefix=OLD, new_prefix=NEW,
               rationale="vLLM loads the original Qwen3.5-9B as Qwen3_5ForConditionalGeneration; its language model sits under language_model.model. The PEFT checkpoint came from the text-only class with model.layers."))
    print(json.dumps(dict(target=str(target), n_tensors=len(tensors),
                          sha256=file_hash(target / "adapter_model.safetensors"))))


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--source", required=True)
    p.add_argument("--target", required=True)
    main(p.parse_args())
