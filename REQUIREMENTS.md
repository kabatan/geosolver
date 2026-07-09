# Requirements

Status values: `active`, `refined`, `superseded`, `completed`. An active
requirement may not disappear; supersession requires a replacement ID, reason,
lost-capability note and owner approval.

## Goals

| ID | Status | Requirement |
|---|---|---|
| GOAL-01 | active | Maximize fixed-budget probability of recovering every distinct correct scalar target value. |
| GOAL-02 | active | Generalize to unseen instances, compositions, families and custom plugins. |
| GOAL-03 | active | Remain a numerical optimization/root-solving system; exact whole-system algebra is not the standard path. |
| GOAL-04 | active | Prioritize speed while improving correctness, multi-answer recall and singular-case stability. |
| GOAL-05 | active | Replace per-case rescues with measurable, failure-family-level mechanisms. |
| GOAL-06 | active | Keep the implementation functional, nonredundant, maintainable and independently reproducible. |

## DSL and plugin ABI

| ID | Status | Requirement |
|---|---|---|
| DSL-01 | active | Preserve open-world black-box geometric expressiveness without mandatory polynomial lowering. |
| DSL-02 | active | Core graph nodes are Literal, Reference, plugin-qualified Call and Select. |
| DSL-03 | active | PluginSpec is the source for Julia dispatch metadata, JSON symbols, generated Python bindings, docs and capability reports. |
| DSL-04 | active | Built-ins use the same versioned, content-locked plugin ABI as external plugins. |
| DSL-05 | active | Relation residual, truth, domain, guard, branch and target have separate semantics. |
| DSL-06 | active | Choice values expose stable candidate keys and validity margins; selectors are generic. |
| DSL-07 | active | Capabilities distinguish C0 Float64, C1 derivatives, C2 BigFloat, C3V validated intervals and C3A algebraic proof. |
| DSL-08 | active | Capability loss is explicit; no silent fallback or precision downcast. |
| DSL-09 | active | JSON never auto-installs code; registries are explicit, allowlisted and frozen per compile/solve. |

## Answer and runtime semantics

| ID | Status | Requirement |
|---|---|---|
| ANS-01 | active | ExactAnswer and ProvisionalAnswer are disjoint public answer levels. |
| ANS-02 | active | Algebraic exact values carry a primitive square-free minimal polynomial, rational isolating interval and real-root index. |
| ANS-03 | active | Configuration validation and target algebraic identity are separate certificates. |
| ANS-04 | active | Float target clusters are reversible scheduling hypotheses; irreversible deduplication requires proof. |
| ANS-05 | active | Deadline/cancellation returns verified partial results and typed search status. |
| ANS-06 | active | Checkpoint resume requires graph, plugin, policy and environment hash equality. |
| ANS-07 | active | Strict guards must be separated from zero by validation before answer promotion. |
| ANS-08 | active | Continuous target sensitivity is reported, not forced into finite enumeration. |

## Architecture

| ID | Status | Requirement |
|---|---|---|
| ARCH-01 | active | GeoTargetBase owns graph/ABI/results; Core owns compiler/search/verification; Geometry is a plugin; Python owns authoring/protocol only. |
| ARCH-02 | active | Search depends only on EvaluationOracle and never on geometry primitive names. |
| ARCH-03 | active | The compiler performs type checking, constant folding, CSE, DCE, dependency/sparsity extraction and typed scalar/batch lowering. |
| ARCH-04 | active | A solve-local ExecutionContext owns deadline, RNG, precision, registry, buffers, policy, events and cancellation. |
| ARCH-05 | active | One Proposal/Observation protocol feeds one event loop, CandidateStore and append-only EvidenceLog. |
| ARCH-06 | active | Types are numeric-generic; Float64 and BigFloat object hierarchies are not duplicated. |
| ARCH-07 | active | Internal failures are typed; broad catch is limited to process/protocol boundaries. |
| ARCH-08 | active | Public presets are stable; research knobs are centralized in versioned SolvePolicy and remain non-public. |

## Research and quality

| ID | Status | Requirement |
|---|---|---|
| RES-01 | active | Preregister each algorithm experiment with controls, counterexamples, budgets, seeds and promotion/kill gates. |
| RES-02 | active | Use primary papers/official documentation and record assumptions and break conditions. |
| RES-03 | active | Diagnose the first failing checkpoint with a common failure taxonomy and Miss Analyzer. |
| RES-04 | active | Use parameterized families, ablations, family-disjoint locked validation and burned-holdout replacement. |
| RES-05 | active | Maintain permanent minimal controls: full-support multistart, fixed-start local solve, canonical validation and unconstrained archive/refinement references. |
| RES-06 | active | Run metamorphic tests over ordering, transforms, scaling, equivalent residuals, redundancy, graph form, branch order and target affine maps. |
| QA-01 | active | Core architecture tests forbid geometry-name coupling, mutable global solve state, eval, silent fallbacks and duplicate truth-bearing pipelines. |
| QA-02 | active | Fuzz at least 10,000 graph evaluations and 1,000 solves without crashes, deadlocks, corruption or RNG/precision interference before v1. |
| QA-03 | active | Release with zero open P0/P1 correctness defects and replayable environment locks. |

