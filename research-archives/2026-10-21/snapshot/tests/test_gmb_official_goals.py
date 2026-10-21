"""Optional integration checks against the installed, unmodified GMB runtime."""

from __future__ import annotations

import importlib
import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
try:
    environment = importlib.import_module("benchmarks.gmb.environment")
    official = importlib.import_module("benchmarks.gmb_comparison.official_goals")
finally:
    sys.path.pop(0)


def test_goal_denominator_includes_common_rejected_outputs_and_eval_errors():
    rows = [
        {
            "model": "saved",
            "goal_clause_count": 1,
            "common_any_output_success": False,
            "official": {"status": "evaluated", "all_passed": True},
        },
        {
            "model": "saved",
            "goal_clause_count": 1,
            "official": {"status": "evaluation_error", "all_passed": False},
        },
        {
            "model": "saved",
            "goal_clause_count": 0,
            "official": {"status": "no_eval", "all_passed": None},
        },
        {
            "model": None,
            "goal_clause_count": 1,
            "official": {"status": "no_output", "all_passed": None},
        },
    ]
    result = official.aggregate(rows)
    assert result["planned_runs"] == 4
    assert result["goal_eligible_emitted_runs"] == 2
    assert result["goal_passed_runs"] == 1
    assert result["conditional_goal_rate"] == 0.5


def test_replay_gate_checks_values_not_just_pass_labels(tmp_path):
    model = tmp_path / "model.json"
    model.write_text(json.dumps({"goals": {"g": 0.005}}))
    request = {
        "jobs": [{"id": "gmb/case/0", "model": str(model), "model_sha256": official.sha256(model)}]
    }
    evaluated = [
        {
            "job": "gmb/case/0",
            "result": {"status": "evaluated", "all_passed": True, "values": {"g": 0.005}},
        }
    ]
    assert official.replay_validation(request, evaluated)["passed"]
    evaluated[0]["result"]["values"]["g"] = 0.006
    assert not official.replay_validation(request, evaluated)["passed"]


def test_official_eval_uses_saved_objects_and_no_optimization(tmp_path):
    if not environment.PYTHON.exists():
        pytest.skip("optional pinned GMB runtime is not installed")
    environment.source_identity()
    code = r"""
import importlib.util, json, math, sys
sys.path.insert(0, sys.argv[1] + '/src')
import tensorflow.compat.v1 as tf
tf.disable_v2_behavior()
tf.logging.set_verbosity(tf.logging.ERROR)
spec = importlib.util.spec_from_file_location('goals_worker', sys.argv[2])
w = importlib.util.module_from_spec(spec)
spec.loader.exec_module(w)

def geo(points, lines=None, circles=None):
    return {'witness': {'points': points, 'lines': lines or {}, 'circles': circles or {}}}

e = w.GoalEvaluator('(param (A B C) triangle)\n(eval (cong A B A C))')
try:
    for length2, expected in [(1.05, True), (1.2, False)]:
        m = geo({'A':[0,0], 'B':[1,0], 'C':[0,math.sqrt(length2)]})
        result = e.evaluate(m, 'geosolver')
        assert result['all_passed'] is expected, result
        assert math.isclose(next(iter(result['values'].values())), (1-length2)**2,
                            rel_tol=1e-12, abs_tol=1e-15)
        assert result['threshold'] == 0.01 and result['optimization_steps'] == 0
    m = geo({'A':[0,0], 'B':[0.1,0], 'C':[0,0.1*math.sqrt(1.2)]})
    assert e.evaluate(m, 'geosolver')['all_passed'] is True  # upstream scale dependence
    for bad in [float('nan'), True, '1e400']:
        try:
            e.evaluate(geo({'A':[bad,0], 'B':[1,0], 'C':[0,1]}), 'geosolver')
        except ValueError:
            pass
        else:
            raise AssertionError('invalid coordinate accepted')
    try:
        e.evaluate(geo({'A':[0,0], 'B':[1,0]}), 'geosolver')
    except ValueError:
        pass
    else:
        raise AssertionError('missing object silently repaired')
finally:
    e.close()

e = w.GoalEvaluator('(param A point)\n(param B point)\n'
                    '(define M point (midp A B))\n(eval (midp M A B))')
try:
    # M must come from the stored witness, not be recomputed from its definition.
    assert e.evaluate(geo({'A':[0,0], 'B':[2,0], 'M':[2,0]}), 'geosolver')['all_passed'] is False
    assert e.evaluate(geo({'A':[0,0], 'B':[2,0], 'M':[1,0]}), 'geosolver')['all_passed'] is True
finally:
    e.close()

e = w.GoalEvaluator('(param A point)\n(param B point)\n(param l line)\n(param C circle)\n'
                    '(eval (on-line A l))\n(eval (on-circ B C))')
try:
    m = geo({'A':[3,2], 'B':[1,0]}, {'l':[0,-2,4]}, {'C':{'center':[0,0],'radius':1}})
    native = {'named_points':{'A':{'x':3,'y':2},'B':{'x':1,'y':0}},
              'named_lines':{'l':{'n':{'x':0,'y':1},'r':2}},
              'named_circles':{'C':{'center':{'x':0,'y':0},'radius':1}}}
    result = e.evaluate(m, 'geosolver')
    assert result['all_passed'] is True
    assert result['values'] == e.evaluate(native, 'gmb')['values']
    m['witness']['lines']['l'] = [0,1,-3]
    assert e.evaluate(m, 'geosolver')['all_passed'] is False
finally:
    e.close()

e = w.GoalEvaluator('(param A point)')
try:
    result = e.evaluate(geo({'A':[0,0]}), 'geosolver')
    assert result['status'] == 'no_eval' and result['all_passed'] is None
finally:
    e.close()

# Record a limitation of the pinned upstream implementation; do not repair it
# in an adapter claiming to reproduce its original goal scores.
e = w.GoalEvaluator('(param l line)\n(param C circle)\n(eval (tangent-lc l C))')
try:
    centered = geo({}, {'l':[0,1,-1]}, {'C':{'center':[0,0],'radius':1}})
    translated = geo({}, {'l':[0,1,-3]}, {'C':{'center':[1,2],'radius':1}})
    assert e.evaluate(centered, 'geosolver')['all_passed'] is True
    assert e.evaluate(translated, 'geosolver')['all_passed'] is False
finally:
    e.close()
print('official formula, squared threshold, scale, bindings, missing/nonfinite, no-eval: passed')
"""
    result = subprocess.run(
        [
            str(environment.PYTHON),
            "-B",
            "-c",
            code,
            str(environment.SOURCE),
            str(ROOT / "benchmarks/gmb_comparison/official_goals_worker.py"),
        ],
        env=environment.child_environment(tmp_path),
        cwd=tmp_path,
        text=True,
        capture_output=True,
        timeout=60,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "passed" in result.stdout
