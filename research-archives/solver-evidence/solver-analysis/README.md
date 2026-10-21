# 機構分析資料の読み方

固定実装`e703e2d99484793f162f961bc50126ae65e4069f`を調べた過去の研究です。
ソースhashは`sha256:6d59d43c8bcbe882e0cf35457e1671ed7ef94a421b6c67c8c98268308f2fe758`で、現在のresearchとは異なります。

まず[日本語報告書](report/research-report-ja.md)または[PDF](report/research-report-ja.pdf)を参照してください。
[元の全資料索引](original-index.md)は当時の案内として保存しています。その全リンク先がGitに含まれるわけではありません。

## Gitで取得できる資料

- `report/`：最終報告書、図、節ごとの説明、描画依存の記録。
- `implementation-map.md`：当時の実装と分析の対応。
- `analysis/`：323問×5seedの問題別集計、47問×30seedの詳細集計、段階・停止・予測の要約など。
- `audits/`：監査への回答、反証、主張の採否。
- `unknown-intake/`：別途選定した自然60問と追加7入力、選定・凍結した予測、停止認定の補足。これらには実行済みの結果があり、新しい未使用holdoutとして扱いません。
- `unknown-references/`：探索入力と分離した採点用参照と分離記録。
- `reproducibility/`：当時の製品ソース・研究コード・323問・依存lockのtar、ソースhash、ローカル生データの全ファイル索引。
- `literature/comparison-v1.md`：文献と今回の主張の対応。

## 結果の読み方と限界

成果は、特定の自然問題での残差表現・目標・精密化・停止の関係を説明したものです。
元の自然60問では自動因子検出は0/60、全pipelineの成否予測は全保留でした。
人手で構造を解析した自然2問では8開始中6認定が一致、2開始を保留しています。一般の未知問題の成否予測を達成したという報告ではありません。

実行済みの別集合や局所介入の例を、未使用の生成88入力と混同しないでください。
seedや同一軌道の複数目標を、独立した問題数へ加算しません。

## 完全な生データと再現

ローカルの全資料は`/home/kabatan/work/solver-experiment/research-archives/solver-analysis/`に残っています。
`reproducibility/archive-files.jsonl`は当時の全資料のファイルhash索引です。
このコンパクト版の収録内容は親の`import-manifest.json`で確認できます。

再現用tarには当時の`benchmarks/solver_analysis/`も含みます。空の別作業ディレクトリで展開し、収録lockから環境を構築してください。
元の索引にあるコマンドは当時の配置を前提にするため、そのまま現行researchで実行せず、展開したソースと新しい出力先を指定します。
生データが必要な再集計・図の再生成にはローカル完全版が必要です。
