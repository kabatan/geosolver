# Selected program audit

2026-09-26. This is a source-based description of the 13 normalized programs frozen by the numeric public/selection checks. The code labels below describe what the submitted Python computes; they are not independent proofs that the proposed formulas hold for every admissible figure.

## Selection result

The long-cap initial collection and its 17 repair responses were processed by `pipeline.py select`. The frozen selection gate passed for seven sources: H01, H04, H07, H13, H15, DA01, and DA05. It accepted 13 programs (two per supported source except H15, which has one) and formed 13 code targets plus 56 numeric targets. The selection receipt records `private_final_outcomes_used: false`. No final-test cases or model outputs were opened for this audit.

H14 remains unresolved. Its four initial attempts failed program format extraction, and its four repair outputs reached the length cap. This is an output-completion/format limitation in this collection; it is not evidence that the model cannot solve H14 mathematically.

The SFT code targets are the selected `normalized_code` strings, wrapped in a Python fence. I checked that all 13 `train-code.json` targets match the selected normalized code exactly. Long derivation comments from the original completions therefore do not appear in those targets. Every selected target is a short, source-specific function using ordinary `math`/`cmath` and scalar arithmetic; none imports an external geometry solver or reads a lookup table.

## Per-source inspection

“Size” is normalized executable source characters / lines, not original completion length. Origin identifies the long initial generation or repair response that supplied the selected program.

| Source | Selected programs and origin | Normalized sizes | What the code computes |
|---|---|---:|---|
| H01 | 2 initial | 204/10, 179/8 | Both return the same compact relation, `abs(BC² − 4·AM²)/(4·AM)`. Their long source explanations use coordinates and projection; the target itself is the scalar formula. |
| H04 | 2 initial | 162/9, 136/7 | Both return `sqrt(BT·(BT+BC))`. Their source explanations try coordinate arguments; the normalized targets retain only the relation and a few assignments. |
| H07 | 2 initial | 773/32, 811/37 | Both reconstruct configuration-specific coordinates from AB, MF, and ON, form E/P/Q, then return the computed triangle area. These are constructive coordinate procedures rather than compact final area relations. |
| H13 | 1 initial, 1 repair | 1,041/36, 741/32 | Both reconstruct a triangle/auxiliary point from BC, BK, and the angle cosine, intersect lines to get J, determine the circumcenter of BJK, and return the measured CZ distance. The repair version uses an explicit 2×2 line-intersection calculation. |
| H15 | 1 repair | 1,334/54 | Uses complex coordinates to reconstruct D from AB, AD, BD, obtains C on the fixed 60° ray, reflects points across the specified lines, intersects the derived lines, and returns BK. This is a construction algorithm, not a closed scalar formula. |
| DA01 | 1 initial, 1 repair | 980/40, 328/15 | The initial version reconstructs C, the two tangent-circle centers, their second intersection, and returns AT. The repair version reduces the answer to `b·c/sqrt(2(b²+c²)−a²)`, where its code sets `a=BC`, `b=CA`, `c=AB`. |
| DA05 | 1 initial, 1 repair | 240/13, 147/9 | Both return the relation `BC²/(4·MD)−MD`. The repair code names `MC=BC/2` and computes `MC²/MD−MD`; the initial normalized code has two identical `solve` definitions, with the latter taking effect. |

The programs therefore split into two visible implementation styles: seven selected programs across four sources return compact relations (both H01, both H04, DA01 repair, and both DA05 entries), while H07, H13, H15 and initial DA01 construct points and measure the requested quantity. DA01 shows both styles for one configuration. This is a description of these selected outputs, not a claim about the model's internal representation or proof understanding.

## Observable implementation caveats

The coordinate programs contain ordinary floating-point branch handling. H07 clamps a negative radicand to zero in one candidate and returns zero for some invalid/near-degenerate constructions; another candidate replaces a near-zero denominator by an epsilon before continuing. H13's initial candidate calls its line-intersection helper and then unpacks the result without handling the `None` case; its circumcenter denominator fallback is only a `pass`, followed by division. The repair H13 candidate instead returns zero for a near-singular intersection and uses a zero-coordinate fallback for a near-zero circumcenter denominator. H15 clamps a negative reconstructed square to zero and returns zero for a near-singular line intersection; its reflection helper returns the input point for a degenerate line.

These branches did not prevent the selected programs from passing the fixed visible/repair public cases and private selection cases. They may limit behavior outside those tested numerical inputs. No extra tests or repairs were run during this audit, and no acceptance decision was changed based on these observations.

## Frozen selection artifacts

| File | SHA-256 |
|---|---|
| `qwen/.runtime/program_self_training_20260926/selection/receipt.json` | `f2441b1e513a450af52890dbbc2df63f3f05a186dadcd45bbbdaec6b8dce97a8` |
| `qwen/.runtime/program_self_training_20260926/selection/accepted-candidates.json` | `2adc899112239f19a60292b6e50d49203627214267795a87eb2fa5bb4e70c99e` |
| `qwen/.runtime/program_self_training_20260926/selection/train-code.json` | `90698ea82c93bc6b730ba98f01e7a9ef6a263b9b7d9043edd7bb324a9a46a219` |
| `qwen/.runtime/program_self_training_20260926/selection/train-numeric.json` | `75997401673246bca334de4e173c0e7553cdc3c56d486952463873ae7c99eba2` |

These hashes identify the frozen selection inputs only. They do not assert performance on the private final split or prove any general relation.
