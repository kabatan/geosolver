# 独立した回帰試験データ

大容量の過去campaignをテスト環境へコピーせずに、同じ反例を再検査するための抽出データ。

- `forbidden-boundary-candidates.json`: JMO 2009とHMMT 2007で以前誤受理された2候補。candidate IDと座標文字列をそのまま保持する。これらは正解・初期値ではなく、最終検証で拒否すべき反例。
- `independent-configurations.json`: 手計算・独立な数学計算から得た12配置の変数代入式。旧検証結果のstatusや残差はコピーせず、各テストで現在のsolverを用いて再検査する。

元artifactの相対パスとSHA-256を各ファイルへ記録した。元ファイルは[repo外の保全先](../../README.md#作業場所と旧資料)のsnapshotディレクトリ以下に元の相対パスで保存されており、このブランチからの相対参照ではない。
移植時に全座標・代入式が元データと文字列として一致することを確認する。campaign runnerはこれらのfixtureを読み込まない。
