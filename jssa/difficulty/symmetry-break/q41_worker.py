"""Observation wrapper; delegates all solver operations to frozen worker.main."""
import json
import os
from pathlib import Path
from stage2_common import CLEAN, save


def main():
    os.chdir(CLEAN)
    directory=Path(os.environ['Q41_OBSERVE_DIR'])
    from q41_observer import install
    finish=install(directory,float(os.environ['Q41_T0']),int(os.environ['Q41_DIMENSION']))
    try:
        from geosolver.runtime.worker import main as frozen_main
        return frozen_main()
    finally:
        save(directory/'observer-summary.json',finish())

if __name__=='__main__':raise SystemExit(main())
