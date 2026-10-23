"""Continue batches 3..25 with storage-only completed-output compaction.

The original outer runner remains unchanged and its preflight hash still holds.
The extra wrapper and hook are pinned in storage-amendment.json before batch 3.
"""
import argparse
import os
import sys
import execute_stage2 as stage

HOOK = stage.BASE / "storage_hook"
os.environ["PYTHONPATH"] = os.pathsep.join([str(HOOK), str(stage.ROOT / "src"), str(stage.ROOT)])


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("number", type=int)
    number = parser.parse_args().number
    if not 3 <= number <= 25:
        raise ValueError("storage amendment applies only to remaining batches 3..25")
    amendment = stage.read(stage.DEST / "storage-amendment.json")
    for rel, expected in amendment["implementation_sha256"].items():
        if stage.sha(stage.BASE / rel) != expected:
            raise RuntimeError("storage implementation changed: " + rel)
    stage.save(stage.DEST / "batches" / f"{number:02d}-storage-adapter.json", {
        "batch": number, "recorded_at_utc": stage.now(),
        "amendment_sha256": stage.sha(stage.DEST / "storage-amendment.json"),
        "implementation_sha256": amendment["implementation_sha256"],
    }, new=True)
    stage.batch(number)


if __name__ == "__main__":
    main()
