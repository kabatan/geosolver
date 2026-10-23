Q28d：文献と確認範囲（2026-10-23、公開資料を検索して確認）

| 文献 | 確認した箇所 | 今回使う範囲 |
|---|---|---|
| Ana Cannas da Silva, *Symplectic Toric Manifolds*, July 2001, 講義ノート。[著者公開PDF](https://people.math.ethz.ch/~acannas/Papers/toric.pdf) | 表紙の著者・日付、§3.2、印刷頁34–36、Theorems 3.2.1–3.2.2。PDFのテキストで確認 | 非退化臨界点の指数、コンパクトな臨界値区間でのセル付加、コンパクト多様体の指数別モース不等式。研究論文ではなく専門家本人の講義資料 |
| Elon Rimon and Daniel E. Koditschek, *Exact Robot Navigation Using Artificial Potential Functions*, IEEE Transactions on Robotics and Automation 8(5), 501–518 (1992).[原論文PDF](https://www.cs.cmu.edu/~motionplanning/papers/sbp_papers/r/rimon_koditschek_potential.pdf) | 原論文p.501の書誌・要旨、p.506のDefinition 1と直前・直後の議論をPDFを指す検索結果の本文抽出で確認。PDFをopenすると18頁だがテキスト行数0と返るため、この取得方法を明記 | 唯一の極小を持つnavigation functionと、位相が要求する追加の不安定平衡点の区別。全構成定理・証明は今回精読していない。solverの残差がその条件を満たすとは主張しない |
| Herbert Edelsbrunner, David Letscher and Afra Zomorodian, *Topological Persistence and Simplification*, Discrete & Computational Geometry 28, 511–533 (2002), DOI 10.1007/s00454-002-2885-2。[原論文PDF](https://www.math.uchicago.edu/~shmuel/AAT-readings/Data%20Analysis%20/Edelsbrunner-Letscher-Zomordian.pdf) | 冒頭の書誌、要旨、Introduction、BackgroundをPDFのテキストで確認 | filtrationに沿う位相的特徴の寿命を測る既存の枠組み。原論文の主対象は有限単体複体等であり、本solverの不連続目的関数への適用保証としては引用しない |

部分レベル集合の零点を含まない成分からの下界、トーラスの明示残差、四次多項式の反例はanswer.md内で直接導出した。これらを上記論文の新定理として帰属させない。0次の成分の誕生と指数0の臨界点の関係はモースのセル付加による説明であり、点群での計算誤差保証は別問題である。

未確認：323問の各許容領域・各残差部分レベル集合の厳密なBetti数、モース／モース・ボット性、非コンパクト端での条件、終点の局所最適性、別seedでの極小数の再現、これらを独立な入力特徴から予測する既存研究の有無。未確認を不存在・新規性と解釈しない。

読み込んだ内部資料：指定のcodex-tasks-1023.md末尾の方針・Q28、codex-session-01a1171a-summary.md、report-draft-v10.md、supplement-v10.md、q20b-dynamics/answer.md、q21e-phase-transition/answer.md、false-attractors/answer.mdの結論・定義・限界・文献の節、minima/summary.md、probe_basins.py、scipy_multistart_backend.pyの関連箇所。false-attractorsの全生データを再解析したわけではない。wall-292・multiplicityの追加データ解析は、入口で不可としたため実施していない。

再実行：既にfreeze.jsonがあるので`--freeze`は付けず、作業ルートから次を実行する。

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src /home/kabatan/work/solver/.venv/bin/python -B jssa/strategy/astra-consult-18/Q28d/audit.py
```

書込みはQ28d内のみ。標準ライブラリのみで、新たなsolver実行・パッケージ導入は行わない。
