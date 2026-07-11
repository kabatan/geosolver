# ADR-0003: Separate discovery, validation and exactness

Status: Accepted  
Date: 2026-07-10

## Decision

A discovered candidate is not an answer. A ProvisionalAnswer has an independent
high-precision or validated numerical recheck. An ExactAnswer additionally has
both a configuration validity certificate and a target algebraic identity
certificate. PSLQ/minimal-polynomial recognition is only a proposal step.

Search coverage, configuration validity, and target exactness are independent
claims and are represented independently in the result schema.

As of Phase M3 (2026-07-12), the numerical recheck means a 512-bit compiled C2
refinement plus an independently restarted 768-bit reference refinement and
fresh canonical replay. It requires `1e-100` residual, coordinate and target
agreement. This remains numerical evidence; C3V interval evidence and C3A
exact proof retain their separate assurance levels.
