# skill-creator

The meta-framework that lets the system **create new frameworks**.

You hand it a paragraph of "I want a framework that does X." It hands
back a ready directory: typed inputs, ordered steps, JSON Schema,
README, and a sample input. Drop the directory into the frameworks
registry tree, hand-tune anything that needs human judgment, and you
have a new framework.

## Inputs

| key                | type    | required | notes                                                       |
|--------------------|---------|----------|-------------------------------------------------------------|
| `skill_description`| string  | yes      | Plain-English description of what the skill should do       |
| `proposed_id`      | string  | yes      | kebab-case framework id (e.g. `customer-discovery-synthesis`) |
| `target_category`  | string  | no       | `business`/`codebase`/`dataset`/`organization`/`custom`     |
| `example_intake`   | object  | no       | An example intake that should validate against the new schema |

## Pipeline

1. `extract_inputs` — derive a typed input specification from the description.
2. `plan_steps` — propose an ordered list of steps (id, agent, dependencies, with-clauses, output keys).
3. `design_output_schema` — synthesize a JSON Schema for the final artifact.
4. `draft_readme` — write the README the new framework needs.
5. `compose_artifact` — validate the assembled output against this framework's own schema.

## Why this exists

With `skill-creator`, the system can ingest a description of a recurring
decision (legal review, customer postmortem, infra audit) and synthesize
a framework draft on its own. The operator still owns the merge — but
the long pole of typing out YAML, schema, README, and a sample input is
gone.

## Future iterations

- Wire `skill-creator` into the architect pipeline so the output
  is dropped directly into a new framework directory under the
  registry root.
- Add a `--validate-with` flag that runs the new framework against the
  `example_intake` immediately and fails the build if the output doesn't
  schema-validate.
- Pair with `framework-from-engagement` so successful one-off engagements
  become reusable frameworks automatically.
