| arm | jobs | exact (seed 0) | Δ vs baseline | lost | gained | wall median | wall mean | timeouts | paired time ratio median (both exact) |
|---|---|---|---|---|---|---|---|---|---|
| baseline (main j6, seed 0) | 6 | 317/323 | — | — | — | 5.26s | 18.94s | 4 | 1.00 |
| NO_ALGEBRAIC | 6 | 317/323 | +0 | 1 | 1 | 7.70s | 21.92s | 5 | 1.09 (p10 0.86, p90 3.39) |
| NO_NOMAD | 6 | 318/323 | +1 | 4 | 5 | 28.98s | 46.12s | 6 | 1.70 (p10 1.06, p90 7.11) |
| NO_ANALYTIC_JAC | 5 | 317/323 | +0 | 0 | 0 | 6.24s | 20.95s | 6 | 1.15 (p10 1.01, p90 1.34) |
| NO_RESCUE | 6 | 319/323 | +2 | 1 | 3 | 6.21s | 21.13s | 3 | 1.20 (p10 1.02, p90 1.38) |
| NO_SCALE_CHART | 6 | 316/323 | -1 | 1 | 0 | 6.35s | 21.05s | 5 | 1.17 (p10 1.01, p90 1.35) |
| NO_SECOND_ATTEMPT | 6 | 308/323 | -9 | 9 | 0 | 5.73s | 17.36s | 0 | 1.08 (p10 0.96, p90 1.25) |

Lost = exact in baseline seed 0 but not in the arm; gained = the reverse.

- NO_ALGEBRAIC: lost ['HMMT-2014-FEB-GEO-10']; gained ['JMO-2015-PRE-02']
- NO_NOMAD: lost ['AIME-2008-I-10', 'AIME-2019-II-15', 'HMMT-2009-FEB-GEO-01', 'aime-2001-2-6']; gained ['AIME-2016-I-15', 'HMMT-2013-FEB-GEO-04', 'HMMT-2016-FEB-GEO-10', 'JMO-2014-PRE-09', 'JMO-2015-PRE-02']
- NO_ANALYTIC_JAC: lost []; gained []
- NO_RESCUE: lost ['aime-2001-2-6']; gained ['AIME-2016-I-15', 'HMMT-2016-FEB-GEO-10', 'JMO-2015-PRE-02']
- NO_SCALE_CHART: lost ['HMMT-2011-FEB-ALGGEO-18']; gained []
- NO_SECOND_ATTEMPT: lost ['AIME-2007-II-15', 'AIME-2014-I-13', 'HMMT-2008-FEB-GEO-05', 'HMMT-2008-FEB-GEO-09', 'HMMT-2014-FEB-GEO-04', 'HMMT-2022-FEB-GEO-10', 'HMMT-2024-FEB-GEO-02', 'HMMT-2025-FEB-GEO-01', 'JMO-2023-PRE-06']; gained []
