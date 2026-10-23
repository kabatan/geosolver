"""Transparent entry into frozen runtime.worker.main, with Q40b observers."""
import time
WORKER_CPU_START_NS = time.process_time_ns()
WORKER_PERF_START_NS = time.perf_counter_ns()

import importlib
import os
import signal
import sys
from pathlib import Path

from stage2_common import (FirstFigure, IdentifyViolation, SOURCE, THREADS,
                           cpu_snapshot, encode, read, sha, utc, write)

RUN = Path(os.environ['Q40B_RUN_DIR'])
META = read(RUN / 'claim.json')
STATE = {'pid': os.getpid(), 'started_utc': utc(),
         'worker_cpu_start_ns': WORKER_CPU_START_NS,
         'worker_perf_start_ns': WORKER_PERF_START_NS,
         'identify_calls': 0, 'verification_calls': 0, 'instrumentation_installed': False}


def state_sample(reason):
    write(RUN / 'worker-end.json', {**STATE, 'reason': reason,
          'snapshot': cpu_snapshot(WORKER_CPU_START_NS), 'ended_utc': utc(),
          'load_average': os.getloadavg()})


def terminated(signum, frame):
    state_sample('signal_' + str(signum))
    os._exit(128 + signum)


def install(assembly, pipeline, frozen_worker):
    original_verify = assembly._verify_revision
    original_pipeline = frozen_worker.run_external_pipeline
    original_bounds = pipeline.infer_problem_bounds

    def verify(evaluator, candidate, **kwargs):
        STATE['verification_calls'] += 1
        result = original_verify(evaluator, candidate, **kwargs)
        if not result.verified:
            return result
        # This is the first operation following the original successful return.
        snapshot = cpu_snapshot(WORKER_CPU_START_NS)
        from geosolver.runtime.deadline import counters_snapshot
        from geosolver.runtime.integrity import source_tree_hash
        payload = {**STATE, 'discovery': snapshot,
                   'outer_perf_start_ns': int(os.environ['Q40B_OUTER_PERF_NS']),
                   'wall_s': (snapshot['perf_ns'] - int(os.environ['Q40B_OUTER_PERF_NS'])) / 1e9,
                   'candidate_uid': candidate.candidate_uid,
                   'candidate_id': candidate.candidate_id,
                   'input_revision': candidate.revision,
                   'candidate_input': encode(candidate),
                   'verification': encode(result),
                   'variable_names': list(evaluator.bundle.var_names),
                   'verified_coordinates': encode(result.values),
                   'source_hash': source_tree_hash(),
                   'dsl_hash': META['dsl_sha256'], 'run_order': META['run_order'],
                   'environment_hash': META['environment_hash'],
                   'affinity': sorted(os.sched_getaffinity(0)),
                   'thread_environment': {k: os.environ.get(k) for k in THREADS},
                   'load_average_at_discovery': os.getloadavg(),
                   'counters_at_discovery': counters_snapshot(), 'discovery_utc': utc()}
        raise FirstFigure(payload)

    def identify(*args, **kwargs):
        STATE['identify_calls'] += 1
        write(RUN / 'identify-violation.json', STATE)
        raise IdentifyViolation('identify_answer was reached; measurement invalid')

    def bounds(bundle):
        result = original_bounds(bundle)
        STATE['inferred_bounds'] = encode(result)
        STATE['bounds_variable_names'] = list(bundle.var_names)
        return result

    def observed_pipeline(*args, **kwargs):
        try:
            return original_pipeline(*args, **kwargs)
        except FirstFigure as stop:
            # Dedicated BaseException is caught at this jssa boundary. The
            # frozen worker then serializes its normal failure artifact after
            # runtime_session closes. The independent figure receipt is the
            # experiment's success evidence, never the ordinary solve status.
            write(RUN / 'figure.json', stop.payload, exclusive=True)
            STATE['intentional_figure_stop'] = True
            STATE['figure_sha256'] = sha(RUN / 'figure.json')
            write(RUN / 'figure-commit.json', {'sha256': STATE['figure_sha256'],
                  'run_order': META['run_order'], 'saved_utc': utc()}, exclusive=True)
            raise

    assembly._verify_revision = verify
    assembly.identify_answer = identify
    ident = importlib.import_module('geosolver.engine.standard.exact_assembly.identify_answer')
    ident.identify_answer = identify
    pipeline.infer_problem_bounds = bounds
    frozen_worker.run_external_pipeline = observed_pipeline
    STATE['instrumentation_installed'] = True


def main():
    raw = Path(os.environ['Q40B_RAW_LOG'])
    raw.parent.mkdir(parents=True, exist_ok=True)
    with raw.open('ab', buffering=0) as log:
        os.dup2(log.fileno(), 1)
        os.dup2(log.fileno(), 2)
    signal.signal(signal.SIGTERM, terminated)
    signal.signal(signal.SIGXCPU, terminated)
    write(RUN / 'worker-start.json', STATE, exclusive=True)
    try:
        # Imports and observer setup are included in worker CPU, as required.
        frozen = importlib.import_module('geosolver.runtime.worker')
        assembly = importlib.import_module('geosolver.engine.standard.orchestration.assemble_exact_results')
        pipeline = importlib.import_module('geosolver.engine.standard.orchestration.run_external_pipeline')
        from geosolver.runtime.integrity import source_tree_hash
        assert source_tree_hash() == SOURCE
        assert str(Path(frozen.__file__).resolve()).startswith('/tmp/q40b-clean/src/')
        install(assembly, pipeline, frozen)
        write(RUN / 'observer-ready.json', STATE, exclusive=True)
        return frozen.main()
    finally:
        state_sample('frozen_worker_main_finished')


if __name__ == '__main__':
    sys.exit(main())
