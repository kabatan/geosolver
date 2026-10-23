"""Synthetic observer contract test. Does not run any solver or search."""
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace

from stage2_common import FirstFigure, IdentifyViolation, OUT, SOURCE, read, sha, utc, write


def main():
    with tempfile.TemporaryDirectory(prefix='q40b-observer-test-') as temp:
        run = Path(temp)
        write(run / 'claim.json', {'dsl_sha256': 'synthetic', 'environment_hash': 'synthetic', 'run_order': -1})
        os.environ['Q40B_RUN_DIR'] = str(run)
        os.environ['Q40B_OUTER_PERF_NS'] = '0'
        import q40b_worker as worker
        from mpmath import mp

        @dataclass
        class Verification:
            verified: bool
            values: tuple
            precision_dps: int = 180
            normalized_residual: str = '0.0'
            hard_feasible: bool = True

        @dataclass
        class Candidate:
            candidate_uid: str = 'synthetic/candidate/17'
            candidate_id: int = 17
            revision: int = 3

        result = Verification(False, (mp.mpf(1), mp.mpf(2)))
        calls = []
        evaluator = SimpleNamespace(bundle=SimpleNamespace(var_names=('x', 'y')))
        candidate = Candidate()

        def original(ev, cand, **kwargs):
            calls.append((ev, cand, kwargs))
            return result

        assembly = SimpleNamespace(_verify_revision=original)
        pipeline = SimpleNamespace(infer_problem_bounds=lambda bundle: [(-2, 2), (-3, 3)])
        reached_after_success = []

        def original_pipeline():
            answer = assembly._verify_revision(evaluator, candidate, precision_schedule=(80, 120))
            reached_after_success.append(True)
            return answer

        frozen = SimpleNamespace(run_external_pipeline=original_pipeline)
        worker.install(assembly, pipeline, frozen)
        assert assembly._verify_revision(evaluator, candidate) is result
        assert calls == [(evaluator, candidate, {})]
        assert pipeline.infer_problem_bounds(evaluator.bundle) == [(-2, 2), (-3, 3)]
        result.verified = True
        try:
            frozen.run_external_pipeline()
            raise AssertionError('successful verification was not stopped')
        except FirstFigure:
            pass
        assert not reached_after_success
        figure = read(run / 'figure.json')
        assert figure['candidate_uid'] == candidate.candidate_uid
        assert figure['input_revision'] == 3
        assert figure['verified_coordinates'] == figure['verification']['values']
        assert figure['source_hash'] == SOURCE and figure['identify_calls'] == 0
        assert calls[-1][2] == {'precision_schedule': (80, 120)}
        assert read(run / 'figure-commit.json')['sha256'] == sha(run / 'figure.json')
        try:
            assembly.identify_answer()
            raise AssertionError('identification was not blocked')
        except IdentifyViolation:
            pass
        assert read(run / 'identify-violation.json')['identify_calls'] == 1
    report = {'passed': True, 'utc': utc(), 'solver_calls': 0, 'search_calls': 0,
              'checks': ['unsuccessful return object unchanged; original called once',
                         'kwargs and candidate attribution preserved',
                         'first verified return raises dedicated BaseException',
                         'pipeline code after discovery is unreachable',
                         'full verified coordinates and committed receipt retained',
                         'identify_answer counter blocks entry']}
    write(OUT / 'observer-validation.json', report, exclusive=True)
    print(report)


if __name__ == '__main__':
    main()
