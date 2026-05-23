# codebase-architecture-map

Reads a codebase summary and produces a structured architecture map: component inventory, dependency graph, hotspots, recommended refactor passes, and risk register.

## When to use it

- New engineer onboarding to an unfamiliar codebase
- Engineering leader auditing technical debt before a major release or restructure
- Acquisition / due diligence assessment
- "Should we rewrite or refactor?" decision support

## What you get

| Section | Content |
|---|---|
| Archetype | What kind of codebase this is (monolith, microservices, library, CLI tool, framework, etc.) with rationale + comparable projects |
| Components | 3+ named components with role, size estimate, external deps, owned subsystems |
| Dependency graph | Edges between components with edge kinds (calls/depends_on/extends/etc.) and any detected cycles |
| Hotspots | Components with issues, each tagged with severity (low/medium/high/critical), evidence, and estimated effort |
| Refactor passes | Ordered list of recommended refactor work with rationale, scope, effort, risk |
| Risk register | Identified risks with likelihood/impact/mitigation |

## Inputs

- `repo_summary` (required, string) — 2-5 paragraph plain-English description of the codebase
- `language` (required, string) — primary language (Python, TypeScript, Go, Rust, etc.)
- `loc` (optional, integer) — approximate total lines of code
- `tech_stack` (optional, array of string) — frameworks, runtimes, databases, infra
- `team_size` (optional, integer) — engineers actively committing

## Step graph

```
classify_archetype
    └─→ enumerate_components
            ├─→ build_dependency_graph
            │       └─→ recommend_refactors
            ├─→ identify_hotspots ─────────────┤
            │       └─→ recommend_refactors    │
            │       └─→ assess_risks ──────────┤
            └─→ assess_risks ──────────────────┤
                                                └─→ compose_artifact (validate)
```

## Version history

- **0.1.0** (2026-05-13) — Initial framework. All steps dispatched to core worker.
