# Q13：完成solverの役割付け替え比較

[最終回答](answer.md)の判定は**中止**。開発323問、seed 0、180秒、1コア、最大8並列でB/R各313問正答、救済・喪失0件。探索的比較であり、時間は高負荷下の参考値。追加のsolver実験とQ2用登録文の作成は実施しない。

## 保存物

| ファイル | 内容 |
|---|---|
| `preregistration.md` | 探索前に固定した予測・対象・判定基準・中止基準 |
| `execution-lock-initial.json` / `execution-lock.json` | 事前登録、入力、コード、凍結ソース、実行環境のハッシュ・日時 |
| `manifest.json` / `scope-audit.md` | 全323入力の接条件規則、既存処理と追加処理の境界 |
| `hook/sitecustomize.py` / `hook/role_patch.py` | workerへの導入と数値パッチ。最終採否の関数は保持 |
| `prepare.py` / `preflight.py` | 入力監査・ロック準備、人工残差の機能検査 |
| `preflight-B.json` / `preflight-R.json` | B/R各15評価の検査結果 |
| `run.py` / `transport.py` / `common.py` | 最大8実行の対応比較、CLI輸送、共通の保存・ハッシュ検査 |
| `report.py` | 既存記録の採点・集計。optimizerを起動しない |
| `verify_delivery.py` | 全返却値・実行条件・採点・ソース同一性・並列数の最終照合。optimizerを起動しない |
| `campaign/{B,R}/runs/<ID>/0.json` | 主解析の全646 raw結果 |
| 同じ場所の `0.receipt.json` | 起動／終了時刻、コア、負荷、worker同梱監査の記録 |
| `return-bundles/000.json`〜`049.json` | 親へ戻ったrawとreceiptの控え。rawはzlib圧縮＋base64、各ファイル20MB未満 |
| `per-run.csv` / `per-problem.csv` / `summary.json` | 実行別、対応問題別、集計結果 |
| `completion.json` / `artifact-recovery.json` | 完了記録と同じ実行の返却値からの1件復元 |
| `delivery-verification.json` / `failures.json` | 646件の照合結果と共通不正答10問の詳細 |
| `deviations.md` / `numerical-code-identity.json` | 記録障害・運用変更・失敗と、数値関数7個のAST一致 |
| `interrupted-attempt/` / `interrupted-attempt-2/` | 主解析に混ぜない2回の中断試行と修正前実装の保存分 |
| `transport-smoke/` / `check_transport.py` | 変数なし人工例B/R各1回による返却経路の確認 |

## 保存結果だけを再集計する

リポジトリのルートで、指定環境を変更せず実行する。下記は保存記録の読取り・照合と本フォルダ内の集計更新のみで、新しいsolver／optimizerは呼ばない。ロック不一致時は停止する。`prepare.py`や`run.py`の再実行はこの再集計手順に含めない。

```bash
env PYTHONPATH=src PYTHONDONTWRITEBYTECODE=1 /home/kabatan/work/solver/.venv/bin/python jssa/difficulty/role-reassign/report.py
env PYTHONPATH=src PYTHONDONTWRITEBYTECODE=1 /home/kabatan/work/solver/.venv/bin/python jssa/difficulty/role-reassign/verify_delivery.py
```

`verify_delivery.py`は返却バンドルと保存JSONを照合し、欠落ファイルがあれば同じ実行の返却値から復元する。内容が食い違う場合は停止する。公式答え集合から採点を再計算するが、solverへ公式答を渡さない。最終照合の結果は646件すべて合格だった。

`execution-lock.json`の基準日時・`actual_optimizer_calls_so_far=0`は初期固定時点の値であり、その後の総実行数ではない。修正日時は別キー、実行数は各試行のcompletion/audit、最終判定はsummaryにある。主解析の監査はworkerの返却artifactに同梱され、独立ログの有無だけには依存しない。

事前登録SHA256：`eeb355396bd3ebdbe048a4cd82dbbe41800e3bdde0c2ef7ec1cd06f394f63c7a`。

凍結ソース署名：`sha256:d8fd9bb8392ad2984276bab3386e033669246ee79586317917c322d31b4541f5`。
