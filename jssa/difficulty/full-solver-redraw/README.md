# sol-7：完成した solver の出発点選び直し

本計算は未実行。事前登録 `jssa/difficulty/start-feasibility-1023/preregistration-4.md` をそのまま実装する。対象は `predictions.csv` の150問、seed 101・102・103、通常／選び直しの900実行、各180秒。本計算の並列数は6で固定する。src/、事前登録、予測表は変更していない。

## 実行経路と介入

`run.py` は既存本計測の `benchmarks/research_runner.py::_run_one` を呼ぶ。公開 CLI → EngineRunner → 実 worker の経路、180秒、cores=1、数値ライブラリのスレッド数1、外部監視の180+8秒、子プロセスの終了処理は既存コードを使う。通常終了後は同じ `assess_campaign` でも採点し、条件別の `assessment.jsonl` を残す。採点器が例外を出した場合は `assessment-error.txt` を残し、エラーを含む per-run の書き出しを続ける。

worker に限って `hook/sitecustomize.py` が hook を読み込む。CLI、symbolic worker、Windows の process_gate には介入しない。読み込み失敗は終了コード91で失敗とし、通常条件への無言のフォールバックはしない。

- 通常：`_build_local_start_sequence_with_kinds` は元の関数のまま。観測用ラッパーだけを両条件に付ける。
- 選び直し：元の関数が返した各点を hard feasibility で検査し、不適なら元と同じ lower/upper の箱から `np.random.default_rng([外部seed, 99, 出発点番号])` の一様乱数で選び直す。元の点を含め2001回、再抽選は最大2000回。全て不適なら最後の点。番号は各 builder が返す列内の0始まり index。内部探索 seed や呼出し回数を乱数キーに追加しない。
- 検査は本体の `evaluate_float_hard_feasibility(..., include_margins=False)`。例外は不適とするが期限切れは伝播する。既存の solve deadline を延長しない。生成・検査・観測にかかった時間も180秒に含まれる。
- 列の kind、順序、prefix 数は維持する。NOMAD 自体とその候補、精密化、厳密同定、最終検証は変更しない。NOMAD 候補がこの builder の出発点列に含まれた場合は、その出発点のコピーだけを同じ規則で検査する。

同じ問題・seed の組を最大6組ずつ取り、通常の波 → 選び直しの波 → 次の通常の波、の順で交互に実行する。波の間には全実行完了の待ち合わせを置く。同じ組は同じ CPU slot に割り当て、両条件の最大並列数は同じ6。最後の端数の波も両条件で同じ件数。再開時は完了済みを飛ばすため、その波の稼働数が減ることがある。

## Windows PC での本計算

前提：repo 全体を同じリビジョンで用意し、repo 直下から PowerShell で実行する。Python は既に環境構築済みの64bit CPython 3.12 の `.venv\Scripts\python.exe` を使う。Linux の venv はコピーできない。`pyproject.toml` と `src/geosolver/dependency-lock.json` に一致する依存関係（Windows 用 PyNomadBBO を含む）と geosolver の配布メタデータが必要。以下の手順はインストールや環境更新をしない。少なくとも6 slot を使える計算機、空きメモリ・空きディスク、スリープしない電源設定を事前に確保する。他の大きな計算を止める。

```powershell
# カレントディレクトリは、この repo のルート
$py = (Resolve-Path .\.venv\Scripts\python.exe).Path
$env:PYTHONDONTWRITEBYTECODE = '1'
$env:PYTHONUTF8 = '1'
& $py -B jssa/difficulty/full-solver-redraw/checks.py
if ($LASTEXITCODE -ne 0) { throw 'protocol checks failed' }
& $py -B jssa/difficulty/full-solver-redraw/run.py --full --jobs 6 --check-only
if ($LASTEXITCODE -ne 0) { throw 'preflight failed: runtime/source/input mismatch' }

# ここから本計算900実行（この作業セッションでは実行していない）
& $py -B jssa/difficulty/full-solver-redraw/run.py --full --jobs 6
if ($LASTEXITCODE -ne 0) { throw 'runner stopped; preserve outputs and resume with the same command' }

# 集計だけをやり直す。solver は一度も呼ばない
& $py -B jssa/difficulty/full-solver-redraw/aggregate.py --refresh-per-run
if ($LASTEXITCODE -ne 0) { throw 'aggregation failed' }
```

初回 preflight は本計算の結果ファイルを作らない。凍結版の engine lock・ソースハッシュ、実行環境の依存関係、事前登録と予測表の固定ハッシュ、対象 DSL を検査する。判定基準・対象・seed・制限時間を変更するオプションはない。環境不一致を無視するオプションもない。

再開は同じ PC・同じ repo パス・同じ Python 環境・同じコード・`--jobs 6` で、上と同じ `run.py --full --jobs 6` をもう一度実行するだけ。`manifest.json` が条件・入力・環境・機械・並列数の変化を検出したら停止する。コードや入力を直して無理に既存 manifest を合わせないこと。

raw JSON が完了の目印で、正答でない実行・エラーも再実行しない。raw があり receipt だけが欠ける場合も自動回復して飛ばす（`--recover` は互換用で不要）。その場合、失われた loadavg は空欄、`receipt_recovered=1`。raw がない途中の実行だけ再試行し、既存の audit は `*.interrupted-*.jsonl` に保存する。通常の中断時は実行中タスクの終了待ちが発生することがある。OS のファイルロックで同じ出力先へのランナー二重起動を防ぎ、終了・クラッシュ時にロックは解除される。`runner.lock` ファイル自体は残ってよい。

計算時間は900×180÷6 = 7.5時間が solver 部分の最大枠。既存の外部監視188秒を全実行が使う場合は約7.83時間。起動・採点・波の待ち合わせ・機械の負荷を含め8〜9時間以上の連続稼働枠を確保する。これは性能の予測ではなく実行枠の目安で、短い実行が多ければ早く終わる。

Windows では psutil の CPU affinity を使用し、POSIX 専用の taskset は呼ばない。Linux の物理コア topology ファイルがなければ取得可能な論理 CPU の先頭から slot を選ぶため、Windows で物理コア独立性までは保証しない。CPU affinity が取得できない環境では CPU 固定なしで動作し、CPU は空欄、affinity は null として記録する。個別の固定失敗・実行時の不一致は記録してエラー計上する。cores=1 と数値スレッド数1は維持する。

loadavg は `os.getloadavg()` が使える環境だけ記録する。Windows 等では開始・最大とも空欄、`load_samples=0` で動く。psutil が生成する初期の仮の0を代用しない。取得可能な環境では開始値と、実行中0.25秒間隔の観測最大を1/5/15分それぞれ記録する（連続時間の厳密な最大ではない）。一時ファイルも各実行の `*.temp/` 内に向け、bytecode の書き込みを止める。

## 出力と確認

本計算の出力はすべてこのフォルダ内。smoke は `smoke/` 配下に分離し、本計算には読み込まない。

| ファイル | 内容 |
|---|---|
| `manifest.json` | 対象、seed、機械、CPU、入力ハッシュ、環境、集計用乱数 |
| `{normal,redraw}/campaign-manifest.json` | 既存採点器用の本計測と同じ manifest |
| `{normal,redraw}/runs/<id>/<seed>.json` | 既存ランナー形式の raw、solver 結果、stdout/stderr |
| 同じ場所の `*.receipt` | 開始終了時刻、loadavg、観測数、runner error、audit 要約 |
| 同じ場所の `*.starts.jsonl` | patch 導入、探索呼出し、生成・予定・実使用の各イベント |
| `{normal,redraw}/assessment.jsonl` | 既存の本番採点器の集合一致判定 |
| `per-run.csv` | 全実行の採点、費用、タイムアウト・エラー、loadavg、介入確認 |
| `per-problem.csv` | 各問の条件別 seed 平均、費用差、正答率、予測値 |
| `score.md` | S1・S2・S3、件数とエラー、介入の確認状況 |

`starts_generated` は生成完了した点数、`redraws_generated` はその再抽選数、`generated_exhausted` は2001回とも不適だった点数。`starts_consumed` は LM/Powell の実呼出し境界まで届いた点だけ。生成した点と optimizer 入力のハッシュを照合し、`consumed_matching_generated`、`redraws_consumed`、`consumed_hard_fraction` を残す。通常条件は `builder_patched=0`、`starts_generated=0`、`redraws_*=0`、元の builder の同一性を確認する。探索経路がこの builder を通らない実行は `starts_consumed=0` で、形の割合は空欄。これはエラーでも選び直しの実使用の証拠でもない。`audit_verified=1` は観測と関数同一性の検査が通った意味で、実使用の有無は別列を見る。途中で期限を迎えた生成は完了点の統計に含まれず、raw の結果と未使用件数を合わせて確認する。

実行前に、preflight が通ること、本計算用の root `manifest.json` が初回なら存在しないこと、再開なら同一 PC のものであることを確認する。Linux で取得した `smoke/manifest.json` は Windows 用に書き換えない。配布した smoke は実証記録であり、Windows で `--smoke` を実行すると機械の違いにより再開が拒否される。本計算の初回起動には影響しない。

実行後に以下を確認する。

- `score.md` が900/900実行、150/150問。両条件450実行ずつであること。
- 通常条件は全て `builder_patched=0` と再抽選0。選び直し条件では worker が起動した実行の `builder_patched=1` と、使用された点の照合が一致すること。実使用0の実行と audit 未確認も件数を見る。
- `external_timeout` と `error` の件数、`execution_contract_issues`、`runner_error`、条件別採点器のエラー記録。これらを除いて集計し直さないこと。
- 正答で180秒以内の実行のみ C=その solver elapsed time、それ以外は C=180。プロセス起動込みの時間は別列に残す。外部タイムアウトとエラーは費用180、正答0で別計上する（両者は重複することがある）。
- S1 は各問3 seed の平均の差（選び直し−通常）を150問で平均。問題単位の paired percentile bootstrap 10,000回、95%区間の上端<0かつ平均<0。集計専用 seed 102304 は solver 乱数と独立。
- S2 は正答率差（選び直し−通常）≥−0.01。S3 は `pred_delta` と費用減少（通常−選び直し）の Spearman 順位相関≥0.3。同順位は平均順位、予測欠測は補完せず122問を使用し件数を示す。

未完了でも、raw がある範囲を `aggregate.py --refresh-per-run` で書き出せる。両条件・全 seed が揃った問だけで暫定値を出し、900実行が揃うまでは S1〜S3 を判定しない。エラー実行は欠測として除外しない。`per-run.csv` からの集計だけなら `--refresh-per-run` を外す。全問未対の時は per-problem まで書き、判定できない旨で停止する。

## 動作確認（本計算ではない）

実施環境：Linux、指定の `/home/kabatan/work/solver/.venv/bin/python`、並列数2、seed 101、180秒。次のコマンドを実行した。

```bash
PYTHONDONTWRITEBYTECODE=1 /home/kabatan/work/solver/.venv/bin/python -B jssa/difficulty/full-solver-redraw/checks.py
PYTHONDONTWRITEBYTECODE=1 /home/kabatan/work/solver/.venv/bin/python -B jssa/difficulty/full-solver-redraw/run.py --smoke --jobs 2
PYTHONDONTWRITEBYTECODE=1 /home/kabatan/work/solver/.venv/bin/python -B jssa/difficulty/full-solver-redraw/aggregate.py --smoke --refresh-per-run
PYTHONDONTWRITEBYTECODE=1 /home/kabatan/work/solver/.venv/bin/python -B jssa/difficulty/full-solver-redraw/aggregate.py --smoke
```

AIME-2023-I-12 と HMMT-2024-FEB-GEO-04 の両条件4実行は正答したが、早い探索経路で終了し、LM 出発点の生成・使用は0だった。そのため、既存の本計測で追加探索に入っていた AIME-2014-I-13 を3問目として加えた。最初の4実行は再実行していない。smoke のみ対象追加と入力ハッシュの履歴を `smoke/initial-two-manifest.json` と `smoke/manifest.json` の `smoke_extension` に保存した。最初の hook との差は、検査用にログを明示的に閉じる関数を返す変更だけ。本計算の150問・判定基準・乱数・制限時間は一切変更していない。

6/6実行が既存採点器の集合一致で正答。外部タイムアウト0、エラー0。全実行で開始・最大 loadavg を取得できた。追加問題での確認値は以下。

| AIME-2014-I-13 / seed 101 | 通常 | 選び直し |
|---|---:|---:|
| builder_patched | 0 | 1 |
| audit_verified | 1 | 1 |
| 生成した点数 | 0（生成関数は無改変） | 3345 |
| 生成時の再抽選回数 | 0 | 12908 |
| 実際に LM に渡した点数 | 132 | 116 |
| 実使用点と生成点のハッシュ一致 | 対象外 | 116/116 |
| 実使用点の再抽選回数 | 0 | 291 |
| 実使用点の hard feasibility 比率 | 62/132 = 0.469697 | 116/116 = 1.0 |
| C（秒） | 130.675187 | 152.498276 |

通常条件は3問とも元の builder の同一性を保持、patch 無効、再抽選0。追加問題の選び直し条件では、差し替えた点が実際の LM 入力になったことまで確認できた。小規模な確認であり、有効性を判定しない。この1問では選び直しの費用は増えている。

`smoke/per-run.csv`（6行）→ `smoke/per-problem.csv`（3行）→ `smoke/score.md` を生成し、独立した集計コマンド2通りも成功した。S1〜S3 は数値だけ表示し、事前登録の成否は「判定しない」。S3 の利用可能予測は本計算では122問、smokeでは3問。

再開コマンドを再実行し6件すべて `skip`、solver の再実行0を確認。raw・receipt・audit の全18ファイルはハッシュと更新時刻が不変だった。`smoke/resume.log`、`aggregate-1.log`、`aggregate-2.log`、`verification.json` に確認結果を保存した。

`checks.py` は8検査に成功（`smoke/checks.log`）。乱数系列、初回を含む2001回と最後の点、期限切れ伝播、通常 builder の同一性、optimizer への配送、集合一致と費用、タイムアウト・エラー込みの3 seed 集計、loadavg/affinity 非対応時、二重起動ロックを確認した。検査中に作る合成データは一時ディレクトリ内で削除し、smoke の実測CSVには混ぜていない。

本計算用には `run.py --full --jobs 6 --check-only` の事前検査だけを実施して成功した。900実行は走らせておらず、このフォルダ直下には本計算の manifest・per-run・per-problem・score・条件別ディレクトリを作っていない。src/ 等の既存ファイルは変更せず、依存関係のインストール・環境更新・commit・push も行っていない。

Windows 実機での起動・Job Object・affinity の検証は未実施。Linux での実動作確認と非対応 API を模擬した検査までである。Windows では先に上記の protocol checks と full の check-only が通ることを確認する。
