"""Propagate candidate-private same-group containment into Python children."""

from __future__ import annotations

import os


if os.environ.get("GEOTARGET_ARCHIVE_CONTAINED_CHILDREN") == "1":
    import contained_lifecycle
    from research.infrastructure.memory_safety import safe_subprocess

    safe_subprocess.run_guarded = contained_lifecycle.contained_run_guarded
