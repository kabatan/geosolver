"""Download the official safetensors snapshot and pin its immutable revision."""

from __future__ import annotations

import os
from pathlib import Path

from .common import MANIFEST, file_hash, now, read_json, require, write_json

MODEL_IDS = {
    "qwen3_4b": "Qwen/Qwen3-4B",
}


def ensure_models():
    # Do not inherit an optional downloader selected by an unrelated environment.
    os.environ["HF_HUB_ENABLE_HF_TRANSFER"] = "0"
    from huggingface_hub import HfApi, snapshot_download

    manifest = read_json(MANIFEST) if MANIFEST.exists() else {"models": {}}
    api = HfApi()
    for key, model_id in MODEL_IDS.items():
        if key not in manifest["models"]:
            info = api.model_info(model_id)
            manifest["models"][key] = {
                "model_id": model_id,
                "revision": info.sha,
                "resolved_utc": now(),
            }
            write_json(MANIFEST, manifest)
        entry = manifest["models"][key]
        require(entry["model_id"] == model_id, "Unexpected model id in the model lock")
        print(f"Downloading {model_id} at {entry['revision']}", flush=True)
        location = Path(
            snapshot_download(
                model_id,
                revision=entry["revision"],
                max_workers=4,
                allow_patterns=["*.json", "*.safetensors", "*.model", "*.txt", "*.jinja"],
            )
        )
        files = sorted(p for p in location.rglob("*") if p.is_file())
        require(any(p.suffix == ".safetensors" for p in files), "No safetensors weights found")
        require((location / "tokenizer_config.json").exists(), "Missing tokenizer config")
        entry["snapshot_path"] = str(location)
        entry["files"] = {str(p.relative_to(location)): file_hash(p) for p in files}
        entry["bytes"] = sum(p.stat().st_size for p in files)
        entry["download_verified_utc"] = now()
        write_json(MANIFEST, manifest)
        print(f"Verified {key}: {len(files)} files, {entry['bytes']} bytes", flush=True)
    return manifest


def locked_models(verify_weights=False):
    manifest = read_json(MANIFEST)
    require(set(manifest["models"]) == set(MODEL_IDS), "Models are not fully downloaded")
    for key, entry in manifest["models"].items():
        require(entry["model_id"] == MODEL_IDS[key], "Unexpected model identity")
        location = Path(entry["snapshot_path"])
        for name, expected in entry["files"].items():
            path = location / name
            require(path.is_file(), f"Missing model file: {path}")
            if verify_weights or path.suffix != ".safetensors":
                require(file_hash(path) == expected, f"Changed model file: {path}")
    return manifest["models"]
