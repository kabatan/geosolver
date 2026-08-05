# Strict inequality / 退化境界の受理バグ修正

## 結論

問題のDSLは変更せず、solverの候補受理経路を修正した。修正前は、strict guardを
通過した全候補に `margin=1` を返していたため、`margin < 1e-8` のPhase C gateが
実質的に無効だった。これにより、`r=0+ε`、面積 `=0+ε`、`p=q+ε` など、問題文の
開条件・非退化条件の境界へ収束した数値候補が受理されていた。

修正版は、guardの実際の値からスケール正規化したmarginを計算し、Phase Cにはその
値を渡す。finiteなmarginが既定の `1e-8` 未満なら `margin_too_small` として拒否し、
marginが実際に正で十分離れた候補だけを厳密化する。DSLへ任意のepsilonを追加したり、
`post_process`で解を削除したりしていない。

## 変更点

- `AssumeGt/Lt/Ge/Le/Eq/Ne`、open bound、logical guardについて、左右差を尺度で
  割った正規化marginを計算する。
- `AssumeConvex` / `AssumeStrictConvex` は各連続turnの最小正規化cross/sineをmargin
  とする。面積が数値的に極小の一直線枝を受理しない。
- guard interpreter、float/HP evaluator、candidate/refiner、Phase C間でmarginを
  保持する。探索中のtrialだけは従来どおりmargin計算を省略し、速度を維持する。
- 1-D探索の浮動小数点closure候補を、最終受理を弱めずに高精度refinerへ渡せるよう
  `1e-8` から `1e-6` の探索側窓へ変更した。Phase Cの残差 `1e-15` とmargin gateは
  変更していない。このため HMMT-2006-FEB-GEO-10 の正しい第二根 `r=24` を、scanの
  `1.2e-7` 程度の丸め誤差だけで捨てなくなった。
- PSLQが `x^k` を極小非零値から `0` と誤同定する経路を拒否する。数値的に厳密な
  zeroでない場合はexact zeroを返さない。

## 証拠

修正前の実装は `_evaluate_guard_check` で、guardが通れば常に `mp.mpf("1")` を返して
いた。一方、Phase Cの閾値は `1e-8` である。したがって例えば HMMT-2018-FEB-GEO-05
の `theta = pi - 6.3e-122` は Boolean上 `guard_ok=true` かつ `margin=1` となり、
面積・答えが `6.3e-122` の退化枝が受理された。修正版では同じ候補のmarginは
`O(1e-122)` となり、`margin_too_small` で拒否される。

小さな再現（修正版）:

```text
AssumeGt(x, 0), x=1e-100:
  dps=80  -> guard false, margin=1e-100
  dps=120 -> guard false, margin=1e-100
  dps=300 -> guard true,  margin=1e-100
  dps=500 -> guard true,  margin=1e-100
```

Booleanの計算精度に依存せず、最終受理には同じ実数marginを使うため、丸めで1へ
置換されることはない。

## 回帰検証

- `compileall`: pass
- 既存のgeometry / contract regression: **36 passed**
- `verify_strict_guard_fix.py`: pass（`1e-122` のstrict候補は拒否、margin=1の候補は受理）
- HMMT-2018-FEB-GEO-05（以前は `{0, 8*sqrt(2)/9}`）: Phase Cのaccepted集合は正答
  のみ（余分な退化候補は `margin_too_small` で拒否）。
- HMMT-2010-FEB-GEO-09: 退化四辺形の `180` は拒否し、`{70,160}` の厳密解集合を
  取得。
- HMMT-2006-FEB-GEO-10: 探索側closure窓の修正後、正しい `24` を取得し、`r≈0` は
  `margin_too_small` で拒否。

12件（過去監査でstrict inequality / 退化境界の偽陽性が確認されたケース）を
`seed=7, 180秒 hard timeout, 1 job, CPU 0` で再測定した結果は
[`benchmark_results_180s_1core_strict_guard_fix_v2_2026-08-05.json`](benchmark_results_180s_1core_strict_guard_fix_v2_2026-08-05.json)
に保存する。採点はpost-processではなく、Phase C raw `answer_values`と独立truthの
厳密解集合の双方向一致で行う。

結果は **12/12 success、10/12 strict exact** だった。12件すべてで境界枝は
accepted集合から除外され、`margin_too_small` として記録されている。残る2件は
`HMMT-2014-FEB-GEO-10`（target近傍のdecimalのみ）と `HMMT-2023-FEB-GEO-04`
（`sqrt(5)` のdecimalのみ）で、いずれも余分な境界解を返した失敗ではなく、厳密式
同定の別問題である。

runtimeはGit管理対象外のため、適用状態は
[`runtime_strict_guard_fix_manifest.json`](runtime_strict_guard_fix_manifest.json) の
SHA256で固定した。再適用用のunified diffは
[`runtime_strict_guard_fix.patch`](runtime_strict_guard_fix.patch) に保存している。元のfrozen runtime `/home/kabatan/work/solver-experiment-runtime`
は変更していない。実験用コピーは `/home/kabatan/work/solver-experiment-runtime-strictfix`
である。

frozen runtimeのルートで適用する場合は `patch -p1 < runtime_strict_guard_fix.patch` を
使い、適用前後にmanifestのSHA256を検証する。

## 残る不一致の扱い

この修正で消えるのは「strict/open/nondegenerate条件の境界候補を受理する」系統だけ
である。正答の数値近傍を厳密式へ同定できない HMMT-2014-FEB-GEO-10、
HMMT-2023-FEB-GEO-04 などは、境界偽陽性とは別の exactification / basin到達問題で
あり、今回のmargin修正でDSLを書き換えてはいない。
