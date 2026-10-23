"""Diagnostic full-search warm start: replace ONLY the initial random probe.

Unlike warm_worker.py, the original Phase A search, heuristic boxes, supplemental
sampling, refinement and completion are all retained. No answer is injected.
"""
from common import *
import importlib
from warm_worker import probe

if __name__ == "__main__":
    pipeline = importlib.import_module("geosolver.engine.standard.orchestration.run_external_pipeline")
    pipeline.run_initial_probe = probe
    from geosolver.runtime.worker import main
    main()
