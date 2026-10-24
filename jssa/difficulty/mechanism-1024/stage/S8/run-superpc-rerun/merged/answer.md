# 事前登録15 S8：superPC分の中間集計

superPC固定53問のみ。WinPC分と合算前。106問の最終判定ではない。

seed 601〜603、180秒、1コア・内部1スレッド・CPU固定、最大8並列。N/C1/C2/C3/C4/C5/BASEのみ。解けた=3seed中2回以上で独立参照集合と完全一致。失敗/timeoutはC=180、正解は所有木回収までの実時間、中断はok/C=nullで結果に数えない。再試行・別seed・問題追加除外なし。

**時間・費用Cはすべて参考値（†）**。他プロジェクトの負荷が重なり、全体平均の構成差から速度効果を判定しない。時間の比較は事前固定した同条件の同時実行ペアだけ。正解数はそのまま有効。

| 構成 | 問題数 | 解けた数 | 未完 | C平均† 秒 | Nからの累積増分 | high_load_overlap 真/偽/不明（枠数） |
|---|---:|---:|---:|---:|---:|---|
| N | 53 | 51 | 0 | 41.381787 | +0 | 0/68/91 |
| C1 | 53 | 41 | 0 | 47.583207 | -10 | 0/128/31 |
| C2 | 53 | 49 | 0 | 34.181644 | -2 | 0/115/44 |
| C3 | 53 | 51 | 0 | 25.421494 | +0 | 0/120/39 |
| C4 | 53 | 52 | 0 | 21.545171 | +1 | 0/127/32 |
| C5 | 53 | 52 | 0 | 21.314974 | +1 | 0/130/29 |
| BASE | 53 | 52 | 0 | 21.462891 | +1 | 0/128/31 |

C平均はseed費用の問題内平均を53問で平均。環境中断があれば全体平均は未確定。high_load_overlapは外部1分ログのhigh_loadを時刻照合し、欠測は偽にしない。各枠のdriver load/start/end/CPUと外部負荷の重なりはper-run.csvに保存。

| 累積段階 | 解けた数の純増 | 新規成功 | 失った成功 |
|---|---:|---:|---:|
| N → C1 | -10 | 0 | 10 |
| C1 → C2 | 8 | 8 | 0 |
| C2 → C3 | 2 | 2 | 0 |
| C3 → C4 | 1 | 1 | 0 |
| C4 → C5 | 0 | 0 | 0 |
| C5 → BASE | 0 | 0 | 0 |

B1（中間値）: N=51/53 (96.23%)、BASE=52/53 (98.11%)。N≤60%かつBASE≥90%の部分集合条件: False。

B4（参考の事前登録式）: 全体C平均のN/BASE=1.928062†（予測3以上）。この算術値は負荷を揃えた時間比較ではなく、支持判定には使わない。

B5（参考の事前登録式）: 全体C平均のC4/C3=0.847518†、算術上の減少率=0.152482†（予測10%以上）。支持判定には使わない。単独G4=N+4は未実行のためB5全体は保留。

外れた方向・負の増分もそのまま保存。B2は上表の全増分を掲載。B3および単独群は今回の対象外。

| 同条件の同時実行† | 適格seedペア数 | C前/後† | 両方正解ペア数 | 正解実時間 前/後の中央値† |
|---|---:|---:|---:|---:|
| N → BASE | 24 | 2.562432 | 24 | 2.217844 |
| N → C1 | 26 | 0.657097 | 24 | 1.809561 |
| C1 → C2 | 70 | 1.735903 | 64 | 1.000002 |
| C2 → C3 | 60 | 2.189386 | 57 | 0.972183 |
| C3 → C4 | 80 | 1.001106 | 80 | 0.992180 |
| C4 → C5 | 77 | 1.017124 | 77 | 0.992335 |
| C5 → BASE | 80 | 0.989146 | 80 | 0.993658 |

時間ペアの固定条件: 同一問題・同seed、同一契約、実行区間の重なり1秒以上、driver開始1分load差≤5、外部high_load_overlapが両方既知で同じ、区間加重平均cpu_pct_other差≤200（2コア相当）。適格ペアのC平均比と、両方完全一致した実時間比の中央値を掲載。ペアが0なら比較不能。適格な並行ペアも専有環境の再測定ではない。

判定規則は計測開始前のanalysis-freeze.jsonでhash固定（sha256 63fd349282b2ec7e2578d7cdff63ed1fa05b2637ad47384d6f6871f054120f8d）。外部ログのスナップショット: load-log-snapshot.jsonl（sha256 084290eed794bfeef75c6cbb12da07f0662593d586cfca6feaedaf7ba3c33022）。原本: /home/kabatan/work/tmp-evac/loadlog/load-log.jsonl。

状態: {'completed': 1113}。採点理由: {'exact_whole_set_match': 1038, 'answer_set_mismatch': 12, 'solver_no_answer_found': 63}。旧試行は ../run-superpc-aborted-attempt1/ に保存、全件結果に含めない。

固定参照: 19a5b9948f846ebaa818e84263647d6a6fdb909c4ccea0b56b2be6035f9a9d98; source/入力/参照hashはmeasurement-freeze.json。raw: see individual receipts: original + rerun。全個別ファイルhashはreceipts、成果物hashはartifact-hashes.json。commit/pushなし。

320 original nonzero_exit slots are infrastructure interruptions; only their authorized rerun receipts replace them. Original campaign is preserved. See replacement-map.json.
