"""Final stage-1 action: verify existing audits, write prediction/lock, then stop.

Only standard-library file reads, Git read-only checks, and the two final writes.
No solver imports or execution paths. Refuses to replace an existing prediction.
"""
from __future__ import annotations

import csv
import datetime
import hashlib
import json
import os
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
COMMIT = '60db4b679b04167175c51c479c87c22fa663fda0'
LIMIT = 5_000_000
PROBABILITIES = [.80,.98,.99,.99,.99,.75,.98,.90,.99,.80,.90,.96,.99,.96,.99,.98,.70]
REASONS = [
    '6変数とmin/maxの非滑らかな射影条件。2配置の代入は合格だが探索上の難しさは残る。',
    '面積・平行・比・鏡映の直接記述。形と尺度の自由度が残るが、単純な等式が中心。',
    '未知Eの2座標を2距離で制約する小さい系。残りは直線交点。',
    '正の実数1変数と距離1条件。目標も同じ直線上の距離。',
    '未知変数0。正六角形と内接円の定義的な評価・厳密値組立が中心。',
    '7変数、共円性、3接線の接点が線分上という枝条件が重なる。',
    '未知2座標だけ。既知三辺から垂足・円・3接線を構成する。',
    '未知3変数だが、円の構成・3共円条件・6点の順序が結合する。',
    '正の辺長1変数。公式図の4小正方形の面積条件は容易。',
    '11変数、3つの正三角形の共通辺長、6線分点、凸順序が結合する。',
    '6変数、角三等分と円の第2交点。既知交点Cを除く枝がある。',
    '3変数、2距離と角の倍角関係。整数出力表現を探索から外してある。',
    '未知変数0。単位正十二角形の交点と扇形面積。床は入力にない。',
    '4変数でCが動く系。直角・中点距離・凸性を満たす異なる2配置を確認。',
    '未知変数0。正五角形と外側への60度回転を評価する角度問題。',
    '4変数。正三角形の2条件と中点の2座標条件。半直線の枝を保持。',
    '6変数、4角条件、凸五角形、内部点の5不等式。今回最も保守的に予測する。',
]


def sha_bytes(data): return hashlib.sha256(data).hexdigest()
def sha(path): return sha_bytes(path.read_bytes())
def load(path): return json.loads(path.read_text())
def canon(data): return json.dumps(data,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()
def git(*args):
    return subprocess.check_output(['git',*args],cwd=ROOT,timeout=20).decode().strip()


def main():
    prediction_path=HERE/'prediction.md';lock_path=HERE/'prediction.lock.json'
    assert not prediction_path.exists() and not lock_path.exists(), 'Already sealed; do not overwrite'
    cases=[json.loads(line) for line in (HERE/'cases.jsonl').read_text().splitlines()]
    assert len(cases)==len(PROBABILITIES)==len(REASONS)==17
    ids=[r['id'] for r in cases]
    assert len(set(ids))==17 and (HERE/'prereg/target-17.txt').read_text().splitlines()==ids
    assert len(list((HERE/'dsl').glob('*.json')))==17
    for name in ['runs','campaign','sealed']:
        assert not any(p.is_file() for p in (HERE/name).rglob('*')), f'Unexpected execution artifact: {name}'
    substitution=load(HERE/'audit/substitution.json');static=load(HERE/'audit/static.json')
    semantic=load(HERE/'audit/semantic.json');duplicates=load(HERE/'audit/duplicates.json')
    source=load(HERE/'source-evidence/manifest.json');mapping=load(HERE/'mapping.json')
    assert substitution['all_passed'] and static['validation']['valid'] and semantic['all_passed'] and duplicates['passed']
    assert not static['forbidden_output_encoding']
    assert all(c['passed'] for c in static['official_output_conversions'])
    assert [r['id'] for r in mapping]==ids
    subby={r['id']:r for r in substitution['records']};sby={r['id']:r for r in source['records']}
    for r,m in zip(cases,mapping,strict=True):
        path=HERE/r['dsl_path'];assert load(path)==r['dsl']
        assert sha(path)==m['input_sha256']==subby[r['id']]['dsl_sha256']
        assert r['answer']==[sby[r['id']]['geometric_reference']]
        for s in sby[r['id']]['sources']:
            assert sha(HERE/'source-evidence'/s['pdf'])==s['sha256']
    assert len(substitution['records'])==17 and sum(len(r['witnesses']) for r in substitution['records'])==20
    assert len(semantic['records'])==17 and len(static['geometric_references'])==17
    assert sum(c['count'] for c in duplicates['coverage'])==397
    plan=load(HERE/'prereg/execution-plan.json')
    assert plan['planned_runs']==85 and plan['seeds']==list(range(301,306))
    planned=[(cid,b['seed']) for b in plan['batches'] for cid in b['case_ids']]
    assert len(planned)==len(set(planned))==85
    assert set(planned)=={(cid,seed) for cid in ids for seed in range(301,306)}
    assert all(len(b['case_ids'])<=4 for b in plan['batches'])
    subprocess.run(['git','diff','--quiet',COMMIT,'--','src','benchmarks/research_runner.py'],cwd=ROOT,check=True,timeout=20)
    assert not git('status','--porcelain','--','src','benchmarks/research_runner.py')
    source_paths=git('ls-tree','-r','--name-only',COMMIT,'src').splitlines()
    source_hashes={p:sha(ROOT/p) for p in source_paths}
    now=datetime.datetime.now(datetime.timezone.utc).isoformat(timespec='seconds').replace('+00:00','Z')
    expected_runs=5*sum(PROBABILITIES)
    means=sum(PROBABILITIES)/17
    table=['| 問題ID | 未知変数 | 1実行の主観的正答確率 | 根拠 |','|---|---:|---:|---|']
    for r,p,reason in zip(cases,PROBABILITIES,REASONS,strict=True):
        table.append(f'| {r["id"]} | {len(r["dsl"]["variables"])} | {p:.0%} | {reason} |')
    text=f'''# Q30b 事前予測（段階1・実行未許可）

固定UTC: {now}

採用は17問（Guts 16、Team A 1）。solver・局所探索・試走・PSLQを実行せず、全問の作成・監査後にこの予測を固定した。
本タスクでcommit・pushは行わない。ユーザーがこの予測をcommit・pushしたことの確認と、**別タスクでの明示的な実行許可**の両方が必要。
このファイルを書いた後はsolverを動かさず、段階1を終了する。

## 事前予測と判定

- 主指標: 17問×5 seed=85実行中、**78正答（78/85=91.7647%、約92%）**を点予測する。
- 問題単位: **3/5以上正答する問題は16/17問**を点予測する。
- 事前の成立基準: **77/85以上の正答、かつ16/17問以上が3/5以上正答**。両方を満たす場合だけ予測成立と報告する。
- seed 301,302,303,304,305には優劣を仮定しない。各seedの事前期待値は同じ15.65/17正答（92.0588%）。これは各seedの結果を丸めて一致させるという判定ではない。
- 下表の主観確率の合計から得る期待値は78.25/85。点予測78/85はその丸め。確率は当該問題を一度も試走せずに置いた主観値で、推定済みの統計モデルではない。
- 同一問題のseed間には相関や全滅があり得るため、独立Bernoulliとは仮定しない。高リスク問題のうち1問が0〜2/5に留まる可能性を見て、問題単位は16問と予測する。
- 欠測、時間切れ、実行契約違反、クラッシュは正答に数えない。分母85・17を維持し、結果による除外・入力修正・有利なseedの再試行をしない。

未知変数0の3問（2014 Guts 3、2022 Guts 11、2024 Guts 4）は探索能力をほぼ測らない。
全17問の主集計には含めたまま、補助集計として残る14問70実行を必ず併記する。
その補助的な点予測は63/70正答、3/5以上は13/14問。易しい2013・2018も含むため、HMMTの高難度全般への一般化はしない。

## 根拠と問題ごとの予測

Q29追記では、出力形式の整数化・床がない17問で84/85正答（98.8%）だったと報告されている。
これは事後の切り分けなので、その値を今回の保証にはしない。今回もtargetを幾何量に揃え、実際に条件を満たす配置を全件確認したことから高めに予測する一方、
min/max、多数の接点・共円性・角条件・凸性を含む問題に余裕を取って約92%へ下げた。
根拠資料は `jssa/strategy/codex-tasks-1023.md` Q29追記・Q30。この17問のsolver出力は予測に一切使用していない。

{chr(10).join(table)}

原文、公式出力、幾何量の参照答、照合PDFページ、各DSLのSHA-256は [problem-list.csv](problem-list.csv) と [problem-list.md](problem-list.md)。
採用集合・問題順と各DSLのSHA-256はprediction.lock.jsonにも列挙する。

## 作成規則

現行の詳細は [authoring-rules.md](authoring-rules.md)。要点は以下のとおり。

1. 原文の点・数値・関係を直接記述する。剛体変換・鏡映の固定と定義的な作図を許し、尺度固定は角度・比だけに限る。
2. targetは幾何量そのもの。整数変数、IsInteger、既約性の証人、床、m+n・桁などの出力表記をDSLへ入れない。
3. 解法から得た長さ・座標・角度・多項式・答え由来の定数を入力へ追加しない。検算用の解析座標は監査コード・監査記録だけに隔離する。
4. 線分・半直線・内外・順序・凸性・第2交点・非退化の枝を保持する。監査不合格を直すために条件を緩めない。
5. 開発323問・new2026 20問・unseen-1983全54候補と重複しない。過去作成済みの除外台帳も照合する。
6. 取得済みHMMT公式PDFの本文と答えを画像で照合し、元PDF・URL・取得UTC・SHA-256・ページを保存する。今回はネットワークを利用しない。
7. 作成中にsolverを一度も動かさない。許す数値検算は、明示的に構成した正しい図への独立代入だけ。

指定のbenchmarks/new-2026/authoring-rules.mdは現checkout・確認できる履歴に存在しないため、読んだとは主張しない。
ユーザーの明示的な訂正、Q29追記・Q30、現存new2026の慣例に従った。unseen-1983の誤った31行目は適用しない。

## 採用監査と選定の限界

一次資料34冊の必要ページを画像確認した。全17問で条件と枝を読み合わせ、20の解析配置を70桁で代入し、144条件チェックが合格した。
最大スケール化等式残差は9.97e-71未満、target絶対誤差は1.16e-69未満（許容差1e-50）。
公開DSLの静的検証、既存採点側の参照式正規化、公式出力との対応も全件合格。
独立代入は解の存在を確認する監査で、全解の列挙・一意性の機械証明・探索成績の測定ではない。
初回Teamの補助配置1つは凸性不合格で記録を残した。同時に用意した別配置は合格し、DSLは変更していない。

ID・DSLの照合は323+20+54問全件。本文は保存済み資料の範囲（開発131問、unseen-1983 54問）で照合し、類似度上位3件も読んだ。一致0。
new2026など本文のない入力の別名・翻訳・数学的同値性を完全に証明したとは主張しない。
今回の17問は前担当の候補を継続したもので、無作為抽出ではない。早いGutsに偏り、Geometryは0問。
2021は公式Februaryアーカイブ内のSpring大会（2021-03-06）で、FEBは実施月ではなくアーカイブ区分。

## 別タスクで許可された後の実行条件

- srcは凍結版commit **{COMMIT}**（60db4b6）と同一。srcと既存research_runner・採点コードのhashを固定する。
- seed **301〜305**、各実行 **180秒・1コア**、同時実行 **最大4**。スレッド数も既存runnerの設定どおり1。
- 1コマンドを数分以内にするため、同一seedの最大4問を1バッチとして25バッチに分ける。既存runnerの180+8秒の外側監視を維持する。全85実行を1つの長時間コマンドにしない。
- 既存 `benchmarks/research_runner.py` の採点を変更せず使う。`unseen-1983/prereg/score_q19.py` と同じ **正常終了かつ正規化された答え集合の完全一致**を正答とする。部分一致・数値近似だけの一致・余分な答えは正答にしない。
- 参照答は幾何量へ正規化済み。2021はAB=`sqrt(73)-3`から公式出力7303、2022は面積=`pi/6-sqrt(3)/12`から公式出力45への対応を採点参照資料側で保持する。床が一致するだけの別の面積は正答にしない。角度は公式にも明記されたラジアン値で比較する。
- 予測・入力・資料・監査のhashを検査し、ユーザーのcommit・push確認と別タスクの許可を得てから開始する。予測の固定だけでは許可にならない。
- 結果は良否にかかわらず全件報告。5,000,000 bytes以上のファイルを作らず、探索軌跡など不要な大きいログを有効にしない。実行不能・欠測は理由を残す。

詳細な未実行のバッチ一覧は [prereg/execution-plan.json](prereg/execution-plan.json)。本タスクはここで終了する。

予測固定・実行は許可待ち
'''
    prediction_bytes=text.encode('utf-8')
    artifacts={str(p.relative_to(HERE)):sha(p) for p in sorted(HERE.rglob('*'))
               if p.is_file() and '__pycache__' not in p.parts}
    artifacts['prediction.md']=sha_bytes(prediction_bytes)
    control_paths=['benchmarks/research_runner.py','jssa/difficulty/unseen-1983/prereg/score_q19.py',
        'jssa/strategy/codex-tasks-1023.md','jssa/difficulty/new2026/README.md',
        'benchmarks/cases.jsonl','jssa/difficulty/new2026/cases.jsonl','jssa/difficulty/unseen-1983/cases.jsonl',
        'jssa/difficulty/unseen-1983/statements.jsonl','jssa/difficulty/unseen-1983/manifest.json',
        'pyproject.toml','uv.lock']
    lock=dict(schema_version=1,task='Q30b',stage=1,status='prediction_locked_execution_not_authorized',
        locked_at_utc=now,solver_executions_this_task=0,local_search_executions_this_task=0,network_used_this_task=False,
        commit_or_push_performed_by_this_task=False,
        authorization_required=['Verify user committed AND pushed these exact artifacts','Explicit solver permission in a separate task'],
        prediction_sha256=sha_bytes(prediction_bytes),
        hash_contract='SHA-256 of exact file bytes including final LF. Paths in artifacts_sha256 are relative to this directory. The lock itself is not self-hashed; a future user commit anchors it.',
        frozen_source=dict(commit=COMMIT,git_src_tree=git('rev-parse',COMMIT+':src'),
            file_count=len(source_hashes),sha256=sha_bytes(canon(source_hashes)),
            sha256_contract='SHA-256 of UTF-8 canonical JSON (sorted keys, separators comma/colon) mapping every tracked src file path at the frozen commit to its SHA-256; current bytes verified against that commit'),
        control_file_sha256={p:sha(ROOT/p) for p in control_paths},
        run_conditions=plan,
        prediction=dict(total_runs=85,point_correct_runs=78,point_run_accuracy=78/85,
            point_problems_at_least_3_of_5=16,total_problems=17,
            success_threshold_correct_runs=77,success_threshold_problems_at_least_3_of_5=16,
            subjective_expected_correct_runs=round(expected_runs,8),subjective_mean_run_probability=means,
            per_seed_expected_correct={str(seed):round(sum(PROBABILITIES),8) for seed in range(301,306)},
            independent_seeds_assumed=False,
            nonzero_variable_subset=dict(problems=14,runs=70,point_correct_runs=63,point_problems_at_least_3_of_5=13)),
        adopted_problem_ids=ids,
        adopted_problems=[dict(id=r['id'],dsl_path=r['dsl_path'],dsl_sha256=sha(HERE/r['dsl_path']),
            target=r['dsl']['target'],geometric_reference=r['answer'],official_output=sby[r['id']]['official_output'],
            n_variables=len(r['dsl']['variables']),subjective_single_run_success_probability=p,
            rationale=reason) for r,p,reason in zip(cases,PROBABILITIES,REASONS,strict=True)],
        audits=dict(all_17_passed=True,analytic_witnesses=20,condition_checks=144,
            proof_scope='Existence at explicit configurations plus semantic review, not exhaustive solution enumeration',
            duplicate_reference_counts=[323,20,54]),
        artifacts_sha256=artifacts,max_file_bytes_exclusive=LIMIT)
    lock_bytes=(json.dumps(lock,ensure_ascii=False,indent=2,allow_nan=False)+'\n').encode()
    assert len(prediction_bytes)<LIMIT and len(lock_bytes)<LIMIT
    assert all(p.stat().st_size<LIMIT for p in HERE.rglob('*') if p.is_file())
    # Final writes. No solver action exists after this point (or anywhere in this script).
    for path,data in [(prediction_path,prediction_bytes),(lock_path,lock_bytes)]:
        with path.open('xb') as f:
            f.write(data);f.flush();os.fsync(f.fileno())
    check=load(lock_path)
    assert check['prediction_sha256']==sha(prediction_path)
    assert all(sha(HERE/p)==h for p,h in check['artifacts_sha256'].items())
    assert all(p.stat().st_size<LIMIT for p in HERE.rglob('*') if p.is_file())
    print('予測固定・実行は許可待ち',flush=True)


if __name__=='__main__':main()
