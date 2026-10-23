# Q20e 成果物

最終判定：**Aの核としては不可。** 候補2件を評価し、候補1の事前固定した小検証を完了した。詳細は[answer.md](answer.md)。

## 読む順序

1. [answer.md](answer.md)：結論、2候補の(a)〜(h)、理論整理、測定と限界。
2. [summary.json](summary.json)：主要数値、使用環境、入力・公式コードのハッシュ。
3. [sources.md](sources.md)：文献、確認範囲、追加で必要な具体的データ。
4. [analysis-plan.md](analysis-plan.md)、[deviations.md](deviations.md)、[resume-plan.md](resume-plan.md)：元の固定計画、実行前変更、再開時の扱い。これらは上書きしていない。

## データ

| ファイル | 内容 |
|---|---|
| [ddar-runs.csv](ddar-runs.csv) | 6実行の状態・時間・ログハッシュ・数値図の鋭角性 |
| [ddar-queries.csv](ddar-queries.csv) | 6×15結論の事前予測と導出判定 |
| ddar-20081/20082/20083-original/renamed.json | 生ログ。既存5件を保持し、20081-originalの1件だけ追補 |
| [same-premise-groups.json](same-premise-groups.json) | IMO-AG-30全件から文字列が同一の仮定を列挙 |
| [published-imo-ag30.csv](published-imo-ag30.csv) | Wu再評価論文Figure 1の目視転記。新規実行結果ではない |
| [exact-common-circle.json](exact-common-circle.json) | 人手で導いた一般式の厳密展開 |
| [analytic-coordinate-checks.csv](analytic-coordinate-checks.csv) | 固定6配置×15結論の解析的作図による数値検算 |
| [gmb-2008p1-existing.csv](gmb-2008p1-existing.csv) | 既存GMBの該当6行。再実行なし |
| [coverage.json](coverage.json) | 公開問題・GMB入力・人間データの対応範囲 |

DD+ARの図の鋭角性は保存座標への事後監査である。元のseed・結果は変更していない。解析的作図の六つの鋭角三角形とは別のデータである。

## 再集計

作業木のルートから次を実行する。指定Pythonを使い、結果はこのフォルダにだけ書く。新たな最適化や証明探索は行わない。

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1 /home/kabatan/work/solver/.venv/bin/python -B jssa/strategy/astra-consult-18/q20e-machines/analyze.py
```

Python 3.12.11、SymPy 1.14.0、mpmath 1.3.0で実行した。計算対象は軽い記号展開と保存済み資料の再集計。計測時間の欄は再実行で変わる。

[run_ddar.py](run_ddar.py)は今回の推論実行を保存したラッパーで、seedと再命名フラグを受け付ける。**同じファイル名の生ログを上書きするため、再集計手順には含めていない。** 推論を再生する場合は、本フォルダ内にラッパーとupstream/の別の実験コピーを作り、既存ログを保持する。今回の再開では既存5件を再実行していない。

依存パッケージの追加、src/の変更、大規模計算、git fetch・commit・pushは行っていない。
