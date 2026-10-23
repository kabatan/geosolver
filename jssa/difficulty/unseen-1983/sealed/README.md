# Q19：凍結版・未使用54候補の封印実行

**54候補×5 seedの全270実行を完了し、封印した。**
結果本文を目視せず、各問の答え・正誤、正答数・成功率は表示・集計・要約していない。

## 封印記録

- 実行開始：2026-10-23 21:48:59 JST（12:48:59 UTC）。
- 実行完了：2026-10-23 22:43:55 JST（13:43:55 UTC）。
- tar作成・SHA-256確定：2026-10-23 22:44:05 JST（13:44:05 UTC）。
- 保存済みraw：270／270件。エラー0件、タイムアウト95件。
  実行条件の不一致0件、保存hookの不備0件。欠測0件、除外0問。
- タイムアウトは、外部監視の `timed_out` またはsolverの
  `termination_reason == "time_limit_reached"` の件数。
  エラーはrunner例外、CLI非0終了、結果欠落、通常終了状態以外の件数で、
  タイムアウトと重複しうる。答えの有無や正誤の集計ではない。
- tar：`q19-frozen-201-205.tar`、932,556,800 bytes、通常ファイル2,767件。
  保存先は末尾に示す作業フォルダ外のraw領域。

封印tar全体のSHA-256：

```text
ef75dabbc2c92859d03797d825475f6f906366a595226e2335b112a69ea65e18
```

54問×seed 201〜205のファイル集合、終点・stats・stdout/stderrの保存項目、
tar内全ファイルのチェックサム、ソート順・mtime・所有者・modeを機械的に検査した。
同じ固定条件でtarをファイルへ書かず再生成し、ストリームのSHA-256が上記と完全一致した。
solverの追加実行はしていない。srcの実行後ハッシュと凍結版との差分も再確認済み。

## 対象と条件

- 対象は実行開始前の `../manifest.json` の `selected_candidate` 全54問。
  `../cases.jsonl` の埋込みDSL、`../dsl/` のbytes、入力固定記録のhashの一致を確認した。
- Q18の監査結果は読まず、除外0問で54問すべてを実行した。
  監査で必要になった除外は、結果を開封する前に別途固定する。
- seed：201、202、203、204、205。54問×5 seed＝270実行。
- 各実行180秒、1コア。最大8並列。数値ライブラリのスレッド数も1。
  8本の独立した物理コア代表CPU（0〜7）に固定し、CLI・workerへ継承する。
- `codex-tasks-1023.md` のQ19にある16並列・監査後の対象という記載より、
  今回のユーザー指示である最大8並列・除外前の54問全件を優先した。
- 介入版は実行していない。高負荷の共有計算機のため、時間は参考値として保存した。

## 凍結版の確認

ローカルに存在するコミット `60db4b679b04167175c51c479c87c22fa663fda0` と
現在のsrcに差分がないことを確認した。両者の `src` Git treeは
`ab7b6ceabc60b205d78bd4fc9d8a08b5f605aae3`。
開始時HEADは `adf64bb1d384b0500ffb3c5551d64553d6a1c437`。

`full-solver-redraw/run.py` の `FROZEN_HASH` と同じengine source hashは
`sha256:d8fd9bb8392ad2984276bab3386e033669246ee79586317917c322d31b4541f5`。
`verify_engine_lock()` と `benchmarks/research_runner.py::runtime_fingerprint()` により、
engine lock・依存環境・この作業コピーのsrcをimportしていることを確認した。

`multiplicity/answer.md` にある246個のsrc Pythonファイルの統合SHA-256も
`7b845d25863158f2023e4640aa5b37141b1c227caf199a7ec4ab235fd2541e11` と一致した。
計算法は `multiplicity/experiment.py::source_fingerprint()` と同じで、
src内の `.py` をパス順に並べ、各ファイルのSHA-256とrepo相対パスの組のリストを
`json.dumps(entries).encode()` にしてSHA-256を取る。
同回答は旧版との同一性を主張していないが、今回は実際のコミット差分・Git treeも照合した。
実行終了時にもこれらを再確認し、tar内の記録に残した。

## 実行経路と保存

`../build_cases.py`、`../verify_static.py`、`../README.md` を読んで形式を確認した。
DSLは公開 `GeometryProblem` 形式で、内容の変換はしていない。
入力をraw領域へbytesのまま複製し、そのスナップショットだけをsolverへ渡す。
公式・二次資料の答えファイルとQ18の監査ファイルは読まない。
tar内の `input-validation.json` は既存ランナーの形式検査記録で、
そこでの `truth_verified_count` は省略時の既定値に由来する。
Q18の監査や答えの照合を済ませた意味ではなく、今回の54問は候補のままである。

`full-solver-redraw/README.md` と同じく、既存の
`benchmarks/research_runner.py::_run_one` を呼ぶ。
公開CLI → EngineRunner → 実worker、180秒、cores=1、外部監視188秒、
プロセスツリー終了処理・実行src/依存環境/affinity検査は既存の経路を使う。
`assess_campaign`、`summarize_campaign`、`read_run_outcome` は呼ばない。

保存専用hookはjssa側に置いた。探索の入力・候補選定・返り値は変えず、
`FloatCandidate.__post_init__` の本来の処理後に全フィールドをJSONLへ追記する。
これにより局所探索の終点に加え、NOMAD等の候補座標・残差・出自も残る。
通常の結果JSONに含まれる精密化候補・pipeline summary・counters・phase timingsも丸ごと保存する。
CLIの `TemporaryDirectory` の削除だけを抑止し、request、worker artifact、保存receipt、
worker stdout/stderrを残す。外側CLIのstdout/stderrも既存raw JSONに保存する。
ログは人間向けの画面へ流さない。保存用の処理時間も180秒内に含まれる。

初回の入力事前検査では335項の和がPython既定の再帰上限に達し、solver起動前に停止した。
入力を変更せず扱うため、ランナー・CLI・workerすべてに共通して
`sys.setrecursionlimit(10000)` を設定した。その後に本実行を開始した。
初回の事前検査記録はraw領域の `q19-preflight-only-001/` に別保存し、本実行と混ぜていない。
保存hookは合成候補で、元の候補と値が同じであることとJSONL記録を検査した。

repo直下からの実行コマンド：

```bash
env PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1 /home/kabatan/work/solver/.venv/bin/python -B jssa/difficulty/unseen-1983/sealed/run_sealed.py run > /tmp/claude-1000/-home-kabatan-work-solver/d461234c-f155-4314-9ede-192e5987bbce/scratchpad/sealed-raw/q19-console.log 2>&1
```

進捗コマンドは運用上の完了・エラー・タイムアウト件数だけを出す：

```bash
env PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 /home/kabatan/work/solver/.venv/bin/python -B jssa/difficulty/unseen-1983/sealed/run_sealed.py progress
```

## 封印の手順

raw領域：
`/tmp/claude-1000/-home-kabatan-work-solver/d461234c-f155-4314-9ede-192e5987bbce/scratchpad/sealed-raw/`

本実行の全出力・入力スナップショット・実行コード・実行前後の環境記録を
同領域の `q19-frozen-201-205/` に保存した。結果を人間が開かず、機械が運用状態だけを取り出した。
各問の返した答え・内部成功フラグ・受理件数・残差・公式解との一致は集計しない。
エラーとタイムアウトは別フラグで、重複しうる。

tar内のファイルを相対パスの昇順とし、全通常ファイルのmtime=0、uid=gid=0、
uname/gname空、mode=0644に固定する。GNU tar形式、gzipなし。
ファイルごとのSHA-256もtarの内側にだけ置く。
同領域の `q19-frozen-201-205.tar` を作り、tar全体のSHA-256だけをこのREADMEに記録した。
結果の開封は、各線の事前登録と監査に基づく除外が固定された後に別の担当が行う。

**rawディレクトリ・tar本体はcommit禁止。** 大きな出力はこの `sealed/` 内に置かない。
srcと既存ファイルは変更していない。git fetch・ネットワーク・commit・pushも行っていない。
