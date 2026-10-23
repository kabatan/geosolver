この記録はQ43bの探索結果を読むための補足。最終判定は `answer.md`、全試行の集計は
`summary.json`・`per-run.csv`・`effects.json`、180秒点検は `followup-summary.json` を参照。

**比較の単位。** 20問×2 seed（43021、43022）を対にする。12形式で480行だが、
式を変えられない44行は原形の同じ実行を参照するaliasで、独立な試行は436件。
cos・vectorは各16問32試行、tanは6問12試行だけが実際の書き換え。
失敗・timeoutを分母から除かず、参照答の厳密なcanonical_keyの集合との完全一致で採点する。
45秒は凍結runtimeの内部APIを使った探索であり、公開APIの通常180秒の成績ではない。

**同値性と数値計算。** 非負の両辺の2乗、無向角の範囲で単射なcosおよび
`tan((θ−π/2)/2)`、元の非退化条件を保つ直線円接線の表現を用いる。
根拠は `equivalence.md`。`form_cos` と `form_vector` は長さ・角・接線をまとめて変える。
観測された差を「cosだけ」「判別式だけ」の効果とは解釈できない。
元変数の探索箱は、今回の全240入力で原形から変わっていない。
独立ダミーはt>0と距離1からt=1に決まるが、変数次元が増えるため、同じ乱数seedでも
元変数に同一の初期点が渡ることを保証しない。

既存 `equivalence.md` の「Line構成は残る」という一般的な説明には補足が要る。
判別式版ではインラインのLine呼出しが消える場合がある。今回の接線3問では、
JMO-2013-PRE-05は残る2つのCircumcircleがP≠R・Q≠Sを要求し、
JMO-2024-PRE-06はA=(0,0)、B=(5,0)なのでA≠B、
HMMT-2007-FEB-GEO-04は残る距離²=49および面積のguardによりB≠C。
従ってこの3問では非退化性が維持される。変換コードを別の問題へ広げるときに、
直線の退化を常に排除できる一般的な実装だとは主張しない。今回の固定入力は変更していない。

**ソースから分かることと未確定な原因。** 凍結60db4b6の
`src/geosolver/engine/standard/refinement/mpmath_refiner.py` の
`_zero_constraint_plans` と `_smooth_zero_constraint_residuals` は、特定の構文の
Distance=0やIsTangent=0にだけ精密化用の式を適用する。
`problem/tangency_contacts.py` も接点・円の構文を照合するので、数学的に同値な式が
同じ処理に入る保証はない。`refinement/analytic_jacobian.py` も対応する命令を限定する。
これは表現依存性の説明候補であり、処理を一つずつ切り替えた因果検証は今回行っていない。

`evaluation/scaled_score.py` は残差の2乗和を使う。等式の重複は同じ解集合を保つが、
最初の1本の重み、guard罰則との相対重み、評価・精密化の処理量を変え得る。
`repeat_all_32` は**入力に書かれた**等式の32重化であり、loweringが自動追加する条件や
guardまで32倍にする操作ではない。入力の長さだけから一律の32倍の遅さを予言しない。
`evaluation/snapshots.py` は必要な作図を遅延評価する。未参照点の影響が小さいことは
この実装と整合するが、それだけで実測時間が完全に同じになるとは言わない。

**図の意味。** accepted候補を元変数へ射影し、相対許容1e-7でまとめた保存図の集合を比較する。
全解集合を列挙したわけではない。連続的に動かせる図や同じ答えを持つ異なる候補もあり、
候補数を幾何的な枝の総数とは呼ばない。`audit_geometry.py` は各代表を元DSLへ100桁で
代入し、正規化した等式残差≤1e-20、元のhard条件、答えの相対誤差≤1e-20を点検する。
この検査は保存値の整合性確認であり、再探索でも独立な厳密証明でもない。

実行した1542代表は数値検査値が全て保存され、最大残差1.04e-94未満、最大答え誤差1.76e-101未満、
hard条件の不適合0件だった。ただし既存スクリプトはこの判定の後、描画用の座標を
high_precision_mode内でfloatへ変換し、全件でHighPrecisionContaminationErrorを起こす。
例外処理がpassをFalseに上書きするため、元の `geometry-audit.json` のpass=0は保持した。
`summarize_geometry_checks.py` は既に保存された検査値だけを同じ1e-20で再集計し、
`geometry-checks.json` に数値検査1542/1542と書き出しエラー1542件を分けて記録した。
閾値付近の値はなく、丸めによる判定の曖昧さもない。元スクリプト・厳密答の採点器は変更せず、
代入検査やsolverの再実行もしていない。描画用の `diagram-coordinates.json` は空である。
元の高精度座標は生ログおよびanalysis-cache/followup-cacheに残っている。

**時間の意味。** wall時間は起動・後処理を含む実測、CPU時間はEngineRunnerの子プロセス群の
使用時間。制限時間まで動いた試行には打切りがある。両条件とも正答した対の比の中央値は
成功した対だけの記述統計で、失敗した対を含む速度改善の証明にはならない。
凍結runtimeは残り時間から段階の予算を設定するので、45→180秒は同じ探索軌道を
単純に長く観測したものでもない。回復を時間不足だけの因果効果と断定しない。
共有32論理CPU機で他実験が並行しており、負荷は高い。wall制限のため成否にも負荷の影響を
除けず、2 seed一致だけで一般的な時間差や難しさの法則を主張しない。

**再開と保存。** 再開時にホストの `ps -eo pid,etimes,cmd` で元のドライバと子を確認。
409/436件からそのまま完走を待ち、436件を採用した。停止・再起動・追加再試行は行っていない。
その後は凍結commitを `/tmp/q43b-clean-60db4b6-d461234c/` に展開し、同じ入力・採点器・
`run.py`・`analyze.py`・`followup.py` のbytesで、元計画にある180秒点検を実施する。
対象の固定は `followup-design.json`、元の固定規則は `protocol.md` に記録した。
生ログと高精度座標は `/tmp/q43b-20261024-d461234c/` に置く。

**再現用の解析コマンド。** 上記クリーン展開のルートで、既存の生ログに対して実行する。
これらの解析コマンドはsolverを再実行しない。

```bash
/home/kabatan/work/solver/.venv/bin/python -B jssa/difficulty/sweep/b-equivalent-forms/analyze.py
/home/kabatan/work/solver/.venv/bin/python -B jssa/difficulty/sweep/b-equivalent-forms/followup.py analyze
/home/kabatan/work/solver/.venv/bin/python -B jssa/difficulty/sweep/b-equivalent-forms/audit_geometry.py
/home/kabatan/work/solver/.venv/bin/python -B jssa/difficulty/sweep/b-equivalent-forms/summarize_geometry_checks.py
/home/kabatan/work/solver/.venv/bin/python -B jssa/difficulty/sweep/b-equivalent-forms/report_metrics.py
```

実行器の再投入は不要。全試行を含むhash検査は `verify_completion.py --origin <共有worktree>`。
予言の判定表は該当なし（仮説なし探索）。未使用問題で確認する場合の設計だけを
`confirmation-design.md` に残し、その新規試行は今回実行しない。
