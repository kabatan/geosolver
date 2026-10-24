#!/usr/bin/env python3
"""Synthetic proof semantics only; never reads or executes evaluation problems."""
import copy
import json
import os
from pathlib import Path
import resource
import subprocess
import tempfile
import time

import certify
certify.environment()
import sympy as sp
from verify_certificate import verify

T, x = sp.symbols('T x')
# 1. Nonradical J: first vanishing power is 2.
# 2. Radical exponent 5: all four NF tests miss, Rabinowitsch still succeeds.
# 3. Genuine nonmembership (p=0 on only some components).
# 4. Saturation essential, and certificate must start from original equations.
# 5. Empty ideal is vacuous, never a successful answer certification.
CASES = [
    ('nilpotent2', [T**2], [], [T], T, T, 'member', 2),
    ('nilpotent5', [T**5], [], [T], T, T, 'member', None),
    ('nonmember', [T**2-1], [], [T], T, T-1, 'nonmember', None),
    ('saturated', [x*T, x**2-x], [x], [x,T], T, T, 'member', 1),
    ('two_inverse_guards', [(x**2-1)*T], [x-1, x+1], [x,T], T, T, 'member', 1),
    ('rational_scaling', [T**2/4-sp.Rational(1,4)], [], [T], T, T**2-1, 'member', 1),
    ('empty', [sp.Integer(1)], [], [T], T, T, 'algebraically_empty', 1),
]


def limits():
    resource.setrlimit(resource.RLIMIT_AS, (certify.MEM, certify.MEM))
    resource.setrlimit(resource.RLIMIT_FSIZE, (certify.MAX_FILE, certify.MAX_FILE))
    os.sched_setaffinity(0, {min(os.sched_getaffinity(0))})


def main():
    results = []
    invalid, _ = certify.parse_log('   ? synthetic error\nMETRIC nf_1_zero 1\nMETRIC rab_unit 1\n')
    assert invalid['status'] == 'error'
    assert invalid['power']['status'] == 'invalid_singular_output'
    assert invalid['rabinowitsch']['status'] == 'invalid_singular_output'
    legacy = {'variables': ['x1','zz','yy'], 'variable_mapping': {'x1': 'T'},
              'target_variable': 'x1', 'equations': ['x1'], 'saturation_factors': [],
              'polynomial': 'x1', 'order': 'dp (degree reverse lexicographic)',
              'certificate_extension': 'K=<original equations, 1-zz*product(saturation factors)>'}
    assert verify(dict(legacy, method='power', exponent=1, coefficients=['1','0']), legacy)['verified']
    with tempfile.TemporaryDirectory(prefix='certify-synthetic-') as directory:
        work = Path(directory)
        for name, eq, fac, variables, target, p, status, m in CASES:
            t = time.monotonic()
            script, model = certify.singular_text(eq, fac, variables, target, p)
            path = work / (name + '.sing')
            path.write_text(script)
            proc = subprocess.run(['Singular', '-q', str(path)], capture_output=True, text=True,
                                  timeout=60, preexec_fn=limits)
            result, blocks = certify.parse_log(proc.stdout)
            if proc.returncode or result['singular_errors'] or result['last_algebra_event'] != 'finished end':
                raise AssertionError(proc.stdout + proc.stderr)
            assert result['status'] == status, (name, result)
            assert result['power'].get('first_zero_power') == m, (name, result)
            verified = []
            rejected_tampering = []
            for method, certpath in certify.extract_certificates(work, model, result, blocks):
                certificate = json.loads(certpath.read_text())
                check = verify(certificate, model)
                assert check['verified'], (name, method, check, proc.stdout)
                broken = copy.deepcopy(certificate)
                broken['coefficients'][0] = '(' + broken['coefficients'][0] + ')+1'
                # In the empty test first f_i=1 as well, so also detects tampering.
                assert not verify(broken, model)['verified']
                broken = copy.deepcopy(certificate)
                broken['equations'][0] = '0'
                assert not verify(broken, model)['verified']
                rejected_tampering.append(method)
                verified.append(method)
            results.append({'name': name, 'status': result['status'], 'first_zero_power': m,
                            'verified_methods': verified, 'tampering_rejected': rejected_tampering,
                            'wall_seconds': time.monotonic()-t})
    certify.write_json(certify.HERE / 'smoke-checks.json', results)
    print(json.dumps(results, indent=2))


if __name__ == '__main__':
    main()
