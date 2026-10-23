# Loaded by every Python process started with this folder on PYTHONPATH (the solver runs its search in a
# worker subprocess, so the patch must be applied there). Does nothing unless REDRAW_MODE is set.
import os

if os.environ.get("REDRAW_MODE") in ("plain", "redraw"):
    import redraw_patch  # noqa: F401
