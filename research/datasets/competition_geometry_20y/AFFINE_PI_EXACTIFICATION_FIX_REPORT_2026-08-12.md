# `A·π+B` exactification 一般修正

## 結論

πを含むdecimal-only 3件を、`A` と `B` が実代数的数である

```text
x = A·π + B
```

として同定する一般経路を追加した。問題ID、期待解、DSLの`answer`式は探索に使っていない。
180秒/1 core再測定では **3/3 strict exact answer-set一致**、timeout、no_solution、
exceptionはいずれも0だった。

## 探索アルゴリズム

有理係数の場合は `[x, π, 1]` にPSLQを適用し、整数関係から `A` と `B` を復元する。
一般の代数係数では、`x^i π^j` の全次数付き単項式にPSLQを適用して二変数整数多項式
`P(x,π)`を得る。その多項式を厳密因数分解し、各square-free factorへ
`x=A·t+B`を代入する。`t`の全係数が0になる多項式系を厳密に解き、次を全て満たす
候補だけを残す。

- `A` と `B` はともに実数で、SymPyが代数的と証明できる。
- `minimal_polynomial(A)` と `minimal_polynomial(B)` を厳密計算できる。
- factorへの代入結果は`t`の恒等的な零多項式である。
- 復元式`A·π+B`そのものと入力数値の距離が`10^-(dps-20)`以下である。
- 同じ許容範囲内に相異なる候補が複数あればfail closedする。

πの超越性により、代数的な`A,B`を持つこの表現は一意である。ただし有限精度の数値から
任意次数・任意heightの代数的数を無制限に探索することはできない。そのため既存の代数的
PSLQと同様に有限上限を設け、strict tierは二変数関係の全次数4、standardは3、relaxedは
有理係数の次数1までとした。strict tierは`√2·π+√3`だけでなく、係数が別々の代数体に
属する`(1+√2)π/3+(√5−2)`も復元する。

## 誤受理防止

整数関係の残差だけでは受理しない。例えば入力が`π−2+10^-70`なら、
`(x−π+2)^2`相当の関係残差は`10^-140`になり得る。しかし修正版はfactorをsquare-free化し、
最終的に式`π−2`との直接距離`10^-70`を検査する。120 dps設定の許容値`10^-100`を
満たさないため拒否される。

また、`π²+1`は`x−π²−1=0`という低次数関係を持つが、代数的`A,B`によるaffine形ではない
ため拒否する。`e·π+1`も係数`e`が代数的でないため拒否する。通常の整数・有理数・代数的数は
従来のminimal-polynomial経路を先に通り、π探索で上書きしない。

## 180秒 / 1 core 再測定

共通条件はseed 7、hard timeout 180秒、jobs=1、`taskset -c 0`、affinity `[0]`、
`one_core_enforced=true`。Phase C raw厳密集合と監査済みtruthの集合一致で採点した。

| case | 期待厳密集合 | Phase C厳密集合 | wall秒 | strict exact |
|---|---:|---:|---:|---:|
| HMMT-2006-FEB-GEO-04 | `{27π/40}` | `{27*pi/40}` | 1.358 | yes |
| HMMT-2008-FEB-GEO-03 | `{π−2}` | `{-2 + pi}` | 85.173 | yes |
| HMMT-2010-FEB-GEO-01 | `{3π/7}` | `{3*pi/7}` | 1.394 | yes |

生データは
[`benchmark_results_180s_1core_affine_pi_fix_three_2026-08-12.json`](benchmark_results_180s_1core_affine_pi_fix_three_2026-08-12.json)
に固定した。DSL、truth、answer projection、post-process、solverの数値許容値は変更していない。

## 回帰検証

- affine-π、repeated-factor、case-specific分岐禁止のfocused tests: **11 passed**
- geosolver全suite: **142 passed, 1 skipped**
- 新規module/testのRuff: pass
- `identify_answer.py` import ordering: pass
- `compileall`: pass
- 合成代数係数2例: pass
- 精度不足・非affine・非代数係数対照: reject

## 再現物

修正版runtimeは `/home/kabatan/work/solver-experiment-runtime-piaffinefix`。基点のrankfix runtimeと
それ以前のfrozen runtimeは変更していない。SHA256は
[`runtime_affine_pi_exactification_fix_manifest.json`](runtime_affine_pi_exactification_fix_manifest.json)、
差分は
[`runtime_affine_pi_exactification_fix.patch`](runtime_affine_pi_exactification_fix.patch) に固定した。

基点ファイルには以前からCRLF/LFが混在するため、再適用時は改行空白を無視する。

```bash
git apply --ignore-space-change --ignore-whitespace \
  runtime_affine_pi_exactification_fix.patch
```

一時base treeへの実適用後、3ファイルの全行が修正版と意味的に一致することを確認済みである。
runtime hash、DSL hash、benchmark条件、一般代数係数・偽陽性対照は
`verify_affine_pi_exactification_fix.py`で機械検証できる。
