# 厳密解法との比較（PCでの本計測、2026-10-22）

- コード: branch `claude/project-thread-fos2rk` commit b0575a0 の `benchmarks/exact_comparison/`（src/ は 60db4b6 と同一）。環境は `env.txt`。
- 版: msolve 0.9.4（Ubuntu 26.04のapt）、Singular 4.4.1-p5（同）。指示にあった 0.6.5 / 4.3系 より新しい。
- 条件: msolve は全323問、1問1800秒、4並列。Singularの消去は有限でない68問に、600秒、4並列。代入による検算は105問に、300秒、2並列。各プロセスのアドレス空間を5 GiBに制限した（`ulimit -v`。Pythonも含む）。
- 比較相手のGeoSolverは本計測（6並列、jssa/results/main-j6-20261022）。並列数が違う（GeoSolverは6並列、msolveは4並列）。また、msolveの計測中には、難しさの実験（4並列）が同時に動いていた。
- 経緯: 最初の起動（10:17）で、変換処理のPythonが21 GBまで膨らんでWSL全体がOOMで落ちた。5 GiBの上限を付けて10:26に再開した（それまでに終わった結果は使っている）。その後もWindows側でWSLのクライアントが止められたため、systemdのサービスとして実行した。
- msolveの出力がない2問:
  - HMMT-2016-FEB-GEO-10: 変換処理の例外（TypeError: 'Zero' object is not subscriptable）。
  - aime-2005-1-14: 5 GiBの上限で MemoryError。
  - 集計では not_run として扱っている。
- 結果（`aggregate/summary.md`、`cases.csv`、`summary.json`）: msolveが答えの集合まで一致したのは201/323。有限でない68、時間切れまたはメモリ超過24、未対応15。msolveで一致した201問の中央値は0.028秒（GeoSolverは同じ201問で2.0秒）。
- 生データ: `msolve_1800/`、`elim_600/`、`lift/` の json。ログは `*-logs.tar.gz`。
