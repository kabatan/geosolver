開発群の本計測 `jssa-main-j6-20261022` の元JSONが見つからないため、指示に従い評価前に停止した。最小多項式を推測・代用していない。全問評価は未完了。

| 予測 | 判定 | 理由 |
|---|---|---|
| C1：変換可能群の認証率50%以上 | 未判定 | 評価未開始 |
| C2：認証群の全体時間中央値2秒以下 | 未判定 | 評価未開始 |
| C3：同一式80%以上、余分な既約因子あり30%以下 | 未判定 | 評価未開始。stageBの全結果も未確認 |
| C4：強化版で解けない認証問題5問以上 | 未判定 | 評価未開始 |
| C5：同一問題集合の時間中央値が強化版より短い | 未判定 | 評価未開始 |

`jssa/results/mechanism-attribution/README.md` は本計測名を示し、同所の `attribution.csv` は323問×seed 0/1/2の969行を持つが、答え・最小多項式・元JSONへのパスを含まない。`exact-scaling-1024/provenance.json` もこの集計CSVを参照し、元JSONの所在は示していない。

既存の読み取り専用集計コード `jssa/difficulty/stage-taxonomy/stage_taxonomy.py` の5行目と32行目から、本来の保存先を `/home/kabatan/work/geosolver/benchmarks/local-evaluation/jssa-main-j6-20261022/runs/<ID>/<seed>.json` と確認した。しかし、この本計測ディレクトリは存在しない。`/home/kabatan/work/solver/benchmarks/local-evaluation/` 側にも存在しない。現在のリポジトリ、`/home/kabatan/work`、`/tmp`、`/mnt/c/geosolver` の読み取り可能なファイル名から、本計測名・同名アーカイブ・mechanism-attribution配下のJSONを探索しても見つからなかった。アクセス不能な私有一時ディレクトリ内は未確認。探索と参照ファイルのSHA-256は [eval/source-search.json](eval/source-search.json) に記録した。

評価試行0、再試行0、代用0。開発外29問だけの先行実行もしていない。対象・成功定義・予測・閾値は変更していない。区分別件数・2種の認証率・非所属の分析は未算出であり、未実行を失敗0件や認証率0%とは扱わない。予定条件は600秒・8 GiB・1 CPU、8並列。計時自体がないため負荷の影響も未評価。

構文修正は現行 `certify.py` の整数多項式全体を括弧に入れる処理と、Singularエラー出力の棄却処理として確認した。停止条件に達したため、合成入力・HMMT-2011の評価前実行確認、入力固定、評価実行、stageBとの結合判定スクリプトの作成・動作確認には進んでいない。`certify.py` と `verify_certificate.py` は変更していない。実行前条件が揃っていないため `pre-run-hashes.json` や結果CSVは作っていない。

C3〜C5の後日の比較先は `jssa/difficulty/exact-strong-1024/stageB/per-problem.csv`（今回の確認時点では存在しない）。stageBには対象リスト・進捗記録があるが、終了まで待つ処理や他タスクへの介入はしていない。

開発5問は評価から除外したまま。既存段階Aの別掲結果は認証2、変換不能1、実装エラー1、資源上限1（[既存CSV](per-problem.csv)）。HMMT-2011の修正版による今回の確認結果を意味しない。今回の評価値には混ぜていない。commit・push・昇格・導入は行っていない。
