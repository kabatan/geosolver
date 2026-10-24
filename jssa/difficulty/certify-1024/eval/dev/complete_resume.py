#!/usr/bin/env python3
"""Detached resume driver and reporting only; never retries a problem."""
import collections
import csv
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import statistics
import subprocess
import sys
import time

sys.dont_write_bytecode = True
D = Path(__file__).resolve().parent
E = D.parent
BASE = E.parent
MAX_FILE = 2_900_000


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    text = json.dumps(value, ensure_ascii=False, indent=2) + '\n'
    assert len(text.encode()) <= MAX_FILE
    tmp = path.with_suffix(path.suffix + '.tmp')
    tmp.write_text(text)
    tmp.replace(path)


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def finalize():
    original = load_module('original_dev', D / 'run_dev.py')
    manifest = json.loads((D / 'pre-run-hashes.json').read_text())
    original.frozen_check(manifest)
    refs = original.shared_checks()
    audit = json.loads((D / 'resume-20261024.json').read_text())
    for row in audit['completed_results']:
        assert sha(D / 'runs' / (row['id'] + '.json')) == row['sha256'], row['id']
    for interrupted in audit['interrupted']:
        for item in interrupted['files']:
            assert sha(D / interrupted['archive_to'] / item['path']) == item['sha256']
    results = [json.loads((D / 'runs' / (cid + '.json')).read_text()) for cid in manifest['target_ids']]
    assert len(results) == 313 and len({r['id'] for r in results}) == 313
    for r in results:
        assert r['attempts'] == 1
        assert all(manifest['sources'][p] == h for p, h in r['implementation_sha256'].items())
        a = json.loads((D / 'runs' / (r['id'] + '.work') / 'attempt.json').read_text())
        assert a['pre_run_hashes_sha256'] == sha(D / 'pre-run-hashes.json')
        assert a['parallelism'] == r['campaign_parallelism'] == (4 if r['id'] in audit['pending_ids'] else 2)
    resumed = sorted((r for r in results if r['id'] in audit['pending_ids']),
                     key=lambda r: json.loads((D/'runs'/(r['id']+'.work')/'attempt.json').read_text())['start_unix'])
    assert [r['id'] for r in resumed] == audit['pending_ids']
    judge = load_module('judge_c3_c5', E / 'judge_c3_c5.py')
    stage_path = BASE.parent / 'exact-strong-1024/stageB/per-problem.csv'
    stage, stage_source = judge.load_stage(stage_path)
    devrows = list(csv.DictReader((D / 'per-problem.csv').open()))
    unseen = list(csv.DictReader((E / 'per-problem.csv').open()))
    assert len(unseen) == 29 and len(devrows) == 323
    assert not ({r['id'] for r in devrows} & {r['id'] for r in unseen})
    judgments = {}
    for name, rows, scope in [('dev', devrows, '開発群323問（実行対象313問）、dev5を含まない。'),
                              ('combined', devrows + unseen, '開発群323問＋開発外29問。実行対象341問、dev5を含まない。')]:
        result = judge.judge(rows, stage)
        result.update(scope=scope, stageb_source=stage_source,
                      judge_script_sha256=sha(E / 'judge_c3_c5.py'),
                      certify_csv_sha256=sha(D / 'per-problem.csv'),
                      unseen_csv_sha256=sha(E / 'per-problem.csv') if name == 'combined' else None)
        write(D / ('c3-c5-' + name + '.json'), result)
        judgments[name] = result
    summary = json.loads((D / 'summary.json').read_text())
    summary['resume'] = {'completed_before':225, 'external_interrupted_not_results':2,
                         'previously_untouched':86, 'resumed_once':88,
                         'parallelism_before':2, 'parallelism_after':4, 'second_retry':False}
    summary['C3_C5'] = {key:{c:value[c] for c in ('C3','C4','C5')} for key,value in judgments.items()}
    write(D / 'summary.json', summary)
    counts = collections.Counter(original.category(r) for r in results)
    categories = ['認証','非所属','変換不能','時間上限','資源上限','実装エラー','検算不能']
    text = '区分別件数：' + '、'.join(f'{c} {counts[c]}問' for c in categories) + '。対象外10問（答えなし3問、最小多項式なし7問）。\n\n'
    text += f'認証率は全対象 **{summary["certified"]}/{summary["all_targets"]} = {summary["rate_all"]:.2%}**、変換できた問題 **{summary["certified"]}/{summary["translated"]} = {summary["rate_translated"]:.2%}**。後者には変換後の時間・資源上限も残す。\n\n'
    text += '| 開発群だけの予測 | 判定 | 観測 |\n|---|---|---|\n'
    text += f'| C1：変換できた問題の認証率50%以上 | {"的中" if summary["C1"] else "外れ"} | {summary["rate_translated"]:.2%} |\n'
    text += f'| C2：認証問題の全体時間中央値2秒以下 | {"的中" if summary["C2"] else "外れ"} | {summary["certified_wall_median_seconds"]:.3f}秒 |\n\n'
    text += '開発群323問のうち313問を評価した。dev5との重複は0問。答えは補遺で固定したクラウド評価の凍結版60db4b6・seed 0の記録を使い、複数答えは全最小多項式の積とした。対象の追加・交換、別の答えでの代用はない。\n\n'
    text += 'C3〜C5は、変更していない[判定スクリプト](../judge_c3_c5.py)を既存stageB結果に当てた。開発外だけの既存判定は[別報](../answer-unseen29.md)。開発群と合算を分けて示す。\n\n'
    for name,label in [('dev','開発群のみ'),('combined','開発群＋開発外29問の合算')]:
        j = judgments[name]
        text += f'**{label}**\n\n| 予測 | 判定 | 観測 |\n|---|---|---|\n'
        strata = j['C3']['strata']
        parts = []
        for rel,label2 in [('equal','同一式'),('extra_irreducible_factors','余分な既約因子あり')]:
            s = strata[rel]
            parts.append(f'{label2} {s["certified"]}/{s["n"]} = {s["rate"]:.2%}（{s["judgment"]}）' if s['n'] else f'{label2} 0問（未判定）')
        text += f'| C3：同一式80%以上、余分な既約因子あり30%以下 | {j["C3"]["judgment"]} | '+ '、'.join(parts) + ' |\n'
        text += f'| C4：強化版で解けない認証問題5問以上 | {j["C4"]["judgment"]} | {j["C4"]["certified_not_solved"]}問、強化版状態の欠測{len(j["C4"]["missing_status"])}問 |\n'
        c5=j['C5']
        text += f'| C5：認証問題でcertifyの時間中央値が短い | {c5["judgment"]} | 対応{c5["paired_n"]}問、certify {c5["certify_median_seconds"]:.3f}秒／強化版 {c5["strong_median_seconds"]:.3f}秒 |\n\n'
        text += f'C3の式比較対象外は{len(j["C3"]["missing_or_unclassified"])}問。欠測・比較対象外を条件付き率の分母に混ぜていない。[判定詳細](c3-c5-{name}.json)。\n\n'
    text += '強化版の「解けた」はverified_completeとdirect_verifiedだけで、verified_subsetを含めない。式は定数倍を除いて比較し、p(T)で割り切れ、かつ新たな既約因子がある場合を余分な因子ありとした。\n\n'
    text += '主な内訳と代表例（保存された理由・最終段階による分類）：\n\n'
    for cat in ['非所属','変換不能','時間上限']:
        buckets=collections.defaultdict(list)
        for r in results:
            if original.category(r)!=cat: continue
            if cat=='変換不能': key=r.get('reason_code') or '理由なし'
            elif cat=='時間上限': key=r.get('last_algebra_event') or r.get('stage') or '段階不明'
            else: key='Rab法で非所属（個別の幾何学的原因は未検証）'
            buckets[key].append(r['id'])
        for key,ids in sorted(buckets.items(),key=lambda x:(-len(x[1]),x[0])):
            text+=f'- {cat}：{key}、{len(ids)}問。例：{", ".join(ids[:2])}。\n'
    text += '\n変換不能の理由コードはπ・角度の目標、未対応のDSL命令・条件などを表す。時間上限の段階は停止位置であり、計算量の個別原因までは断定できない。非所属は複素数の等式・非零条件からp(T)=0が従わないという計算結果で、solverの誤答とは扱わない。符号や根号の枝などで余分な解が残る可能性があるが、個別原因は未検証。非所属一般の独立証明書検算も行っていない。\n\n'
    text += '認証には、変換完了、Jが非単位、Rab法で所属、少なくとも一方の証明書の独立検算、べき法との無矛盾を要求した。これは多項式関係の認証であり、実図の存在・一意性・答え集合の完全性を保証しない。\n\n'
    text += '2026-10-24 12:32 JST頃、外部要因（アプリ全体の停止）で旧制御プロセスが終了した。完了225問は再実行していない。AIME-2008-II-05とJMO-2021-PRE-02の中断は結果と数えず、旧.workを[interrupted/](interrupted/)に内容・ハッシュ付きで保存し、各問を最初から1回だけ実行した。第2の再試行はない。未着手86問と合わせて88問をtarget-order.csvの順に開始した。[再開前監査](resume-20261024.json)。\n\n'
    text += '旧225問は並列2、再開88問は並列4固定。各問600秒・8 GiB・1 CPU、再試行0。起動時のload averageを各attempt.jsonに記録した。setsid・nohup、標準入力/dev/null、ログへの標準出力・標準エラー出力で制御プロセスを切り離した。時間は共有機の負荷付き参考値で、起動・変換・飽和・基底・正規形・証明書・検算を含む。並列条件も異なるため、C2/C5の数値を一般的な速度優位と解釈しない。\n\n'
    text += '事前登録・予測・成功定義と元コードは変更なし。run_dev.pyは保持し、そのコピーでは対象の取り方・排他開始記録・並列数とその記録だけを変更した。report関数は元と同一で、集計後にこの説明とC3〜C5を別処理で付記した。dev5は今回の対象外で再実行していない（既存結果は[README](../../README.md)）。\n\n'
    text += '[問題別CSV](per-problem.csv)、[集計](summary.json)、[終了監査](post-resume-audit.json)、[進捗](progress.md)。昇格・システム導入・他タスクの変更・commit/pushなし。各成果物は2,900,000 byte以下。\n'
    (D / 'answer-dev.md').write_text(text)
    write(D / 'post-resume-audit.json', {'completed_unix':time.time(),'completed':len(results),
          'original_225_unchanged':True,'interrupted_archives_unchanged':True,
          'all_frozen_sources_and_inputs_match':True,'all_results_match_implementation_hashes':True,
          'resume_start_order_matches':True,'resumed_once':len(resumed),'retry':False,
          'shared_references':refs,'stageb_source':stage_source,
          'report_function_unchanged':(D/'run_dev.py').read_text().split('\ndef report():',1)[1] == (D/'run_dev_resume.py').read_text().split('\ndef report():',1)[1],
          'driver_sha256':sha(__file__),'resume_adapter_sha256':sha(D/'run_dev_resume.py')})
    original.progress(results,{},313,'完了（外部中断から88問を再開、報告・C3〜C5判定・監査済み）')
    p=D/'progress.md'
    p.write_text(p.read_text().replace('並列2固定','旧225問は並列2、再開88問は並列4固定')+'\n外部中断2問は結果ではなく、旧.workをinterrupted/に保存して最初から各1回実行。第2の再試行なし。完了225問のJSONと凍結コード・入力のハッシュ一致を終了後も確認。answer-dev.mdを参照。\n')
    files=[p for p in sorted(D.rglob('*')) if p.is_file() and p.name not in ('artifact-hashes.jsonl','progress.md','controller-resume.log')]
    assert all(p.stat().st_size<=MAX_FILE for p in files)
    with (D/'artifact-hashes.jsonl').open('w') as f:
        for p in files: f.write(json.dumps({'path':str(p.relative_to(D)),'bytes':p.stat().st_size,'sha256':sha(p)})+'\n')
    assert (D/'artifact-hashes.jsonl').stat().st_size <= MAX_FILE
    print('RESUME_COMPLETE',flush=True)


if __name__ == '__main__':
    if len(sys.argv)>1 and sys.argv[1]=='finalize':
        finalize()
    else:
        with (D/'detached-driver-start.json').open('x') as f:
            json.dump({'pid':os.getpid(),'ppid':os.getppid(),'sid':os.getsid(0),'pgid':os.getpgrp(),
                       'start_unix':time.time(),'driver_sha256':sha(__file__),
                       'command':'setsid nohup python -B eval/dev/complete_resume.py'},f)
        code=subprocess.call([sys.executable,'-B',str(D/'run_dev_resume.py'),'run'],stdin=subprocess.DEVNULL)
        if code: raise SystemExit(code)
        finalize()
