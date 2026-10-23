# Q12 成果物と再現

**判定：Aの中心は縮小。** 理由・統合表・理論は [answer.md](answer.md)。独立の局所探索は行っていない。

- [stop-criteria.md](stop-criteria.md)：詳細な結果を読む前に固定した中止基準。初回answerの暫定判定は縮小だった。
- [role-policy.md](role-policy.md)：入力だけを使う役割規則、適用証拠、保留、完成solverで実際に変える範囲。
- [preregistration.md](preregistration.md)：Q2の未実行計画。仮説・数値基準は固定したが、実装・最終入力manifestの登録は未完了。
- [literature.md](literature.md)：一次文献の確認範囲と未確認事項。
- [source-manifest.json](source-manifest.json)、[snapshots/](snapshots/)：2026-10-23 21:25:32 JST取得の既存資料23ファイルとSHA256。合計512,932 bytes。原文を保存しているため、snapshot文書内の元の相対リンクは取得元の場所を基準とする。
- [reaggregate.py](reaggregate.py)、[reaggregate.json](reaggregate.json)：既存CSV/JSONの再集計と結果。元solver・幾何評価器は呼ばない。
- [freeze_sources.py](freeze_sources.py)：上記snapshotの取得コード。既存snapshotを上書きしないため、再実行時には停止する。
- [verify_delivery.py](verify_delivery.py)、[delivery-check.json](delivery-check.json)：保存出典のハッシュ、Q12内リンク、ファイルサイズ、主要件数の確認。
- [document-lock.json](document-lock.json)：Q12文書のハッシュ。実験の外部登録や実行用コードの凍結を意味しない。

再集計はrepoルートから次の一行で行う。指定Pythonを使い、依存関係の追加なし。書込み先はこのQ12フォルダのJSONだけ。

```bash
env PYTHONPATH=src PYTHONDONTWRITEBYTECODE=1 /home/kabatan/work/solver/.venv/bin/python -B jssa/strategy/astra-consult-17/Q12/reaggregate.py
```

納品物の確認：

```bash
env PYTHONPATH=src PYTHONDONTWRITEBYTECODE=1 /home/kabatan/work/solver/.venv/bin/python -B jssa/strategy/astra-consult-17/Q12/verify_delivery.py
```

Q1のsnapshotは進行途中であり、全292問の結論に使わない。answerの観測数4,907とCSVの5,269には更新時刻差がある。掲載した問題平均・対応数は、CSV上の完了35問・4,282開始に限定し、summaryとの一致を確認した。

Q2はREADMEとauthoring-rulesのみ読んだ。READMEには候補ID・変数数・構造概要が含まれたため、その露出を隠して「入力盲検」と称していない。DSL、official_answers、原文、solver出力は開いていない。Q2のv3は全採用問題を収録する規則へ更新中だったので、古い18問という件数を固定した評価集合と扱わない。

作業は初期の中止基準と暫定answer保存→既存成果の読取り→小さい出典snapshot→再集計→一次文献の確認→理論・規則・Q2計画の記述→整合性確認。既存optimizerの実行、終点の新しい摂動、一歩診断、候補生成は0回。新たなコードは出典保存・表の集計・文書確認だけである。

src、他担当のファイル、Python環境は変更していない。新しい書込みはQ12内のみ。pip install、git fetch、commit、pushは行っていない。
