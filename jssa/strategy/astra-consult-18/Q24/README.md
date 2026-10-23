# Q24 成果物と検証方法

[結論・理論・開発群の検査](answer.md)、[未使用26問の事前登録文案](preregistration.md)、[全予告CSV](unseen26-predictions.csv)が主な成果物。Aの核の判定は不可。未使用群の当否は未検証。

## 固定順序

1. 開発群323問の既存記録を再集計し、R0/R1/R2の3候補を検査した。新規の局所探索や数値的な配置生成は行っていない。
2. `preregistration-core.md`、規則コード、開発結果等を `rule-lock.json` で固定（2026-10-23 14:33:22 UTC）。この時点ではQ18 auditと未使用DSLをまだ読んでいない。
3. Q18 auditからid/verdict/dsl_file/dsl_sha256だけを保持し、合格26問のDSL JSONに固定コードを適用した。入力DSLは5フィールドだけで、答えや実行結果を含むJSONLは読んでいない。各DSLのSHA-256はQ18記録と一致。
4. 登録本文を変えず、入力由来の全26問表を付録として加え、`prediction-lock.json` で固定（14:35:28 UTC）。
5. 理論・開発成績・予言の限界を `answer.md` へまとめ、固定ハッシュと表の整合性を検査した。

時刻はローカルの記録であって、公的な時刻認証ではない。commit・pushは行っていない。

## ファイル

|ファイル|内容|
|---|---|
|answer.md|結論、理論の導出、何が予言できなかったか、自己点検|
|preregistration-core.md|未使用入力を見る前に固定した規則・閾値・判定基準|
|preregistration.md|固定本文＋全26問の入力だけによる予言表|
|rule-lock.json / prediction-lock.json|規則固定時・予言完成時のSHA-256|
|static_features.py|標準ライブラリによる入力AST特徴と3規則|
|predict_unseen.py|入力ファイルの限定・Q18ハッシュ照合・固定規則の適用。既存の出力を上書きしない|
|reanalyze.py / audit_development.py|既存開発データの再集計、出典確認、比較、全外れ表の作成|
|development.csv|323問の特徴・既存p・費用・観測分類|
|development-predictions-all.csv|全323問×3候補。保留・判定不能を含む|
|development-errors-all.csv|3候補の全判定可能誤予測|
|development-errors-R1.md|R1の全115誤予測行と、費用判定不能の全件|
|development-directional.csv|R1/R2の方向予告の全件|
|development-summary.json / development-audit.json|再集計、混同行列、共通対象での基準比較、見逃し、完成solverへの移行仮説|
|development-input-manifest.json|読み取った開発データのバイト数・SHA-256|
|q21f-reanalysis.csv|Q21fの既存6問の経路数・根数・成功数とAST特徴|
|multiple-targets.csv|多答8問の値別hitの再集計|
|source-msolve-cases.csv / source-msolve-README.md|出典commitから読み取り専用で再取得した小さい原資料|
|source-audit.json|元のblob SHAと全CSVフィールドの照合、121/122の再集計|
|unseen26-predictions.csv|全26問の構文特徴、定性的分類、弱い完成solver副予言|
|unseen26-input-manifest.json / unseen26-summary.json|26入力のハッシュ、選定欄、計算内容と予言数|
|literature.md|検索して確認した一次資料と未確認部分|
|analysis-plan.md|開発群の再解析前に書いた探索手順|
|verify_delivery.py / verification.json|固定後の読み取り検証と、その保存結果|
|SHA256SUMS|成果物の最終ハッシュ（このファイル自身は除く）|

## 検証

リポジトリのルートで次を実行する。新しい探索は行わず、既存のハッシュ・CSV・入力ASTだけを検査する。

```sh
env PYTHONPATH=src /home/kabatan/work/solver/.venv/bin/python -B jssa/strategy/astra-consult-18/Q24/verify_delivery.py
```

最初に実行した再解析コマンドは以下。これらのうち最初の2本は固定対象を再生成するため、納品後の通常検査には上の読み取り検証を使う。`reanalyze.py` の経過時間は再実行ごとに変わる。全入力ハッシュと抽出・分類コードを保存しているので、測定値と集計内容は追跡可能である。

```sh
env PYTHONPATH=src /home/kabatan/work/solver/.venv/bin/python -B jssa/strategy/astra-consult-18/Q24/reanalyze.py
env PYTHONPATH=src /home/kabatan/work/solver/.venv/bin/python -B jssa/strategy/astra-consult-18/Q24/audit_development.py
env PYTHONPATH=src /home/kabatan/work/solver/.venv/bin/python -B jssa/strategy/astra-consult-18/Q24/predict_unseen.py
```

## 読み取り・実装上の注意と失敗記録

- 最初の再集計は探索不要行の空のn_startsを整数化してValueErrorになった。d=0かつ保存開始0件であることをassertして0として扱う修正後、全323問を再集計した。数値探索の失敗ではない。最終規則の固定前の修正である。
- Hのコピーの生バイトSHAは元provenanceと異なった。CSVとsummaryは末尾改行、READMEはBOMと末尾改行が原因。元CSVと元READMEを再取得し、原blob SHAを確認した。`development-summary.json` の元コピーに対する不一致フラグは消していない。解決内容は `source-audit.json` にある。
- `benchmarks/` の現チェックアウトには元msolve比較結果がなかったため、Hのprovenanceから読み取り専用GitHub接続で出典を確認した。git fetchやcheckoutはしていない。
- 背景指定の `full-solver-nohard` に対応するQ5成果物は見つからず、結果を補作していない。`minima/basins-323.py` と `scripts/` の読み取り試行もパス不存在だった。測定器の実ファイルは `jssa/difficulty/probe_basins.py` と確認して読んだが、実行していない。
- `certify-all/per-case.csv` はdevelopment323とholdout2026の混在ファイルで、再解析はdevelopment323だけを採用した。未使用26問・Q19の記録ではない。進行中のwall実験は背景の読み取りにとどめ、今回の規則検査に追加実行や途中結果の継ぎ足しをしていない。
- Menckほか2013の出版社本文は取得できず、機関PDFも非公開だった。書誌・概要と後続著者論文の本文を区別し、未確認を文献表に残した。
- AST特徴には数値ランク、代数的次数、根数、開始箱の測定、許容領域の体積推定を含めていない。非線形・危険演算の集合は不完全な代理であり、0個でも安全とは限らない。変数名変更での整合性は全323問で確認したが、等価な式変形への不変性は主張しない。
- 会話中の「厳密重・局所高の3問とも外れ」は不正確だったため、比較可能2問が外れ・1問は未対応で評価不能、と訂正した。最終表と判定は訂正後の分類による。

出力は全てQ24内。src・既存データ・Python環境には書き込まず、pip install、commit、push、fetchを行わなかった。Q19の封印・中身・結果は参照せず、未使用26問にはsolver・局所探索・配置生成・p推定を実行していない。
