"""Load the registered intervention in the production solver worker only."""
import os
import sys

_argv = sys.orig_argv
_module = _argv[_argv.index("-m") + 1] if "-m" in _argv else None
if os.environ.get("ROLE_AUDIT_PATH") and _module == "geosolver.runtime.worker":
    try:
        from role_patch import install
        install()
    except BaseException:
        import traceback
        traceback.print_exc()
        os._exit(91)
