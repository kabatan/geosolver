# Exactification repeated-factor verification fix

## 結論

これは特定の72を通すための変更ではない。PSLQが返す任意の整数関係を、そのまま
「最小多項式」として残差検証していた一般的な検証器欠陥を修正した。

修正版は次の順で処理する。

1. 関係をprimitive・positive-leading形式へ正規化する。
2. SymPyの厳密因数分解で重複因子を除去し、数値候補に最も近い実根を持つirreducible
   factorを選ぶ。
3. そのfactorについて、元の多項式残差だけでなく、最寄りの実根との距離も同じ
   precision toleranceで検証する。
4. 因子の選択が曖昧、因数分解できない、定数または零多項式の場合はfail closedする。

したがって、`(x-72)^2` は検証時に `x-72` へ縮約される。誤差を二乗した残差はもはや
受理条件にならない。正確な入力 `x=72` は、通常どおり `[1,-72]` として受理される。

## 再現証拠

候補を

```text
v = 72 + ε
ε ≈ 8.516793148599... × 10^-88
```

とする。修正前の高設定では、PSLQが `[1,-144,5184]`、すなわち
`(x-72)^2` を返し、残差は約 `7.2552×10^-175` となるため、`precision_dps=180` の
許容誤差 `10^-160` を通過していた。

修正後の同じ入力では、関係は `[1,-72]` に正規化され、残差は
`8.5167×10^-88` と報告される。これは `10^-160` を満たさないため、候補は
`verification_failed` / `not_identified` となる。つまり、同じ近似値を二乗残差で
誤って72へ厳密化することはない。

一方、正確な `72` では残差・根距離ともに0で、`selected_exact_value="72"`、
`minimal_polynomial=(1,-72)` となる。

## 変更対象

- `polynomial_search.py`: 関係のprimitive化、因数分解、重複因子除去、因子選択。
- `verify_identified_answer.py`: canonical factorと根距離を含む二重検証。
- `identify_answer.py`: 旧/外部検索器からの非canonical relationに対する防御的正規化。

DSL、問題定義、answerのpresentation変換、post-processは変更していない。

## 回帰検証

- exactification専用回帰: **4 passed**
- geosolver既存テスト: **132 passed, 1 skipped**
- `compileall`: pass

適用済みruntimeのSHA256と再適用用unified diffは
[`runtime_exactification_factor_fix_manifest.json`](runtime_exactification_factor_fix_manifest.json)
および [`runtime_exactification_factor_fix.patch`](runtime_exactification_factor_fix.patch) に固定した。
CRLFの外部runtimeへ再適用する場合は、`runtime_strict_guard_fix.patch` 適用後に
`patch --binary -p1 < runtime_exactification_factor_fix.patch` を実行する。
実験用runtimeは `/home/kabatan/work/solver-experiment-runtime-exactfix`、旧strict-guard
測定用runtimeは `/home/kabatan/work/solver-experiment-runtime-strictfix` として分離し、
元のfrozen
runtime `/home/kabatan/work/solver-experiment-runtime` は変更していない。
