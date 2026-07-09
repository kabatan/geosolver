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

