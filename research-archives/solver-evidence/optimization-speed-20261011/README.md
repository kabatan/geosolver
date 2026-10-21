# 追加高速化の記録

追試の結論は**追加変更の採用なし**です。`final-report.json`には目標未達、退行、対比較、採否理由を残しています。

| 調べる内容 | 資料 |
|---|---|
| 実験契約と凍結順序 | `protocol.json` |
| Newton法の退行と修正 | `refinement-receipt.json`、`evaluation-trust-review-receipt.json`、`evaluation-fallback-v4-review-receipt.json` |
| 同一コア・従来版→試作版→試作版→従来版の比較 | `refinement-fallback-v4-abba/{manifest,summary}.json`、`records.jsonl` |
| 角度・三角関数の解析微分 | `algebra-analytic-stable-v3-paired/{manifest,comparison,receipt}.json`、`records.jsonl` |
| 多倍長演算・cache・代数的な候補の不採用 | `evaluation-negative-receipt.json`、`algebra-negative-receipt.json` |
| 失根の診断 | `evaluation-hmmt2013-root-loss-audit.json` |
| 未使用入力と数学的な正解 | `fresh-holdout/{cases.jsonl,derivations.json,manifest.json}` |
| 当時の基準版・最終試作版 | `source-snapshots.tar.gz`とそのファイル索引`source-snapshots.json` |

元の計測・比較用スクリプト、patch、独立レビューの記録も保存しています。アーカイブ内のソースを現行実装へ適用したものではありません。
snapshotには`baseline-source`、`refinement-fallback-v4-source`、`analytic-stable-v3-source`の`src/`と依存lock・設定を収録しています。

最終報告の`evidence`が参照する14ファイルは、このディレクトリで取得でき、取り込み前に当時のhashとの一致を確認しました。
`records.jsonl`は対比較の記録です。巨大なworker捕捉データを含む全実行の復元には、親索引に示したローカル保存先が必要です。

生成コードは当時のままで、スクリプトの隣の`fresh-holdout/`を出力先とし、既存なら上書きを拒否します。
再生成を調べる場合は、生成コードを別の空ディレクトリにコピーして実行してください。生成と静的検証は求解評価とは別です。
