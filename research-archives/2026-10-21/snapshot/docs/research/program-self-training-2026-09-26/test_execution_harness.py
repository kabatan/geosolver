"""CPU checks of actual OS isolation, bounded execution and extraction rules."""
import dataclasses
import json
from pathlib import Path
import socket
import unittest

import execution_harness as h


class HarnessTests(unittest.TestCase):
    def test_allowed_math_and_number_types(self):
        code = '''import math, statistics, fractions, decimal, cmath, itertools, functools
def solve(givens):
    x = math.sqrt(givens['x'])
    x += statistics.mean([1, 3])
    x += float(fractions.Fraction(1, 2))
    x += float(decimal.Decimal('0.25'))
    x += cmath.sqrt(4).real
    x += sum(itertools.islice(itertools.count(1), 2))
    return functools.reduce(lambda a,b: a+b, [x, 1])
'''
        row = h.execute_program(code, {'x': 9})
        self.assertEqual(row['status'], 'ok'); self.assertEqual(row['value'], 11.75)
        self.assertEqual(h.execute_program('from fractions import Fraction\ndef solve(givens):\n return Fraction(1,3)\n', {})['status'], 'ok')
        self.assertEqual(h.execute_program('from decimal import Decimal\ndef solve(givens):\n return Decimal("0.125")\n', {})['value'], 0.125)

    def test_runtime_and_invalid_output(self):
        self.assertEqual(h.execute_program('def solve(givens):\n return 1/0\n', {})['status'], 'runtime_error')
        for value in ['None', 'True', '"3"', '[3]', 'complex(3,0)', 'float("inf")', 'float("nan")']:
            row = h.execute_program('def solve(givens):\n return '+value+'\n', {})
            self.assertEqual(row['status'], 'runtime_error', value)
        self.assertEqual(h.execute_program('import os\ndef solve(givens):\n return 1\n', {})['status'], 'invalid_program_or_input')

    def test_cpu_wall_memory_and_output_limits(self):
        code = 'def solve(givens):\n while True: pass\n'
        cpu = h.execute_program(code, {}, h.Limits(wall_seconds=3, cpu_seconds=1))
        self.assertEqual(cpu['status'], 'cpu_timeout'); self.assertIn(cpu['returncode'], (-24, 128+24))
        wall = h.execute_program(code, {}, h.Limits(wall_seconds=0.12, cpu_seconds=2))
        self.assertEqual(wall['status'], 'wall_timeout')
        memory = h.execute_program('def solve(givens):\n x=[0]*100000000\n return len(x)\n', {})
        self.assertEqual(memory['status'], 'runtime_error'); self.assertEqual(memory['error_type'], 'MemoryError')
        output = h.execute_program('def solve(givens):\n while True: print("x"*2048)\n', {})
        self.assertEqual(output['status'], 'output_limit')

    def test_host_files_hidden_and_mounts_readonly(self):
        root = Path('qwen/.runtime/program_self_training_20260926/cpu-tests').resolve()
        root.mkdir(parents=True, exist_ok=True)
        marker = root/'host-only-sentinel.txt'; marker.write_text('not exposed to candidates')
        code = f'def solve(givens):\n try:\n  open({str(marker)!r}).read()\n except FileNotFoundError:\n  return 1\n return 0\n'
        self.assertEqual(h.execute_program(code, {})['value'], 1)
        probe = h.run_isolated(['-c', 'import os,json; print(json.dumps({"home":os.path.exists("/home"),"etc":os.path.exists("/etc"),"root":os.listdir("/")}))'], b'', h.Limits())
        self.assertEqual(probe['status'], 'process_ok')
        dirs = json.loads(probe['stdout']); self.assertFalse(dirs['home']); self.assertFalse(dirs['etc'])
        write = h.execute_program('def solve(givens):\n open("/usr/lib/python3.14/forbidden-write", "w").write("x")\n return 0\n', {})
        self.assertEqual(write['status'], 'runtime_error'); self.assertEqual(write['error_type'], 'OSError')

    def test_network_namespace_and_fork_seccomp(self):
        with socket.socket() as server:
            server.bind(('127.0.0.1', 0)); server.listen()
            port = server.getsockname()[1]
            code = f'import socket,json\ns=socket.socket();s.settimeout(.2)\ntry:\n s.connect(("127.0.0.1",{port}));print("CONNECTED")\nexcept OSError as e:\n print(json.dumps({{"blocked":True,"errno":e.errno}}))\n'
            row = h.run_isolated(['-c', code], b'', h.Limits())
            self.assertEqual(row['status'], 'process_ok'); self.assertTrue(json.loads(row['stdout'])['blocked'])
        row = h.run_isolated(['-c', 'import os\ntry:\n os.fork();print("FORKED")\nexcept PermissionError:\n print("BLOCKED")'], b'', h.Limits())
        self.assertEqual(row['status'], 'process_ok'); self.assertEqual(row['stdout'].strip(), 'BLOCKED')

    def test_extraction_and_normalization(self):
        answer = '```python\ndef solve(givens):\n return 1\n```\ntext\n```python\n"""unverified explanation"""\n# explanation\ndef solve(givens):\n """another claim"""\n return 2\ndef solve(givens):\n return 3\n```\n'
        result = h.extract_program(answer, 'stop')
        self.assertEqual(result['selected_fence_index'], 1); self.assertEqual(result['solve_definitions'], 2)
        normalized = result['normalized_code']; self.assertNotIn('explanation', normalized); self.assertNotIn('claim', normalized)
        self.assertEqual(h.execute_program(normalized, {})['value'], 3)
        eos = h.extract_program('```python\ndef solve(givens):\n return 1\n```<|im_end|>\n', 'stop')
        self.assertTrue(eos['stripped_one_trailing_assistant_eos'])
        self.assertEqual(h.execute_program(eos['code'], {})['value'], 1)
        with self.assertRaises(ValueError): h.extract_program(answer, 'length')
        with self.assertRaises(ValueError): h.extract_program('```python\ndef solve(givens):\n return 1\n', 'stop')
        with self.assertRaises(ValueError): h.normalize_program('def solve(givens):\n return givens.__class__\n')
        with self.assertRaises(ValueError): h.normalize_program('def solve(givens):\n return eval("1")\n')
        # Re-executing normalization detects code that reads its own docstring.
        with self.assertRaises(ValueError): h.normalize_program('def solve(givens):\n """claim"""\n return len(solve.__doc__)\n')

    def test_oracle_not_in_payload_and_comparison(self):
        cases = [{'case_id':'test1','source_id':'toy','split':'visible','givens':{'x':9},'answer':3}]
        result = h.evaluate_candidate('import math\ndef solve(givens):\n return math.sqrt(givens["x"])\n', cases)
        self.assertTrue(result['all_passed']); self.assertEqual(result['n_passed'], 1)
        wrong = h.evaluate_candidate('def solve(givens):\n return givens["answer"]\n', cases)
        self.assertFalse(wrong['all_passed']); self.assertEqual(wrong['events'][0]['execution']['error_type'], 'KeyError')


if __name__ == '__main__':
    unittest.main(verbosity=2)
