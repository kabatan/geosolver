# sol-4 実行前の扱い（2026-10-23）

基準は `../ghost-1023/preregistration-2.md` の B を固定する。
対象は sol-1 の n_pairs_found>0 かつ has_hits=1 の58問。
`plan.json` は介入実行前に保存し、入力の SHA-256、全対象、全点対の
当たりでの安全確認、L、除外、乱数抽出を固定する。

- L は元の seed 0 の全 hit の図の直径の中央値。点名は ghost_scan.point_names、
  座標は probe_basins.construction_coordinates / answer_float を使う。
- 全ての元の hit で |PQ| > 0.02 L を確認できる found=1 の点対を使う。
  未定義座標も安全確認不可として除く。ε=0.02、w=1。
- placebo も正しい図で0の同じ罰則にするため、同じ安全確認を適用する。
  found=0 の安全な点対を辞書順に並べ、default_rng([7, 問題番号]) で
  非復元抽出する。問題番号は sol-2 と同じ basins-323.csv の全行の0始まり番号。
  事前登録は番号と復元の有無を明記していないため、ここで結果を見る前に固定する。
- 同数の異なる placebo 点対が足りない7問は placebo 欠測。重複、found=1
  からの補充、treatment の間引き、対象問題の除外はしない。
- 安全確認後の treatment が0組の5問も対象に残し、0行追加として実行する。
- 保存済みの全 start は11,038個。元の200個を再生成したり補充したりしない。
  出発点の順序、seed=0、局所探索経路、元の LM max_nfev=80、許容誤差、
  Powell 分岐と上限を維持する。src の編集はしない。
- run.py の既定は probe_basins と同じ、各問題・各armの探索全体120秒。
  締切により完了しなかった start は not_run_deadline とし、失敗に置換しない。
  その問題の固定 start 全体の p は欠測とし、確定したhit数/Nから
  (確定hit数+未完了数)/Nの範囲を示す。もしユーザーが全保存済みstartの
  実行を指示した場合のみ、run-settings.json に全体締切を外したことを明記する。
- 最適化残差関数をプロセス内で一時的にラップし、元の等式・guard・hard罰則を
  呼んだ後に点対の行を追加する。元のbundle、評価器、採点経路はそのまま。
  追加点対の座標が探索中に未定義なら、元の評価器と同じ1e10の有限罰則を
  追加行に返し、発生数を記録する。正しい図では発生しないことを別途検証する。
- 採点は元の probe_basins と同じ：箱、元の等式ノルム<=1e-8、guard、
  hard feasibility、元の答えと相対許容誤差1e-6で照合。追加行で採点しない。
- B1 = median(p_treatment - p_original) >= 0.10。
- B2 = median(p_treatment - p_original) - median(p_placebo - p_original) >= 0.08。
  「問題ごとの treatment-placebo 差の中央値」には変更しない。
- B3 は元が非hitで treatment がhitになった start 全体で、
  元の終点 coinc < 1e-4 の割合 >= 0.50。全hitで常に一致する点対は
  ghost_scan と同じ判定で除く。coinc 未定義や未完了があれば、欠測を含む範囲も示す。
- 固定58問に欠測があれば、58問の点推定や判定を完全ケースにすり替えない。
  成功率が[0,1]にあることだけから全58問の中央値等の上下限を計算する。
  上限でも基準未満なら「不成立」、下限で基準以上なら「成立」、それ以外は
  「判定不能」。完全ケースの値は補助記述に限定する。
- B2 が不成立または判定不能なら、退化解が当たり外れの原因だとは主張しない。

外部環境の変更、依存のインストール、commit/push はしない。
出力はこのフォルダ内のみ、実験workerは最大4、BLASスレッドは1。
