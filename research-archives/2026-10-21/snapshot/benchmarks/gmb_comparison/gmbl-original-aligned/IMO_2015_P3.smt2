; Derived from rkruegs123/geo-model-builder, commit f070afe18ed874b3a31db519ea6f593f40a1be00.
; Copyright 2020 Ryan Krueger. Apache-2.0; see LICENSE.
; Modified 2026-08-31: restore the original cyclic order A,B,C,K,Q.
; This is a research comparison input, not the unmodified official GMB input.
(param (A B C) acute-tri)
(assert (gt (dist A B) (dist A C)))
(define Gamma circle (circumcircle A B C))
(define H point (orthocenter A B C))
(define F point (foot A (line B C)))
(define M point (midp B C))

(param Q point (on-circ Gamma))
(assert (right H Q A))
(param K point (on-circ Gamma))
(assert (right H K Q))

(assert (opp-sides K B (line C A)))
(assert (opp-sides Q B (line K A)))

(eval (tangent-cc (circumcircle K Q H) (circumcircle F K M)))
