# Q28c：早期棄却と保存記録の監査

結論は [answer.md](answer.md)。新しいsolver実験は行っていない。既知の次数分布を確認し、全非2冪次数問題2問の既存結果を再集計した。

実行順は、指定資料・既存不可案を読む → 暫定不可と [preregistration.md](preregistration.md) を保存 → [audit.py](audit.py) を作成 → 監査1回 → 結果・文献確認を反映、である。外部登録やgit commitは行っていない。登録ファイルのハッシュは実行時に [manifest.json](manifest.json) に保存し、登録本文は実行後も変更していない。

作業ルートから再現するコマンド：

```bash
env PYTHONPATH=src PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 /home/kabatan/work/solver/.venv/bin/python jssa/strategy/astra-consult-18/Q28c/audit.py
```

SymPy 1.14.0。式の構文確認に使い、新しい最小多項式・ガロア群は計算しない。1プロセス、数値スレッド1。実測約0.073秒（importを除く）で、プロセス全体のツール記録は約0.204秒。調査・執筆時間とは別。

| ファイル | 内容 |
|---|---|
| per-value.csv | 338答値の次数・式・平方根の塔の十分条件による分類 |
| per-problem.csv | 323問題の答値分類。図全体の分類ではない |
| non2-local.csv | 非2冪次数の全2問×2seed。元rawの全recordsを数えた4行 |
| non2-full-solver.csv | 同2問の既存完成solver全6行 |
| summary.json | 分母・欠測・全結果・数値的群計算ツールのPATH/import確認 |
| manifest.json | Python・環境・登録・コード・使用入力のSHA256、入力非改変確認 |
| sources.md | 一次文献と確認範囲 |

既存の次数表はQ21bの計算結果を使用しており、今回独立に全最小多項式を検算したわけではない。4次の `CRootOf` 2値は未分類のまま。人間難度は非2冪の2問とも欠測。相関・群間有意差・因果推定は実施していない。

**手順上の逸脱。** 初回の軽量な読み取りツール4件を同時発行した。並列上限2の指定に対する逸脱として記録する。以後の同時呼出しは2以下、数値計算は一貫して1プロセス。予言・対象・閾値の事後変更、監査の失敗・再実行はない。

書込み先はQ28cのみ。srcのimportもせず、bytecode生成を無効化した。依存追加、作業外書込み、git fetch/commit/push、封印tar・unseen-1983の参照は行っていない。
