# H07 v1/v2 candidate audit

These are draft English teacher examples for two H07 rows marked `train` and tagged as shape augmentations by the benchmark authoring metadata. At the model-visible level, the geometry template is unchanged: the prompts expose only alternative numeric givens `AB`, `ON`, and `MF`. Generator parameters `x0,y0` are not present in either prompt or answer, so the examples are numeric counterfactuals, not model-visible shape conditioning. The prompts and complete general proof come from the accepted `external-H07-v0` teacher. The source audit accepted its numeric result, radial-root relation, reflection construction, and branches. Only the final numerical branch is adapted here. The audit below uses H07 v1/v2 benchmark input rows and H07 generation metadata only; no H08/H15 instance or evaluation record was used.

## Exact substitution and branch

The general proof establishes `λ=OA²/ON²` with `M=λN`, `0<λ<1`, `PQ=AB(1−λ)`, and `area(EPQ)=AB·MF·(1−λ)`. The prompt already specifies that `NAB` is acute and scalene. Numerically verifying `0<λ<1` also confirms that M is on the ordered segment `ON`; with `MF=3>0` this makes `PQ>0` and the area nondegenerate.

| Variant | `AB`, `OA`, `ON²` | `λ=OA²/ON²` | `PQ=AB(1−λ)` | Height `2MF` | Independent exact area |
| --- | --- | --- | --- | --- | --- |
| v1 | `7`, `7/2`, `2401/148` | `37/49` | `12/7` | `6` | `(1/2)(12/7)·6=36/7` |
| v2 | `8`, `4`, `256/13` | `13/16` | `3/2` | `6` | `(1/2)(3/2)·6=9/2` |

Both λ values are strictly between 0 and 1. Thus the source proof's branch-dependent facts apply: M lies between O and N, `|w|<a` follows from `M=λN` and the acute-triangle condition `|u|<a`, and C,D are the genuine second intersections. The reflection point E lies a positive distance `2MF` from horizontal line PQ; because `PQ>0`, triangle EPQ has positive area.

## Feasibility witness from the v1/v2 generator parameters

As an additional audit-only check on the stated acute-scalene domain, the H07 generator places the tangent points at A=(0,0), B=(c,0), and its M-witness at `(x0,y0)`. These hidden generator parameters are not model inputs. Translating O to the origin and using the computed λ gives these N witnesses:

| Variant | `M−O` | `N=(M−O)/λ` | `ON²` | Side-length squares `NA², NB², AB²` |
| --- | --- | --- | --- | --- |
| v1 | `(-1/2,3)` | `(-49/74,147/37)` | `2401/148` | `882/37,1225/37,49` |
| v2 | `(-2,3)` | `(-32/13,48/13)` | `256/13` | `16,720/13,64` |

For v1, `|u|<a=7/2` and `ON²=2401/148>49/4=a²`; for v2, `|u|<a=4` and `ON²=256/13>16=a²`. These are the acute-angle tests at A/B and N in O-centered coordinates. The three side squares in each row are distinct, so both generator witnesses are scalene. Also their M heights are 3 and N heights exceed 3, consistent with M being closer to AB. This check is supplementary; the candidate prompts retain the benchmark's acute-scalene condition.

The examples are untrained candidates. The geometric and arithmetic checks validate their construction and labels; they do not establish transfer or model performance.
