"""Write the final prediction and hash lock, then STOP. Never runs a solver.

All authoring, source checks, audits, and selection must already be complete.
The lock is not a commit, a push receipt, or permission to execute.
"""
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import subprocess
from verify_bundle import verify

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[3]
FROZEN='60db4b679b04167175c51c479c87c22fa663fda0'

# Counts are rounded per-problem point predictions, not observed seed results.
PREDICTIONS={
 'AIME-2001-I-05':(5,'正三角形の辺長','2変数の二次関係。楕円上の正の非退化枝を明示。'),
 'AIME-2001-I-07':(5,'内心を通るDEの長さ','既知3辺と内心構成、辺内分の制約。4変数だが配置の枝が明確。'),
 'AIME-2001-II-04':(5,'PQの長さ','中点条件の2元線形系。幾何量の同定も有理数。'),
 'AIME-2001-II-13':(4,'CDの長さ','4変数で2つの角等式と凸性の枝を扱うため、一部の探索失敗を見込む。'),
 'AIME-2002-I-02':(5,'長方形の長辺/短辺','20円でも自由変数は4。水平行の配置を原文の図からパラメータ化。ただし多数の重複等式の負荷は未測定。'),
 'AIME-2003-I-02':(5,'緑環の面積/全円の面積','未知変数なし。100円の有限面積式であり探索の成功を示す問題ではない。'),
 'AIME-2004-II-07':(5,'長方形の周長','高さ1変数、原文の鏡映による折り返し。定義域とAD上の枝を保持。'),
 'AIME-2005-I-01':(1,'外円内で6内円外の面積','11変数で6円の接触環と多数の非重複/凸性条件。対称配置の解を入力で固定していないため最も不確実。'),
 'AIME-2005-I-07':(5,'辺長AB','原文指定60度の2辺を構成した1変数の長さ条件。'),
 'AIME-2005-II-08':(4,'共通外接線が切る弦長','4変数。内接の絶対値と接線の同側条件による複数枝の探索に失敗余地。'),
 'AIME-2005-II-12':(4,'長さBF','2変数でも尺度900、角条件とAE<BFの枝があり数値条件を割り引く。'),
 'AIME-2005-II-14':(5,'長さBE','3辺で三角形が固定され、線分上の1点の角条件。'),
 'AIME-2012-I-14':(5,'斜辺の平方h²','4変数3等式の連続族だがtargetは恒等的に一定。配置一意性を要求しない評価になる。'),
 'AIME-2014-I-01':(5,'固定靴紐経路と最低余長の合計','未知変数なしの長さ式評価。2問目の探索を要しないケース。'),
 'AIME-2014-I-10':(5,'sin²(角BEA)','転がりの定義から1変数の線形角条件。ラジアンと三角式の同定には不確実性を残す。'),
 'AIME-2014-II-10':(4,'複素平面の多角形面積','実部・虚部4変数、原文の尺度2014を維持。大きな係数と非実根の枝を割り引く。'),
 'AIME-2019-I-12':(4,'点zの実座標','1変数だがfの2重合成と内積による高次式で大きな項の相殺がある。'),
}


def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def git(*args):return subprocess.check_output(['git',*args],cwd=ROOT,text=True).strip()


def main():
    assert not (HERE/'prediction.md').exists() and not (HERE/'prediction.lock.json').exists()
    receipt=verify()
    assert receipt['passed'] and not receipt['prediction_locked']
    cases=[json.loads(x) for x in (HERE/'cases.jsonl').read_text().splitlines()]
    ids=[c['id'] for c in cases]
    assert set(ids)==set(PREDICTIONS) and len(ids)==17
    assert sum(PREDICTIONS[i][0] for i in ids)==76
    assert sum(PREDICTIONS[i][0]>=3 for i in ids)==16
    assert git('rev-parse','60db4b6')==FROZEN
    assert not git('diff',FROZEN,'--','src'), 'current src differs from frozen source'
    assert not git('ls-files','--others','--exclude-standard','src'), 'untracked source files'
    timestamp=datetime.now(timezone.utc).isoformat(timespec='seconds').replace('+00:00','Z')
    rules=(HERE/'authoring-rules.md').read_text()
    duplicate=json.loads((HERE/'audit/duplicate-audit.json').read_text())
    other_count=next(r['count'] for r in duplicate['coverage'] if r['group']=='unseen2b_snapshot')
    table=['| 問題 | raw幾何量 | 変数数 | 成功数の点予測 / 5 | 根拠 |',
           '|---|---|---:|---:|---|']
    for c in cases:
        n,quantity,why=PREDICTIONS[c['id']]
        table.append(f'| {c["id"]} | {quantity} | {len(c["dsl"]["variables"])} | {n} | {why} |')
    text=f'''# Q30a 予測固定 — 未使用AIME 17問、段階1

固定UTC: `{timestamp}`

**solver未実行。予測を固定したところで本タスクを終了する。**
ユーザーが予測をcommit・pushしたことを確認し、さらに別タスクで明示的な実行許可を
受けるまで実行しない。ファイル作成やcommitだけを許可と解釈しない。
本タスクではcommit・pushを行っていない。

## 事前予測

17問×seed 301〜305の**85実行中76正解、89.4%**を点予測とする。
**5実行中3回以上正解する問題は17問中16問**を点予測とする。

| 指標 | 点予測 | 主観的な約90%予測区間 | 予測成立と呼ぶ閾値 |
|---|---:|---:|---:|
| 実行ごとの正答率 | 76/85 = 89.4% | 65〜82/85 = 76.5〜96.5% | 73/85以上（85%以上） |
| 問題ごと3/5以上正解する数 | 16/17問 | 14〜17問 | 15/17問以上 |

seedの番号自体には性能差の根拠がないので、各seedでの共通の期待正答率も89.4%
（17問あたり15.2問相当）と置く。特定seedで何問解けるかを観測した値ではない。
下表は問題ごとの5実行成功数を整数に丸めた点予測であり、5/5の行も成功を保証しない。
区間は独立Bernoulliの信頼区間ではなく、問題間・seed間の依存と小標本を含む主観予測。

根拠はQ29追記の「出力形式の整数制約がない17問で84/85」と、
`unseen-1983/failure-audit/d/prediction.md`に記録された2026年20問の55/60。
前者は事後の切り分けなので98.8%を無条件で外挿しない。
今回も出力変換をDSLから除いたが、11変数の円の輪、大きな原文尺度、角条件、
高次式の相殺、既存の厳密同定、共有機の時間制限を考慮して89.4%へ割り引く。
2問は未知変数なしの式評価なので、集合の全問が難しい探索問題という主張はしない。
候補の採否・入力は新規solver実行の成績に基づかない。

## 採用問題と問題別予測

{chr(10).join(table)}

全問題文・条件との対応・幾何量参照値・正解図・枝の根拠は`cards/`、
`mapping.json`、`references.json`、`audit/substitution.json`。
原文の整数答はprimary Answer Keyから抽出した。幾何量は手計算の独立構成で確認し、
採点変換後の値が17問すべてでAnswer Keyと一致する。

## 母集団・採否・作成監査

2000〜2005・2010〜2019年、AIME I/II、各1〜15の全480スロット。
年→I/II→番号の順で確認し、83問を既存重複、380問を主題・表現上の対象外とした。
採用は監査合格17問すべて。15〜20問の指定範囲を満たす。
不採用の理由は全件`manifest.json`と`audit/selection.csv`に固定した。
20問に達するために最大最小・整数問題等を解法で単純な求値へ置き換えない。
対数の周長、piを含む分母の面積比は既存の厳密答型では採点できないため対象外。
3成分比の問題も、単一スカラーのraw幾何量という規則から対象外とした。

ユーザー提供の保存HTML64ページを`source-evidence/`へコピーした。
0バイト・404・不完全HTMLは不採用とし、最終的に全64ページでページtitle、
完全HTML、15問題節または15整数答、SHA-256を確認した。
最初に無効だったページは、ユーザーの再取得で有効な内容が到着した後に取り込んだ。
HTML内のアーカイブ日時、コピーUTC、元ファイルmtimeを分けて記録し、
こちらがダウンロード日時・HTTPステータスを観測したとは主張しない。
外部curl・解説ページ参照はしていない。

機械的重複検査は開発323問、new2026の20問、unseen-1983の54問、
他担当bの取得時点の{other_count}問、および採用17問内部に対して実施した。
IDの大小文字・I/1・II/2・先頭ゼロを正規化し、IDを除いたDSL、
宣言順を保った名前の置換と条件順を無視するAST、取得可能な正規化問題文も比較した。
全方式で重複0件。既存の一部に原文がないため、数学的同値性を完全に網羅する検査ではない。

全17問の静的AST検査663式、手計算の正解図18配置の90桁代入が合格した。
等式は `abs(left-right)/(1+abs(left)+abs(right)) < 1e-70`、
厳密不等式は正の余裕、非厳密不等式は90桁丸め誤差を許した符号検査。
targetと手計算参照値も相対残差1e-70未満。整数変数・既約性証人・床・剰余はDSLにない。
GeoSolverのエンジンをimportせず、探索・局所探索・PSLQを起動していない。
既知の参照式をexact descriptorへ変換する採点契約検査は求解成績ではない。
代入は存在確認であり、全解の自動網羅探索ではない。目標一意性の手計算を各カードに添えた。

## 別タスクで許可を受けた場合の実行条件

- 凍結版の`src`: commit `{FROZEN}`（短縮`60db4b6`）。
- srcのgit tree: `{git('rev-parse',FROZEN+':src')}`。
- source tree hash: `sha256:d8fd9bb8392ad2984276bab3386e033669246ee79586317917c322d31b4541f5`。
- seedは301,302,303,304,305。17問×5=85実行を全件報告する。
- 各実行`time_limit_seconds=180`、1コア、CPUを割り当て、同時実行は最大4。
  外側プロセスの終了判定等は既存research_runnerの契約を使い、solver時間を延ばさない。
- `cases.jsonl`と`dsl/`の固定bytesを入力とする。監査座標、初期値、探索箱は渡さない。
- `unseen-1983/prereg/score_q19.py`と同じ
  `research_runner._answer_keys`、`read_run_outcome`、`describe_exact`による
  **正常終了かつ全返却解集合の厳密一致**。research_runner自体は変更しない。
- runnerにはraw幾何量の参照値を渡す。`score.py`はこの比較に加え、返却された厳密値を
  問題文の整数形式へ変換してAnswer Keyと照合する。どちらかだけの一致は不正解。
  同じm+nを与える別の幾何量、余分な解、数値近似だけの一致を正解にしない。
- 変換は分子+分母、平方した値の分子+分母、既約分母、根号の標準形、床、
  sqrt(3)係数の剰余など、`references.json`の全17行で固定する。
  既存runnerに汎用のm+n変換はないことを確認したため別アダプターに置いた。
- 答えなし・誤答・余分な解・異常終了・実行契約違反・欠落を分母85から除外しない。
  再実行で失敗を置換せず、結果を見て問題の除外・DSL修正・seed追加を行わない。
- 予測commitのhash、push済みの確認、実行許可、凍結src、環境、CPU、入力hashを
  将来の実行receiptへ記録する。現時点ではそのreceiptは作らない。
- 各ファイルは5,000,000 bytes未満。大量の軌道を保存しない。
  採点に必要な全answer descriptorと終了情報を欠かさず、5MBを超えるログは作らない。

## この時点の実行ゲート

`prediction.lock.json`はこのファイル、全DSL、作成規則、一次証拠、採否・監査・採点コードの
SHA-256とUTCを保存する。ロック自身の自己hashは含めない。
**段階1のsolver実行数は0。ユーザーのcommit・push確認は未了。実行許可は未取得。**
別タスクでの明示的な許可まで、この予測固定状態を維持する。

## 固定した作成規則全文

以下は`authoring-rules.md`の固定時点の全文。

```text
{rules.rstrip()}
```
'''
    # This is the first write of either requested prediction artifact.
    prediction=HERE/'prediction.md'
    prediction.write_text(text)
    external_paths=['benchmarks/research_runner.py','benchmarks/cases.jsonl',
                    'jssa/strategy/codex-tasks-1023.md','jssa/difficulty/new2026/README.md',
                    'jssa/difficulty/new2026/cases.jsonl','jssa/difficulty/unseen-1983/cases.jsonl',
                    'jssa/difficulty/unseen-1983/prereg/score_q19.py',
                    'jssa/difficulty/unseen-1983/failure-audit/d/prediction.md',
                    'src/geosolver/engine-lock.json','src/geosolver/dependency-lock.json','uv.lock']
    artifacts={str(p.relative_to(HERE)):sha(p) for p in sorted(HERE.rglob('*'))
               if p.is_file() and '__pycache__' not in p.parts and p.name!='prediction.lock.json'}
    lock=dict(schema_version=1,state='prediction_fixed_execution_not_authorized',
              locked_at_utc=timestamp,prediction_path='prediction.md',prediction_sha256=sha(prediction),
              adopted_problems=[dict(id=c['id'],dsl_path=c['dsl_path'],dsl_sha256=sha(HERE/c['dsl_path']),
                                    statement_sha256=hashlib.sha256(c['problem_statement'].encode()).hexdigest(),
                                    predicted_successes_out_of_5=PREDICTIONS[c['id']][0]) for c in cases],
              prediction=dict(correct_runs=76,total_runs=85,run_accuracy=76/85,
                              run_count_subjective_90pct_interval=[65,82],
                              problems_at_least_3_of_5=16,total_problems=17,
                              problem_count_subjective_90pct_interval=[14,17],
                              run_success_threshold=73,problem_success_threshold=15),
              execution=dict(frozen_commit=FROZEN,src_git_tree=git('rev-parse',FROZEN+':src'),
                             source_tree_hash='sha256:d8fd9bb8392ad2984276bab3386e033669246ee79586317917c322d31b4541f5',
                             seeds=[301,302,303,304,305],time_limit_seconds=180,cores_per_run=1,maximum_parallel_runs=4,
                             scoring='unmodified research_runner exact-key set equality and normal completion, plus fixed official-output conversion',
                             user_commit_push_confirmed=False,explicit_execution_permission_in_separate_task=False,
                             user_prediction_commit=None),
              solver_execution_count_in_stage1=0,local_search_execution_count_in_stage1=0,
              input_witness_injection=False,authoring_checkout_commit=git('rev-parse','HEAD'),
              preseal_readonly_verification=receipt,
              external_reference_sha256={p:sha(ROOT/p) for p in external_paths},artifact_sha256=artifacts,
              self_hash_note='lock excludes itself; prediction.md and every other locked artifact are SHA-256 hashed',
              file_size_limit_bytes=5_000_000)
    lockdata=(json.dumps(lock,ensure_ascii=False,indent=2)+'\n').encode()
    assert len(lockdata)<5_000_000
    (HERE/'prediction.lock.json').write_bytes(lockdata)
    # Read-only byte integrity checks are the final action. No solver entrypoint exists here.
    assert verify()['prediction_locked']
    print('予測固定・実行は許可待ち')


if __name__=='__main__':main()
