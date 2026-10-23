**Q21d：条件数と感度の小検証**

結論と候補ごとの(a)〜(h)は[answer.md](answer.md)。判定は「Aの核になりうるか：不可」。主仮説の固定基準q≤0.01は正則・微分安定な218問中0問だった。これは今回の尺度・選抜・基準での結果であり、全323問の自然入力の条件数を測り終えたという意味ではない。

**入力と範囲**

- benchmarks/cases.jsonl：開発用323問のDSL。
- jssa/difficulty/minima/raw-323/：最初の保存hitの座標。各JSONのSHA-256を測定結果に記録。
- jssa/difficulty/minima/basins-323.csv：局所探索のp。完成solverの正答率ではない。
- jssa/results/stage-profile-20261023/per-case.csv：3seedの候補数と精密化時間。今回新たに完成solverを全問実行したものではない。
- jssa/difficulty/ghost-1023/human_feat.csv：human列。主解析との共通部分はAIME 31問、HMMT 46問。

背景として指定の方針転換・Q20/Q21・追加判定基準・セッション要約、相談16/17、本文v10・補足v10、astra-consult-17のG〜LおよびQ6〜Q10/Q12を参照した。Q3・Q4・Q11は実際の出力先であるwall-diagnostic/answer.md、multiplicity/answer.md、certify-all/answer.mdを参照。指定のQ5/answer.mdは見つからず、その結果を推測して補っていない。未使用問題の封印結果は参照していない。

**成果物**

| ファイル | 内容 |
|---|---|
| [answer.md](answer.md) | 結論・根拠・3候補の(a)〜(h)・今後の設計 |
| [literature.md](literature.md) | 一次資料のリンク、書誌の確認範囲、未確認箇所 |
| [protocol.md](protocol.md) | 主測定の実行前計画。測定後は変更していない |
| [measure.py](measure.py) | 保存正答配置での残差Jacobian・求値勾配・条件数の計算 |
| [measurement-lock.json](measurement-lock.json) | 計画・実行コード・参照データ・srcを含む252ファイルの実行前ハッシュ |
| [measurements.json](measurements.json) | 323問の全結果、除外分類、微分行列、3刻みの比較 |
| [measurement-completion.json](measurement-completion.json) | 計算時間27.85秒、不変確認 |
| [analyze.py](analyze.py) | p・時間・人間難度との結合。新しい探索はしない |
| [summary.json](summary.json)・[per-problem.csv](per-problem.csv) | 集計と問題別の表。分離の必要数22、実数0 |
| [selected-controls.json](selected-controls.json) | 強分離群が空だったため、対照群からID順で選んだ3問 |
| [perturbation-plan.md](perturbation-plan.md) | 3問の数字の対応付け・局所補正の実行前計画 |
| [perturb.py](perturb.py)・[perturbation-lock.json](perturbation-lock.json) | 固定した入力摂動・方向微分・整数三角形の検算と実行前ハッシュ |
| [perturbation-runs.json](perturbation-runs.json) | 24回の局所補正の座標・値・元式残差・guard/hard検査 |
| [input-sensitivities.json](input-sensitivities.json) | 6方向の直接項・座標経由項・一次整合性・中心差分との照合 |
| [directional-checks.json](directional-checks.json) | 最弱方向と目標勾配方向の直接評価、計18件 |
| [integer-triangles.json](integer-triangles.json) | 整数の辺・面積でも高さの感度が発散する初等的反例 |
| [perturbation-summary.json](perturbation-summary.json) | 24/24補正合格、12/12微分検算合格、計算時間0.66秒 |
| [verify.py](verify.py)・[verification.json](verification.json) | 別公式で218組の感度を再計算、3問の閉形式・6方向を照合、元データ不変確認 |

**再現**

今回の環境はPython 3.12.11、NumPy 2.5.1、SciPy 1.18.0、mpmath 1.3.0。パッケージの追加・更新はしていない。

作業ルートで以下を順番に実行する。インストールは不要。各スクリプトが書くのはこのフォルダだけで、bytecodeの書き込みを無効にしている。全再現は、このフォルダの生成データと実行前ハッシュ記録を上書きするので、今回の実行記録を保つ場合は先に別名で保存する。

    env PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1 /home/kabatan/work/solver/.venv/bin/python -B jssa/strategy/astra-consult-18/q21d-conditioning/measure.py
    env PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1 /home/kabatan/work/solver/.venv/bin/python -B jssa/strategy/astra-consult-18/q21d-conditioning/analyze.py
    env PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1 /home/kabatan/work/solver/.venv/bin/python -B jssa/strategy/astra-consult-18/q21d-conditioning/perturb.py
    env PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1 /home/kabatan/work/solver/.venv/bin/python -B jssa/strategy/astra-consult-18/q21d-conditioning/verify.py

既存結果の検算だけなら最後のverify.pyのみを実行すればよい。verify.pyはこの固定データに対する検算で、将来の別データで同じ問数・結果を強制するための汎用テストではない。

新規計算は逐次、1worker、数値ライブラリ各1thread。主測定は1問25秒・全体60分の上限、入力摂動は1実行5秒・最大100評価の上限を設定した。新しい乱数出発点は使っていない。主仮説が不成立だったため、候補1の後段の精密化軌道計測や候補2・3の本検証は実行していない。これらはanswer.mdに設計だけを残した。
