"""Install Q14 instrumentation only in the production solver worker."""
import os
import sys

args = sys.orig_argv
module = args[args.index("-m") + 1] if "-m" in args else None
if os.environ.get("NOMAD_WALL_MODE") in ("B", "N") and module == "geosolver.runtime.worker":
    try:
        from nomad_wall_patch import install
        install()
    except BaseException:
        import traceback
        traceback.print_exc()
        os._exit(91)
