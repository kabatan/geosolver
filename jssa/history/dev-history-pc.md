# 制作経緯（PC上のgit履歴から）

出典はすべて C:\geosolver の `git log --all`（773〜779件）です。動機がcommitに書かれていないものは推測せず「記録なし」としました。

## このPCで見つからなかったもの

- `codex/research-before-publish-20261022`、`codex/solver-hardening`、`codex/research-before-import-20260830` はどのクローンにもありません。ブランチは research、claude/project-thread-nycxfb、bisect-*、jssa-* だけです。
- 履歴の最古は **2026-07-10**（4749153 "chore: ratify clean-slate solver charter"）です。1月〜7月9日の履歴はこのPCのgitにありません。
- `~/work/solver`、`research-archives/2026-10-21/...`、`optimization-20261011/`（候補v1〜v8）はWSLとC:\にありません。v1〜v8の段階別測定は一覧できません。

## 日付別

| 日付 | commit | 内容（commitメッセージ） |
|---|---|---|
| 07-10 | 4749153 | chore: ratify clean-slate solver charter（履歴の最初） |
| 07-10 | a38902c | research: preregister singular refinement study |
| 07-10 | 1458167 | research(local): preregister rank-aware solver comparison |
| 07-11 | d0fb08b | research(disc): preserve validated scaling fallback |
| 07-12 | 5776aeb | feat(exact): add isolated algebraic backend scaffold |
| 07-12 | c157254 | feat(exact): add owned PSLQ recognition（julia/GeoTargetExact/src/pslq.jl 348行） |
| 07-12 | cad8eb9 | feat(exact): add C3A exactification backend |
| 07-12 | 379264c | chore(research): remove rejected Powell hybrid code（EXP-LOCAL-007、−4,895行） |
| 07-13 | aa78a93, cb81114, d620a9a | research: rank-precision rescue wave / rank rescue T0 |
| 07-27 | 05439a7 | research: freeze champion experiment evidence（nomad_backend、mpmath_refiner、IsTangent が最初に現れる） |
| 07-27 | 19a6e4e | feat: productize frozen champion solver（1431ファイル） |
| 07-29 | 0967ff1 | feat: ship qualified optimized champion solver（lattice の語が最初に出る） |
| 07-30〜31 | 130e5f4, 0346339, fd991f0, 807be91, 2b1ed15, f669472 | experiment: interval rescue / Krawczyk rescue / trig algebraic proposals / angle equality fallback / exact transport fallback |
| 08-05 | 807ff91 | benchmark failed cases after mpmath refiner fix |
| 08-12 | 32bd715 | fix: identify algebraic affine pi answers |
| 08-24 | a5045c6 | refactor(package): unify distribution under geosolver（189ファイル、−66,751行） |
| 08-26 | 7b2ebf1 | fix: restore NOMAD backend and high-precision polar（PyNomadBBO が最初に現れる） |
| 08-31 | de0e90f | refactor: remove obsolete repair assets and unused runtime paths（−10,050行、323問のDSLは維持） |
| 09-08 | 2b096ab | Archive research solver and GMB experiments |
| 10-21 | 052a477 | Archive research working tree before core cleanup（algebraic_branches が最初に現れる） |
| 10-22 | 1aa9139, 7b6691b | Publish current solver and benchmark core / mechanism evidence |

## 機構ごと（`git log --all -S<語>` の最初の出現）

- **NOMAD**: `nomad_backend` 05439a7（07-27）、`PyNomadBBO` 7b2ebf1（08-26 "restore"）。8/26より前に外れた時期があるかもしれませんが未特定。選んだ理由は記録なし。
- **第2探索・rescue**: 憲章 4749153 に語。実装は 07-13 の rank rescue と 07-30〜31 の interval/Krawczyk 試作。`second_attempt` は 10-22 の実験commit（6e7308c, d064075）が最初。
- **代数的な近道**: `algebraic_branches` 052a477（10-21）。前身は 07-12 の exact backend と 07-31 の trig algebraic proposals。
- **多倍長精密化**: `mpmath_refiner` 05439a7（07-27）。07-10 に singular refinement の事前登録（a38902c）。
- **PSLQ**: c157254（07-12）、Julia GeoTargetExact に自前実装。
- **IsTangent書き換え**: 語の初出は 05439a7。動機を述べたcommitは未発見。
- **格子点探索の削除**: 明確な1件は未特定。a5045c6、de0e90f が候補だが断定しない。
- **GeoTargetとGeoSolver**: 07-10〜12 は Julia の GeoTargetExact（exactification）が中心。07-27 に geosolver 製品化（19a6e4e）、08-24 に配布物を geosolver に統合（a5045c6）。関係を述べた説明文は未発見。
- **試して捨てた方法**: commitに rejected と明記されたのは Powell hybrid（379264c）のみ。

## 本人に聞くとよい点

NOMADを選んだ理由、IsTangent書き換えの動機、lattice削除の時期と理由、1〜7月9日の経緯、codex/* ブランチとv1〜v8の所在。
