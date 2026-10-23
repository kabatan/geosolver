# Q20c：引き継ぎ結果と再現

[answer.md](answer.md) が最終回答。現在の判定は **Aの核になりうるか：不可**。2候補を(a)〜(h)で評価し、前回の固定計画による小検証を完結させた。

## 引き継いだもの

登録記録の実験開始は **2026-10-23 12:57:58 UTC（21:57:58 JST）**。計算終了は同じ秒。20設定・180記録、計算時間0.289秒。結果は中断前に完成しており、再開後は実験を再実行していない。

- [preregistration.md](preregistration.md)：T1〜T3、固定パラメータ、比較条件。
- [registration-lock.json](registration-lock.json)：開始時の本文・コードのSHA-256、Python/NumPy/mpmathの版。
- [experiment.py](experiment.py)：1プロセス・最大130×130の線形代数。GeoSolverの局所探索は呼ばない。
- [experiment-rows.csv](experiment-rows.csv)、[matrix-conditions.csv](matrix-conditions.csv)、[experiment-summary.json](experiment-summary.json)：全結果。
- [reanalyze.py](reanalyze.py)、[source-hashes.json](source-hashes.json)：既存データ再解析のコードと108参照ファイルのハッシュ。
- [corpus-context.csv](corpus-context.csv)、[expansion-audit.csv](expansion-audit.csv)、[existing-paired-effects.csv](existing-paired-effects.csv)、[existing-summary.json](existing-summary.json)：自然問題の記述集計。

これら12ファイルは保持した。再開時に更新した既存ファイルはanswer.mdだけ。追加したのは本README、[theory.md](theory.md)、[literature.md](literature.md)、[verify_resume.py](verify_resume.py)、[verification-resume.json](verification-resume.json)。

## 再計算せず検算する

リポジトリ直下から次を実行する。登録・実験結果・入力は読み取りだけで、出力はこのディレクトリのverification-resume.jsonのみ。

```bash
env PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 /home/kabatan/work/solver/.venv/bin/python -B jssa/strategy/astra-consult-18/q20c-representation/verify_resume.py
```

検査内容は、登録ハッシュ、全108参照ファイルのハッシュとサイズ、180記録の網羅性、T1〜T3の固定判定、解析式と保存条件数の一致、57問の対応比較と元の集計・43問のhit記録の一致である。指定Python以外や第三者ライブラリは要らない。srcからのimportもなく、局所探索は0回。

この検算は、保存座標の誤差を最初から求め直す計算ではない。証拠の保存状態と集計の整合を確かめるもの。実験の再実行を別途行う場合は、元のexperiment.pyが登録記録とCSVを上書きするため、同じフォルダで再実行せず、新しい比較用ディレクトリへコードと固定計画をコピーして行う。本担当ではその再実行をしていない。

## 集計上の注意

T1〜T3は全て成立。一方でT3は補助変数固有の必要性を否定する対照である。三つ通ったことを、研究のA判定の合格へ読み替えない。

自然問題57問は既知の開発群。14問と43問ではk、対象、試行数が違う。二群の中央値の差をkの因果効果とは解釈しない。human_featは補助線介入の人間成績ではない。

43問の0.2低下の件数にはfloat境界の相違がある。AIME-2008-II-05のE=39/40、Y=31/40は厳密な差が1/5だが、旧score.pyのfloat式では閾値外になっている。今回は整数比の記述集計と旧判定を区別し、旧P2を変更していない。

## 指定資料の所在

Q20・追加基準、セッション要約、相談16/17、本文・補足v10、astra-consult-17/G〜LとQ6〜Q10、basins-323.csv、human_feat.csv、extra-variablesの入力・プロトコルを参照した。

Q3/Q4の指定形式のanswer.mdは存在せず、待ち行列の出力先にあるwall-diagnostic/answer.md、multiplicity/answer.mdを参照した。Q5は指定先とfull-solver-nohard/のどちらも存在せず、待ち行列の指示のみ確認した。結果を取得したふりはせず、fetchも行っていない。

保存済みの実験は1プロセス・数値ライブラリ各1スレッド。再開後の読取作業は最大2呼出し並列、検算は1プロセス。インストール、src変更、作業フォルダ外への書き込み、commit・pushはしていない。大規模計算と将来案の探索は未実行。
