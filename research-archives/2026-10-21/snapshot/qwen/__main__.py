"""CLI entry: download, doctor, infer."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .common import now, write_json
from .doctor import run as doctor_run
from .inference import infer
from .models import ensure_models

DEFAULT_SYSTEM = "You are a helpful assistant."


def main():
    parser = argparse.ArgumentParser(prog="qwen")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("download", help="Resolve, download and hash-verify the pinned model")

    p_doctor = sub.add_parser("doctor", help="Environment diagnostics on GPU")
    p_doctor.add_argument("--kv-tokens", type=int, default=32768)
    p_doctor.add_argument("--smoke-max-new-tokens", type=int, default=512)
    p_doctor.add_argument("--output", type=Path, help="Also save the report JSON here")

    p_infer = sub.add_parser("infer", help="Single chat inference on arbitrary text")
    src = p_infer.add_mutually_exclusive_group()
    src.add_argument("--prompt", type=str, help="User message text")
    src.add_argument("--file", type=Path, help="Read the user message from a file")
    p_infer.add_argument("--system", type=str, default=DEFAULT_SYSTEM)
    p_infer.add_argument("--model-key", type=str, default="qwen3_4b")
    p_infer.add_argument("--seed", type=int, default=0)
    p_infer.add_argument("--max-new-tokens", type=int, default=32768)
    p_infer.add_argument("--context-limit", type=int, default=32768)
    p_infer.add_argument("--temperature", type=float, default=0.6)
    p_infer.add_argument("--top-p", type=float, default=0.95)
    p_infer.add_argument("--top-k", type=int, default=20)
    p_infer.add_argument("--wall-seconds", type=float, default=900)
    p_infer.add_argument("--output", type=Path, help="Also save the result JSON here")

    args = parser.parse_args()

    if args.command == "download":
        ensure_models()
        return

    if args.command == "doctor":
        report = doctor_run(
            kv_tokens=args.kv_tokens, smoke_max_new_tokens=args.smoke_max_new_tokens
        )
        text = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
        sys.stdout.write(text)
        if args.output:
            write_json(args.output, report)
        return

    if args.command == "infer":
        if args.file is not None:
            prompt = args.file.read_text(encoding="utf-8")
        elif args.prompt is not None:
            prompt = args.prompt
        else:
            prompt = sys.stdin.read()
        result = infer(
            {
                "model_key": args.model_key,
                "system": args.system,
                "prompt": prompt,
                "seed": args.seed,
                "max_new_tokens": args.max_new_tokens,
                "context_limit": args.context_limit,
                "temperature": args.temperature,
                "top_p": args.top_p,
                "top_k": args.top_k,
                "wall_seconds": args.wall_seconds,
            }
        )
        record = {"utc": now(), **result}
        text = json.dumps(record, ensure_ascii=False, indent=2) + "\n"
        sys.stdout.write(text)
        if args.output:
            write_json(args.output, record)
        return


if __name__ == "__main__":
    main()
