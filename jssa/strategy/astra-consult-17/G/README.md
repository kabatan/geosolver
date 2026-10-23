# astra-G 成果物と再現

最終回答は [answer.md](answer.md)。結論、根拠、(a)〜(f)、追加6の切り分けを含む。
ここにある改変は研究用であり、凍結版solverの成績・既定設定の変更ではない。

## ファイルの対応

| 内容 | コード | 記録・集計 |
|---|---|---|
| 前セッションの事前基準 | — | `preregistration-pilot.md`（変更なし） |
| 292問の開始点・失敗終点・入力特徴 | `common.py`, `census.py` | `census.json/csv`, `endpoint-diagnostics.jsonl`, `census.log` |
| 14問のhard罰則除去 | `intervention.py` | `intervention.json`, `intervention-summary.json/csv`, `paired-outcomes.csv`, `intervention.log` |
| 旧集計・入力モデル | `analyze.py` | `summary.json`, `input-models.json`, `input-predictions.csv`, `analysis.log`, `provenance.json` |
| AIMEの終点と差分・hit方向の調査 | `aime_geometry_audit.py` | `aime-finite-difference.csv`, `aime-geometry-summary.json`, `aime-geometry.log` |
| 前セッションの全残差評価点 | `intervention.py` | `aime-traces.json`（受理・拒否の記録ではない） |
| 追加6の実行前の固定基準 | — | `preregistration-resume.md` |
| native試行・停止条件の6条件比較 | `mechanism.py` | `mechanism-data/*.json`, `mechanism.log`, `native-aime-traces.json`, `native-trace.log` |
| 6条件の集計・R1–R5 | `summarize_mechanism.py` | `mechanism-summary.json/csv`, `mechanism-status.csv`, `native-aime-summary.csv`, `native-last-steps.csv`, `mechanism-analysis.log`, `mechanism-provenance.json` |
| 定数行で拒否された試行の事後検算 | `constant_audit.py` | `constant-audit.json/log`, `constant-rejected-trials.csv` |
| 引き継ぎ・元データの再照合 | `audit_existing.py` | `inheritance-audit.json/log`, `instrumentation-before-fix.json` |
| 納品時の整合性確認 | `verify_delivery.py` | `delivery-check.json` |

## 実行方法

リポジトリのルートで実行する。Python環境は変更せず、依存関係を追加しない。
`common.py` がこのリポジトリの `src/` と既存ベンチマーク補助コードの場所を
読み込みパスに追加する。新しいファイルはこのGディレクトリだけに作る。

```bash
export PYTHONDONTWRITEBYTECODE=1
export OPENBLAS_NUM_THREADS=1
export OMP_NUM_THREADS=1
export MKL_NUM_THREADS=1
```

保存データを読み直すだけの集計（新しい局所探索なし）：

```bash
/home/kabatan/work/solver/.venv/bin/python jssa/strategy/astra-consult-17/G/analyze.py
/home/kabatan/work/solver/.venv/bin/python jssa/strategy/astra-consult-17/G/summarize_mechanism.py
/home/kabatan/work/solver/.venv/bin/python jssa/strategy/astra-consult-17/G/constant_audit.py
/home/kabatan/work/solver/.venv/bin/python jssa/strategy/astra-consult-17/G/audit_existing.py
/home/kabatan/work/solver/.venv/bin/python jssa/strategy/astra-consult-17/G/verify_delivery.py
```

`analyze.py`の数値最小化は入力モデルのロジスティック回帰の当てはめであり、
幾何の局所探索ではない。`audit_existing.py`は292問の全開始点の許容判定と、
指定3例の摂動を再評価する。既存の集計ファイルは再生成する。

追加6の局所探索そのものを再現する場合（事前基準を読んでから実行）：

```bash
/home/kabatan/work/solver/.venv/bin/python jssa/strategy/astra-consult-17/G/mechanism.py --stage trace
/home/kabatan/work/solver/.venv/bin/python jssa/strategy/astra-consult-17/G/mechanism.py --stage all
/home/kabatan/work/solver/.venv/bin/python jssa/strategy/astra-consult-17/G/summarize_mechanism.py
```

`all`は固定した14問×80開始点×6条件、最大4プロセス、各条件10秒、
MINPACKの上限80評価（差分評価は別）である。`trace`はseed 0のAIMEの
k=2,3,5について同じ6条件を走らせる。元の開始点のJSONを必要とする。
全例の評価時間合計は最終再実行で約190秒だったが、記録処理込みの値であり、
速度比較の実験ではない。開始点は問題内で対応し、全条件の最終採点は同じ。

旧実験を最初から再現する場合は `census.py` → `intervention.py` →
`analyze.py` → `aime_geometry_audit.py` の順。`intervention.py`は新しい局所探索を
実行する。他の大規模計算と同時に起動して4並列を超えないようにする。

## statusと軌道の読み方

- `optimizer.status`はSciPyの番号。1=gtol、2=ftol、3=xtol、4=ftol+xtol、0=評価上限。
- `native.raw_info`はMINPACKの番号。1=ftol、2=xtol、3=両方、4=gtol、5=評価上限。
  6/7/8は機械精度の制限である。S/CSでこれらが出た場合、SciPyへの返却だけ
  6→1、7→2、8→4に変換するため、必ずraw infoを併読する。
- B/S/J/N/C/CSの意味と変更点は `preregistration-resume.md` に固定されている。
  S/CSはftolとgtolを0にするが、機械精度の停止や、厳密に直交した場合のgtol=0停止は残る。
- `native.tail`は最後の8試行。`base`が比較対象の受理基点。
  `decision_from`は次のnative jacまたは返却点を使った復元である。
  `same_coordinate=true`は`unknown`とし、受理とも拒否とも数えない。
- 残差関数の全呼び出しには差分点もあるが、nativeの`fun`呼び出しとは区別している。
  この環境ではnative入口に初回チェックが1回余分にあり、`fun_calls=nfev+1`、
  `jac_calls=njev`となることを全6,720実行で照合した。
- Jの`optimizer.optimality`はSciPyが終了後に元の差分関数で再評価した値で、
  nativeへ渡した変更後のJによる勾配ではない。Jの機構の解釈には
  `last_native_jac.hard_jac_used`を使い、optimalityは使っていない。
- hard罰則を外しても、等式が非有限の場合の全残差`1e10`置換や、最終の
  hard/guard/箱の判定は残る。errorを一律にPython例外と解釈しない。

## 引き継ぎ時の修正と限界

前セッションのコード・データ・事前基準は利用可能で、再計算で不整合は
見つからなかった。旧 `aime-traces.json` は差分点を含み、受理・拒否の証拠として
は使わない。新しいnative記録で補った。

追加計測の最初の版では基点と全く同じ座標への呼び出しを試行表から省いていた。
それをunknownとして保存するよう修正し、固定した全6,738実行を再実行した。
修正前の最終分類・座標・残差・答え・status・raw infoのハッシュを
`instrumentation-before-fix.json`に残し、修正後と全問一致した。
主分析には修正後の記録だけを使う。追加実行総数は13,476、独立反復数を
二倍にした集計ではない。事前基準と最適化条件は変更していない。

定数対照で最後の試行が採点上hitなのに拒否されたことは、結果を見た後に
保存座標を再評価して分かった。これは `constant_audit.py` に分け、事前予測の
成功数に加えていない。内部の信頼領域半径、λ、fnorm、ratioは取得していない。

今回の全問題・旧seedの結果は開発データであり、未知問題への予測検証は
未実施。`answer.md`の本検証案も未実行である。文献の確認範囲と未確認箇所は
同ファイル(f)に記載した。
