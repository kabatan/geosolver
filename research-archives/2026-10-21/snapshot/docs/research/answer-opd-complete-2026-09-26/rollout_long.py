"""Long completion wrapper for the frozen answer-conditioned rollout driver.

Keeps prompts, seeds and checkpoint identity checks. Only raises the generation
bounds and allows retrying selected IDs from the same batch at the longer cap.
"""
import argparse
import hashlib
import importlib.util
from pathlib import Path

HERE = Path(__file__).resolve().parent
ORIGINAL = HERE.parent / "answer-opd-pilot-2026-09-26/rollout_worker.py"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True)
    ap.add_argument("--pool", required=True)
    ap.add_argument("--round", type=int, required=True)
    ap.add_argument("--start-index", type=int, required=True)
    ap.add_argument("--checkpoint")
    ap.add_argument("--out")
    ap.add_argument("--preflight", action="store_true")
    ap.add_argument("--only-id", action="append", default=[])
    args = ap.parse_args()
    spec = importlib.util.spec_from_file_location("frozen_opd_rollout", ORIGINAL)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    original_settings, original_prepare = module.rollout_settings, module.prepare

    def extended_settings(config):
        r = dict(config["rollout"])
        if (r["generation_max_tokens"], r["max_model_len"]) not in ((32768, 40960), (81920, 98304)):
            raise ValueError("Only the two fixed long-generation budgets are allowed")
        original_settings(dict(config, rollout=dict(r, generation_max_tokens=4096, max_model_len=8192)))
        return r

    def prepared_subset(options):
        value = original_prepare(options)
        if options.only_id:
            wanted = set(options.only_id)
            if len(wanted) != len(options.only_id) or not wanted <= {j["id"] for j in value["jobs"]}:
                raise ValueError("Retry IDs must be unique members of the original batch")
            value["jobs"] = [j for j in value["jobs"] if j["id"] in wanted]
        return value

    module.rollout_settings = extended_settings
    module.prepare = prepared_subset
    module.run(args)
    if args.out and not args.preflight:
        import json
        p = Path(args.out) / "receipt.json"
        receipt = json.loads(p.read_text())
        receipt.update(wrapper_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                       retry_only_ids=args.only_id)
        module.write_json(p, receipt)


if __name__ == "__main__":
    main()
