"""Run the frozen HP bridge with one memory-safe lock slot per physical CPU."""

from __future__ import annotations

import os
import runpy
import sys
from pathlib import Path

from geotarget.hp_preloader import SOCKET_ENV, delegated_run


def main() -> None:
    try:
        cpu = int(sys.argv[sys.argv.index("--cpu") + 1])
    except (ValueError, IndexError) as error:
        raise SystemExit("optimized HP slot requires the frozen --cpu argument") from error
    if cpu not in range(16):
        raise SystemExit("optimized HP slot CPU must satisfy the frozen [0,15] contract")
    product_root = Path(__file__).resolve().parent
    frozen_bridge = (
        product_root
        / "_engine/runtime/solver/research/experiments/EXP-V15-243-001/candidates"
        / "point_on_circle_periodic_semantics/approved_hp_bridge_v5.py"
    )
    global_lock = Path("/tmp/geotarget-one-heavy-hp-process-v1.lock")
    slot_lock = Path(f"/tmp/geotarget-heavy-hp-process-cpu-{cpu:02d}-v1.lock")
    original_open = Path.open
    original_reserved = None

    def slot_open(path: Path, *args, **kwargs):
        target = slot_lock if path == global_lock else path
        return original_open(target, *args, **kwargs)

    Path.open = slot_open
    try:
        if not os.environ.get(SOCKET_ENV):
            raise SystemExit(
                "optimized HP authority requires the product preloader"
            )
        solver_root = product_root / "_engine/runtime/solver"
        if str(solver_root) not in sys.path:
            sys.path.insert(0, str(solver_root))
        from research.infrastructure.memory_safety import safe_subprocess

        original_reserved = safe_subprocess._run_guarded_reserved

        def preloaded_reserved(command, **kwargs):
            return delegated_run(command, original=original_reserved, **kwargs)

        safe_subprocess._run_guarded_reserved = preloaded_reserved
        runpy.run_path(str(frozen_bridge), run_name="__main__")
    finally:
        if original_reserved is not None:
            safe_subprocess._run_guarded_reserved = original_reserved
        Path.open = original_open


if __name__ == "__main__":
    main()
