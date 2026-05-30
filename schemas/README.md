# AgentDrive Framework Output Schemas

This directory holds (or will hold) the JSON Schema files referenced by
genome `framework.output.schema` entries.

## Contract

- When a `FrameworkSynthesis` (from `agentdrive.reasoning.synthesizer`) is turned
  into a real genome, the corresponding `<id>-vX.Y.json` Schema should live here
  (or be referenced relatively from the genome's `framework.yaml`).
- The synthesizer currently emits a sibling-style name. Materialization code
  (genome writer, promotion service, etc.) is responsible for ensuring the
  file exists and is valid.
- These schemas describe the *output* shape of a framework execution, not the
  framework definition itself.

## Current Status

As of the current evolution tranche, many genomes are still in "candidate" or
"extracted" state. Real schemas will be added as high-value frameworks are
promoted from the DNA / dream loops into production genomes.

See:
- `src/agentdrive/reasoning/synthesizer.py`
- `src/agentdrive/scanners/rich_run_scanner.py`
- Genome manifest + framework materialization paths
