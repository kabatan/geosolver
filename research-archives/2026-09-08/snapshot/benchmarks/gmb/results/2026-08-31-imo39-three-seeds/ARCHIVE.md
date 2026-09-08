# 3seedの証跡保存

2026-08-31、seed 0の保存済み結果とseed 1/2の追加結果をまとめて保存した。
元のseed 0のraw・Git側の結果・archiveは変更していない。

## 全raw archive

- path：`/home/kabatan/work/solver-research-assets/gmb-campaigns/gmb-imo39-three-seeds-20260831.tar.gz`
- size：2,763,397 bytes
- SHA-256：`10525e67b9705387a3e624cceda27bc4c8a7311dbfa59ba4c5fe86dd3e67d0a8`
- regular files：1,169。archive内のファイル集合および各ファイルのSHA-256が、元の2directoryと一致することを確認済み。

archiveには次の2directoryをそのまま収録した。

| directory | SHA256SUMS対象ファイル | checksum一覧自身も含むファイル数 |
|---|---:|---:|
| `gmb-imo39-seed0-cpu4-20260831/` | 404 | 405 |
| `gmb-imo39-seeds1-2-cpu4-20260831/` | 763 | 764 |

36問×3seedの108実行、95model、stdout/stderr・events・資源・実行identity、入力、
依存lock、manifest、試験記録、集計、報告書を含む。仮想環境そのものは含めず、版と配布物hashをlockで記録した。
元の人工入力による計測hook検査は旧archiveに保存したままであり、この新archiveには重複収録しない。
これは同じPC内の別directoryへの複製であり、別装置へのbackupとは主張しない。

## hashの対応

| 対象 | SHA-256 |
|---|---|
| seed 0 manifest | `c543237e768aeb1413ac3baf83c5cabe16bebbf02d8a72987a34681fdd847cb4` |
| seed 0 SHA256SUMS | `7a3caf361a08a05dc6743366058fa3ec9e517c32aea9b694ae97f8aa5e27bf00` |
| seed 1/2 manifest | `bfe5be6053acaed565f366bbeebf2de156a57a4eab076944c4e9a8826863947f` |
| seed 1/2 SHA256SUMS | `e8dfbfe2924ecaefdc327a6ef9d5a78085ec6e716348b29e09d8cf703502d143` |
| 元のseed 0 archive（人工入力検査を含む） | `a910d94f94e3c12db5ae94d6565cf9fbd5e6289d3a48f5236eb64e4abf45bef4` |

元のarchiveの所在は[旧保存記録](../2026-08-31-imo39-seed0/ARCHIVE.md)を参照。
このARCHIVE.md自体は自己参照を避けるためarchive外のGit側に置く。

## 確認済み事項

- 両campaignのSHA256SUMSを検証し、元のseed 0の404ファイルも不変。
- 各campaignのJSON集計、3seedを合わせたJSON/CSV集計を再生成し、保存値と完全一致。
- 別のraw検査scriptで、108実行・95model・117行・39問題、eval判定、seed、入力・環境・CPU固定の対応を確認。
- Git側へ複製した結果・manifest・方針・checksumは、封印した追加rawの同名ファイルとbyte単位で一致。
- 実行前の全316試験、および実行後のGMB関連30試験に合格。追加コード・検査scriptのRuffも合格。
- GeoSolver本体、323問の入力・参照値、依存lock、solver-a0 tagは変更していない。

このdirectoryのSHA256SUMSは、Git側の小さい抜粋だけではなく、追加raw全763ファイルの一覧である。
hash検査はraw directoryまたはarchive展開先で行う。3seed全体の解釈にはcombined-summary.jsonを使用する。

```bash
sha256sum /home/kabatan/work/solver-research-assets/gmb-campaigns/gmb-imo39-three-seeds-20260831.tar.gz
```
