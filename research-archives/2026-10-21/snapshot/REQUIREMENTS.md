# GeoSolver研究coreの契約

- Python 3.12。実行入口はPython APIとvalidate / solve / doctor / catalog CLI。
- 入力はGeometryProblem v1。HTTP/UI、Julia、別reference engine、旧run_ir APIは提供しない。
- 単一のstandard pipeline。NOMAD主探索とSciPy補助探索、mpmath精密化、有限な厳密化探索を維持する。
- 公開APIの時間指定は180〜900秒。core指定は使用上限であり、現実装は1 worker・1数値計算stream、実効coreは1。
- 研究runnerは1問題・1seed・1 subprocess、180秒・1 core。問題単位の並列実行には異なるCPUを割り当てる。
- 円の正半径、図形の非退化性、交点の存在・一意な枝、条件・boundsを最終検証する。
- 最終残差は共通の加算定数を誤差scaleに使わない。閉じた算術条件は厳密に検査する。数値検証は一般的な記号証明の代替ではない。
- 厳密値は最小多項式・実根番号・有理分離区間を持つ代数的数、または代数的係数の一次式 A*pi+B。曖昧な根を近さだけで選ばない。
- 数値探索・厳密値の推定は網羅性を証明しない。無変数問題も含めcompleteness=unknown。
- 全phaseとdescriptor生成はworkerの同一deadline内。最後の2秒を結果書出し用に予約し、外側process上限を安全装置にする。
- 候補、最終検証、厳密化、枝、棄却理由、phase時間、評価回数、実行設定・導入依存関係をartifactに記録する。
- raw artifactは参照値を含まない。正誤比較は別工程で数学的なcanonical keyの集合を比較する。
- campaign出力先は空ディレクトリ限定。参照値と問題のhashを固定し、既存runとの混在・重複seedを拒否する。

## 検証条件

Linuxを正式な評価環境とし、Windows・macOSはclean wheelとworkerのCIで検証する。ローカルLinuxでの合格をWindows実測済みとは扱わない。

反例試験、全テスト、Ruff、compileall、schema整合、import順、clean wheel、corpus整合が必須。正式な性能評価には同一host・CPU割当・依存環境での比較が必要。
