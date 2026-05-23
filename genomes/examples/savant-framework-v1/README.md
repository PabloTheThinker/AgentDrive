# Savant Framework

> *Total recall. Instant structural synthesis. Zero tolerance for vagueness.*

The Savant Framework is the flagship typed framework — a single cognitive
pass that turns a corpus of observations (plus an optional chat transcript)
into a fully-typed, schema-validated artifact. Every claim it makes carries
a count and a citation. Every step it takes is in the audit ledger before
the action runs. Every output is reproducible.

This is the executable form of the Savant cognition primitives.
The Python modules are the muscle; this framework is the workflow.

---

## Workflow — Five Layers

The framework runs five layers in order. Each layer's output is consumed
by the next, and the whole stack composes into one typed artifact.

```
┌─────────────────────────────────────────────────────────────────┐
│  1. OBSERVATION  — refuse vagueness, force structure            │
│       audit_inputs   (savant_audit_vagueness)                    │
├─────────────────────────────────────────────────────────────────┤
│  2. SYNTHESIS    — build structure from the raw blob            │
│       induce_schema           (savant_induce_schema)             │
│       synthesize_framework    (savant_synthesize_framework)      │
│       infer_pattern           (savant_infer_framework)           │
├─────────────────────────────────────────────────────────────────┤
│  3. DETECTION    — find what breaks the pattern                 │
│       anomalies               (savant_detect_anomalies)          │
│       cross_domain_joins      (savant_cross_domain_join)         │
│       contradictions          (savant_detect_contradictions)     │
├─────────────────────────────────────────────────────────────────┤
│  4. REASONING    — walk the audit ledger, explain itself        │
│       reconstruct_trace       (savant_reconstruct_reasoning)     │
│       mine_causality          (savant_mine_causality)            │
├─────────────────────────────────────────────────────────────────┤
│  5. LEARNING     — improve over time                            │
│       recognize_pattern       (savant_recognize_pattern)         │
│       calibrate               (savant_calibrate)                 │
├─────────────────────────────────────────────────────────────────┤
│  compose_artifact — validate against output_schema, persist      │
└─────────────────────────────────────────────────────────────────┘
```

The audit ledger cross-cuts every layer. Each tool call writes an
open-entry before the work runs and a close-entry after, so the
reasoning layer can reconstruct the chain of thought from the ledger
itself — not from a prompt summary.

---

## Inputs

| Name                 | Type   | Required | Purpose                                              |
|----------------------|--------|----------|------------------------------------------------------|
| `observations`       | array  | yes      | Typed observation rows (kind, identity, summary…)    |
| `transcript`         | array  | no       | Chat messages — drives `infer_pattern` + `recognize` |
| `prior_observations` | array  | no       | Baseline for identity-novel anomaly detection        |
| `calibration_topic`  | string | no       | Topic key in the calibration store                   |
| `pattern_corpus`     | string | no       | Corpus key in the pattern memory                     |

## Output

A JSON artifact validated against
[`schemas/savant-framework-v0.1.json`](../../schemas/savant-framework-v0.1.json).
Top-level keys mirror the layers: `audit`, `synthesis`, `induced_schema`,
`inferred_pattern`, `anomalies`, `joins`, `contradictions`,
`reasoning_trace`, `causality`, `pattern_matches`, `calibration`.

---

## Why this framework matters

Every other agent framework in May 2026 lets you write a workflow.
**This one writes the workflow's audit trail too**, refuses vague
language, demands a citation for every count, persists what it learns
across runs, and emits a typed artifact you can diff between runs.

That is the difference between an agent that talks and an agent that
*thinks like Christian Wolff*.
