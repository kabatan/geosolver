"""Inject only into the real production worker, including Windows subprocesses."""
import os
import sys

_args = sys.orig_argv
_module = _args[_args.index("-m") + 1] if "-m" in _args else None
if os.environ.get("REDRAW_AUDIT_PATH") and _module == "geosolver.runtime.worker":
    try:
        from redraw_patch import install
        install()
    except BaseException:
        # sitecustomize exceptions are normally swallowed by Python. Fail closed.
        import traceback
        traceback.print_exc()
        os._exit(91)
