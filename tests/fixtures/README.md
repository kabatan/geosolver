# 独立した回帰試験データ

現行solverの挙動を確認するための、自己完結した回帰試験入力。評価runnerの初期値や正解生成には使わない。

- `forbidden-boundary-candidates.json`: JMO 2009とHMMT 2007で以前誤受理された2候補。candidate IDと座標文字列をそのまま保持する。これらは正解・初期値ではなく、最終検証で拒否すべき反例。
- `jmo-2009-boundary.json`: 境界誤受理と有効な非退化配置を対照検査するための別表現DSL。現行323問の登録とは独立。
- `independent-configurations.json`: 手計算・独立な数学計算から得た変数代入式と期待値。`checks`で残差評価、最終検証、厳密化の対象を指定し、現在のsolverで再検査する。旧実行結果のstatusや残差は使わない。

誤受理候補に記録した元artifactのパスとSHA-256は来歴情報であり、実行時の依存ではない。元資料はGit履歴または[repo外の保全先](../../README.md#作業場所と旧資料)から確認できる。
