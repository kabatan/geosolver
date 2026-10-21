; Synthetic environment check, not an IMO or held-out evaluation problem.
(param (A B C) triangle)
(assert (eq (dist A B) (dist A C)))
(define M point (midp B C))
(eval (eq (dist B M) (dist M C)))
