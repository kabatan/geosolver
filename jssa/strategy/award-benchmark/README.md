# 受賞作の水準と判定の較正（award-benchmark）

作成 2026-10-24。GPT-Pro の判定を「GPT-Pro の好み」ではなく人間の審査員の基準に合わせるための物差し。

| ファイル | 中身 |
|---|---|
| [01-official-criteria.md](01-official-criteria.md) | 審査の流れ・賞・審査委員・評価の観点（公式文言と出典URL）。**明文の採点基準は無い**こと、**第70回の最終審査は対面**であること |
| [02-it-awards-62-69.md](02-it-awards-62-69.md) | 情報・技術／応用数学（高校）第62〜69回の受賞作57件をランク別に。概要PDFのURLと、何が評価されたか（推測と明記） |
| [03-calibration-table.md](03-calibration-table.md) | GPT-Pro の A〜E と実際の賞の対応、各ランクの典型的な水準（事実／推測を分けて）、GPT-Pro と人間のずれ方 |
| [04-blind-anchor-test.md](04-blind-anchor-test.md) | 目隠し較正テストの手順と判定プロンプト |
| anchors-order1〜3.md | 受賞作16件＋geosolver の概要を匿名で混ぜたもの（3通りの並び順） |
| anchors-key.md | その答え（判定する GPT-Pro には渡さない） |
| geosolver-summary-v14.txt | geosolver の概要（受賞作と同じ定型、本文 v14 から作成） |
| raw/ | 主催者サイトから取得した原文テキスト・PDF（要項、規定、受賞作一覧、概要287件）。索引は raw/index.md |

共有フォルダの raw/ にはPDF本体（pdfs/）を除いたテキストを置いた。PDF本体はブランチ claude/project-thread-9bdbbg の同じ場所にある。
