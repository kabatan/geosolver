# GMB IMO39・単一seed基準計測 v1

この文書と計測実装を、本集合の最初の実行前にcommitする。
目的はこのPCでのGMBの動作・資源使用の測定であり、GeoSolverとの優劣や、
原論文の数値の厳密再現を主張する実験ではない。

## 対象を減らさない

[論文v2 §4](https://arxiv.org/html/2012.02590v2)は39問中36問が表現可能、
3問は図形の個数が可変で表現非対応と記載している。
[公開実装](https://github.com/rkruegs123/geo-model-builder/tree/f070afe18ed874b3a31db519ea6f593f40a1be00/problems/IMO)
の36入力をbyte単位でそのまま使用する。入力を修正・翻訳・追加しない。

非対応3問のIDは論文本文の一覧ではなく、公開入力との差分と問題文からの照合による：
IMO 2002 P6（任意個数の単位円）、2006 P6（一般の凸多角形）、2011 P2（風車問題）。
[2002公式問題](https://www.imo-official.org/problems/2002/eng.pdf)、
[2006英国代表団長の報告](https://www.imo-register.org.uk/2006-report.html)、
[2011公式問題](https://www.imo-official.org/problems/2011/eng.pdf)を参照。
manifestにこの照合根拠と確度を記録し、非対応3行は実行時間nullで残す。

## 事前に固定する条件

- 各入力1回、seed 0。Python・NumPy・実際のTensorFlow graphにseedを設定する。
  seedによる成功確率の推定はしない。研究計画の20反復比較は別campaignとする。
- Linux x86-64、CPU4に固定、1ジョブずつ順次実行。1論理CPUのみ使用するので、
  SMTの2threadを同時使用しない。TensorFlow・BLAS等も各1thread、GPU無効。
- 1問180秒。新規processの起動直前から計測し、import・parse・graph構築・探索・
  座標保存・終了を含む。超過時SIGTERM、最大2秒後SIGKILL。終了猶予は別記する。
- 公開commitと全依存を固定。探索は`util.DEFAULTS`のまま：5000反復、3試行、
  10初期値、1model、eps=0.001、学習率0.1等。`enforce_goals=False`を維持。
  `verbosity/plot_freq/loss_freq/losses_freq=-1`とする（上流experimentと同じ表示抑制）。
- 年・問題番号順。ウォームアップは人工smokeのみ。本集合での調整・選別はしない。
  異常・失敗後の自動再試行はしない。再測定は新campaignとし、旧結果を保存する。
- CPUは占有せず、他の作業・SSD監視を止めない。SMT sibling、背景負荷、
  周波数設定を保存する。物理CPU固定は競合や周波数変動を消す保証ではない。

## 成功・失敗と時間

主結果はGMB自己判定による配置生成（`model_returned`）である。
期限内に正常終了し、`build(..., show_plot=False)`が1個以上のmodelを返した場合のみ該当する。
`no_model`、`timeout`、`error`、`crash`、`resource_violation`、`unsupported`を分ける。
途中で配置が保存されても、timeout後に成功へ読み替えない。

原論文と同様に、生成済みmodelの`eval`の値がすべて`eps*10=0.01`以下かを副集計する。
`eval`なしは未評価とする。これは上流の内部計算値による診断であり、独立な幾何検証や
定理の証明ではない。目的の証明・求値・厳密解列挙の成功率とは呼ばない。
元問題の全条件とDSLの意味同値性・数値的正当性の独立検証は今後の共通検査器の課題。

主時間は起動～process終了のwall time。最初のmodel取得、build区間、preprocess、
初期値生成、trainの時間も保存する。phaseは入れ子なので合計しない。
timeoutは打切りを明記し、成功例だけの平均と全実行の平均を混同しない。
Linux `wait4`のuser+system CPU時間、最大RSS、終了code、affinity観測も保存する。

## 記録方法と改変の範囲

公式sourceは変更しない。実行時subclassでgraph seedと時刻・モデル保存hookを追加し、
各上流methodを1回だけ呼ぶ。追加のTensorFlow評価やoptimizer更新は行わない。
人工入力でhook有無の座標一致を確認する。hook・I/Oの費用は測定に含める。
GMBが内部で捕捉するtrain例外も記録するが、上流の回復挙動は変更しない。

`campaign-manifest.json`、入力copy、各runのrequest・stdout/stderr・events・座標・
終了情報、CSV/JSONL、summary、SHA256SUMSを保存する。
solver source、依存lock、harness、環境検査、CPU情報のhash/identityを記録する。
GMBのcheckpointは各run専用作業領域に限定する。既存artifactを上書きしない。
checksumは破損・差し替え検出のためであり、第三者による実験認証ではない。

## 主張できないこと

原論文は3反復、時間計測範囲も異なり、180秒の外側制限は報告されていない。
このPC・Python・依存versionも論文と同一とは限らない。
原論文の平均27.07秒との直接的な速度比、単一seedからの安定性、
GeoSolverに対する優劣は、この実験からは主張しない。
