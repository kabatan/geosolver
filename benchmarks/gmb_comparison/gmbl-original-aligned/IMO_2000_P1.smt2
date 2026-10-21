; Derived from rkruegs123/geo-model-builder, commit f070afe18ed874b3a31db519ea6f593f40a1be00.
; Copyright 2020 Ryan Krueger. Apache-2.0; see LICENSE.
; Modified 2026-08-31: restore the original problem's near-M tangent condition.
; This is a research comparison input, not the unmodified official GMB input.
(param C point)
(param D point)
(param M point (on-seg C D))

(param A point)
(param N point (on-circ (circ C A M)))
(define B point (inter-lc (para-at A (line C D)) (circ N M D) rs-arbitrary))

(assert (tangent-lc (line A B) (circ C A M)))
(assert (tangent-lc (line A B) (circ N M B)))

(define P point (inter-ll (line N A) (line C M)))
(define Q point (inter-ll (line N B) (line M D)))
(define E point (inter-ll (line C A) (line D B)))
(assert (on-ray E D B))
(assert (on-ray E C A))

(assert (gt (dist N (foot N (line A B))) (dist M (foot M (line A B)))))

(eval (cong P E Q E))
