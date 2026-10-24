"""Audit switch routing only. Does not import a solver or evaluate answers."""
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent

def load(p):
    return json.loads(p.read_text())

def main():
    plan = load(HERE / 'smoke-plan.json')
    configs = {c['name']: c for c in load(HERE / 'configs.json')['configurations']}
    reports, issues = [], []
    for job in plan['jobs']:
        d = HERE / 'smoke' / f"{job['index']:02d}"
        events = [json.loads(l) for p in sorted((d / 'trace').glob('*.jsonl'))
                  for l in p.read_text().splitlines()]
        gates = [e for e in events if e['event'] == 'gate'
                 and e['caller'] != 'runtime/ablation.py']
        checked = {e['switch']: e['disabled'] for e in gates}
        expected = configs[job['configuration']]['environment']
        violations = []
        for e in gates:
            if e['disabled'] != (expected['GEOSOLVER_ABLATE_' + e['switch']] == '1'):
                violations.append('gate mismatch: ' + e['switch'])
        calls = [e for e in events if e['event'] == 'call']
        def called(function, file_contains=''):
            return any(e['function'] == function and file_contains in e['file'] for e in calls)
        backends = []
        for function, label in [('search_algebraic_branches', 'algebraic prepass'),
                                ('search_positive_scale_chart', 'positive scale chart')]:
            if any(e.get('function') == function and e.get('produced_batch') for e in events):
                backends.append(label)
        if any(e.get('function') == '_import_pynomad' and e.get('import_succeeded')
               and 'search/nomad_backend.py' in e.get('file', '') for e in events):
            backends.append('NOMAD normal')
        if called('run_search', 'scipy_multistart_backend'):
            backends.append('SciPy multistart')
        if any(e.get('function') == '_import_pynomad' and e.get('import_succeeded')
               and 'run_rescue_search.py' in e.get('file', '') for e in events):
            backends.append('NOMAD rescue')
        smooth = called('_smooth_zero_constraint_residuals')
        analytic = called('evaluate_jacobian')
        residual_top20 = called('select_residual_candidates')
        rescue = called('run_rescue_search')
        if expected['GEOSOLVER_ABLATE_NO_RESIDUAL_REWRITE'] == '1' and smooth:
            violations.append('residual smoothing called while disabled')
        if expected['GEOSOLVER_ABLATE_NO_ANALYTIC_JAC'] == '1' and analytic:
            violations.append('analytic Jacobian evaluated while disabled')
        if expected['GEOSOLVER_ABLATE_NO_DIVERSE_SELECTION'] == '0' and residual_top20:
            violations.append('residual-only selection called while diverse selection enabled')
        if expected['GEOSOLVER_ABLATE_NO_RESCUE'] == '1' and rescue:
            violations.append('rescue called while disabled')
        worker = load(d / 'worker.json')
        starts = [e for e in events if e['event'] == 'process_start']
        for e in starts:
            if e['environment'] != expected:
                violations.append('process environment mismatch')
        attempts = sorted({e['attempt_count'] for e in events if 'attempt_count' in e})
        exp_attempts = 1 if expected['GEOSOLVER_ABLATE_NO_SECOND_ATTEMPT'] == '1' else 2
        if attempts != [exp_attempts]:
            violations.append('ordered attempt descriptor count mismatch')
        if 'NOMAD normal' in backends and expected['GEOSOLVER_ABLATE_NO_NOMAD'] == '1':
            violations.append('normal NOMAD imported while disabled')
        for field, switch in [('search_algebraic_branches', 'NO_ALGEBRAIC'),
                              ('search_positive_scale_chart', 'NO_SCALE_CHART')]:
            if expected['GEOSOLVER_ABLATE_' + switch] == '1' and any(
                e.get('function') == field and e.get('produced_batch') for e in events):
                violations.append(field + ' produced batch while disabled')
        rec = dict(**job, expected_environment=expected, actual_branch_checks=checked,
            unvisited_switches=sorted(k.removeprefix('GEOSOLVER_ABLATE_') for k in expected
                                     if k.removeprefix('GEOSOLVER_ABLATE_') not in checked),
            actual_backends=backends, ordered_attempt_descriptor_counts=attempts,
            residual_top20_called=residual_top20, refinement_smoothing_called=smooth,
            analytic_jacobian_evaluated=analytic, rescue_called=rescue,
            optional_batch_returns=[e for e in events if 'produced_batch' in e],
            worker_artifact_received=worker['worker_artifact_received'],
            source_hash=worker['source_hash'], process_count=len(starts),
            cpu_affinity_sets=[e['affinity'] for e in starts], violations=violations,
            correctness_recorded=False)
        reports.append(rec)
        issues.extend([dict(index=job['index'], violation=v) for v in violations])
    config_reports = []
    for name, config in configs.items():
        rows = [r for r in reports if r['configuration'] == name]
        checked = sorted(set().union(*(set(r['actual_branch_checks']) for r in rows)))
        missing = sorted({k.removeprefix('GEOSOLVER_ABLATE_') for k in config['environment']} - set(checked))
        config_reports.append(dict(configuration=name, jobs=[r['index'] for r in rows],
            checked_switches=checked, unvisited_switches=missing,
            violations=[v for r in rows for v in r['violations']],
            mechanism_not_fired=[feature for feature in ['refinement_smoothing_called',
                'analytic_jacobian_evaluated', 'rescue_called'] if not any(r[feature] for r in rows)]))
    record = dict(full_process_runs=24, retries=0, seed=601, time_limit_seconds=20,
        max_parallel=6, correctness_recorded=False, grading_performed=False,
        main_measurement_executed=False, switch_wiring_violations=issues,
        limitations=['Observation adds profiling overhead: these elapsed times are not performance data.',
            'Enabled gates do not prove mechanism applicability, production of candidates or answer quality.',
            'Only first call/return per function/process is logged; full call counts at normal process exit.',
            'Ordered descriptors may include fallback without actually running it.',
            'No reruns or extra probes were performed for unvisited paths.'],
        configurations=config_reports, jobs=reports)
    (HERE / 'smoke-check.json').write_text(json.dumps(record, ensure_ascii=False, indent=2) + '\n')
    lines = ['# 12構成の短時間フルプロセス動作確認', '',
        '固定した2問 AIME-2014-II-08 / HMMT-2008-FEB-GEO-09 を各構成1回、seed 601、20秒上限、1コア、最大6並列で実行した。EngineRunner→本物のworker→必要なsymbolic subprocessを使用。全24親プロセスreturncode=0、外側28秒timeout=0、全worker artifact受領。正誤・答えの集合・採点ラベルは保存していない。本計測は0回。', '',
        '観測は observe/sitecustomize.py の sys.setprofile によりソースを書き換えず実施。実際の ablated() 戻り値、呼出元、通常NOMAD import成功/SciPy backend到達、ordered attempt数、残差選別、精密化平滑化・解析微分評価の到達を保存した。単に環境変数を設定しただけの確認とは区別する。', '',
        f"**スイッチ矛盾・停止漏れ：{len(issues)}件。** 各構成の未到達flagは下表およびJSONで明示。flagが0でも、対象外・早期返却・短い残時間でその機構が動かない場合がある。再試行・追加問・追加seedは行わない。", '',
        '| 構成 | AIME / HMMTで実際に到達したbackend | 分岐未到達のスイッチ（2問合算） | 平滑化 / 解析J評価 / 救済（いずれか1回） |',
        '|---|---|---|---|']
    for c in config_reports:
        rows = [r for r in reports if r['configuration'] == c['configuration']]
        flags = ['yes' if any(r[k] for r in rows) else 'no' for k in
                 ['refinement_smoothing_called', 'analytic_jacobian_evaluated', 'rescue_called']]
        lines.append('| ' + c['configuration'] + ' | ' + ' / '.join(', '.join(r['actual_backends']) or 'なし' for r in rows)
            + ' | ' + (', '.join(c['unvisited_switches']) or 'なし') + ' | ' + ' / '.join(flags) + ' |')
    lines += ['', '「no」は停止成功または有効だが未発火。各flagの設定値・実測分岐はsmoke-check.jsonを参照。残差書き換えと解析Jの停止時に呼出しがないこと、G3停止時の生残差選別、G2停止時のattempt数1を照合した。救済は残時間8秒以上かつ未完了等の条件付きなので、未発火をNO_RESCUE不動作とは判定しない。', '',
        '診断生ログ：smoke/00〜23/{start.json,end.json,worker.json,trace/*.jsonl,stderr.log}。freeze.json に観測コードとsmoke計画の実行前hashを保存。プロファイルの負荷があるため時間を本計測や構成比較に転用しない。未発火機構の完全な動的検証までは主張しない。', '']
    (HERE / 'smoke-check.md').write_text('\n'.join(lines))
    print(json.dumps(dict(violations=issues, configurations=config_reports), ensure_ascii=False, indent=2))

if __name__ == '__main__':
    main()
