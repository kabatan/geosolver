# 測定の表示変換の修復

実行中、worker.py の `error_digits=float(digits)` が high_precision_mode 内で float(mpf) 禁止に当たり、候補の目標値誤差の行への記録が失敗していることを発見した。探索と精密化の座標は独立に保存済みである。

元の worker.py と事前ハッシュは変更しない。repair_measurement.py は measure 工程だけを、保存された精密化座標から実行する。差分は `error_digits=float(digits)` → `error_digits=float(str(digits))` の1箇所であり、浮動小数表示への変換経路だけを変える。高精度での誤差・残差の計算、最良候補の定義、P1〜P3の閾値、参照値、判定ルールは一切変えない。

探索・精密化・検証は再実行しない。修復は本計測の2ストリームが終了した後に1並列で行う。元の失敗した測定と自動生成された暫定集計は/tmpに保存する。追加スクリプトのhashと時刻を修復測定前に measurement-repair-hashes.json に記録し、修復後に同じ analyze.py で最終集計する。
