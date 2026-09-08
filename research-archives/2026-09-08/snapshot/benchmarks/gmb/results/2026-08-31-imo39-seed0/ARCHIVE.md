# 証跡の保存場所とhash

## 全rawデータ

作業用directory：
`/home/kabatan/work/solver/benchmarks/local-evaluation/gmb-imo39-seed0-cpu4-20260831/`

研究資産archive：
`/home/kabatan/work/solver-research-assets/gmb-campaigns/gmb-imo39-seed0-cpu4-20260831.tar.gz`

- archiveサイズ：1,058,033 bytes。
- archiveのSHA-256：`a910d94f94e3c12db5ae94d6565cf9fbd5e6289d3a48f5236eb64e4abf45bef4`
- 本計測`SHA256SUMS`自体のSHA-256：`7a3caf361a08a05dc6743366058fa3ec9e517c32aea9b694ae97f8aa5e27bf00`
- 本計測manifestのSHA-256：`c543237e768aeb1413ac3baf83c5cabe16bebbf02d8a72987a34681fdd847cb4`

archiveには本計測directoryと、計測hookの不変性を確認した人工問題の
`gmb-imo39-harness-check-20260831/`を含む。
本計測404ファイル＋checksum一覧、人工問題33ファイル＋checksum一覧、計439ファイル。
全archive memberを展開せずに読み、保存元とのhash一致を確認済み。
同一PC内の複製であり、別媒体・別ホストへのbackupではない。

## Gitに保存したもの

報告書、事前方針、manifest、CSV/JSONL、summary、全raw用SHA256SUMS、本文書。
元の座標・stdout/stderr・phaseログは上記raw directory/archiveを参照する。
このGit directoryにはraw全404ファイルはないため、ここで直接
`sha256sum -c SHA256SUMS`を実行しないこと。全rawを置いたdirectoryで検査する。

```bash
# repo直下から、本計測の全hashとJSON集計を確認（solverの再実行はしない）
.venv/bin/python -m benchmarks.gmb.campaign verify benchmarks/local-evaluation/gmb-imo39-seed0-cpu4-20260831

# archiveそのものを確認
sha256sum /home/kabatan/work/solver-research-assets/gmb-campaigns/gmb-imo39-seed0-cpu4-20260831.tar.gz
```

Git側の各結果ファイルが全raw側の同名ファイルとbyte一致することも確認済み。
本計測の条件・harnessは実行前commit `77e97a8b`に固定した。
checksum固定後に本計測のrawデータは変更していない。
人工問題は本計測前のcontroller版で保存したため、古い集計を現在の書式へ上書きせず保全する。
