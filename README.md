# Savant

**The Independent, User-Owned Living DNA Framework for AI Agents and Swarms.**

Savant is the open-source system that gives every agent — and every swarm of sub-agents spawned by Grok, Claude Code, Codex, or any model — its own persistent, private, user-controlled pool of experience (DNA = memory + reasoning patterns). Each sub-agent starts with an empty pool that grows only with its own lived work, while the swarm compounds intelligence under your complete control.

**DNA = Memory + Patterns** (starts empty, fills with real use).

When an agent deploys sub-agents (Grok spawn_subagent, Claude Code agents, Codex workers, etc.), each child automatically receives an isolated Savant Pool under `~/.savant/swarms/<swarm_id>/<subagent_id>/pool/`. Sub-agents grow their own private DNA while the swarm compounds collective intelligence under explicit user-controlled policies — exactly like connecting the lived experience of multiple agents (the "Exo Labs for agent minds").

User sovereignty is absolute: settings, isolation policy, sharing rules, retention — all user-controlled and overridable by the user at any time (including by telling any connected AI "use these Savant pool settings").

This is the foundation for true multi-agent self-improvement and training that respects the person who owns the machine.

Rather than another general-purpose agent, Savant serves as the **evolutionary layer** above individual agents and orchestrators. It enables agents to extract valuable patterns from successful work, package them as structured Genomes, transfer them across different agent implementations, and collectively improve them over time through real usage.

## Core Philosophy

- **Structure enables reliable sharing and evolution.** Free-form skills are powerful for single agents. Typed, schema-enforced, versioned Genomes make capabilities transferable and systematically improvable across an ecosystem.
- **Agents teaching agents.** The highest-leverage progress comes from creating first-class mechanisms for capability transfer and collective advancement.
- **Reproducibility with emergence.** Strong contracts, schemas, and audit trails provide trust and determinism, while still supporting novel combinations and improvement.
- **Open by default.** Public (or private) registries, clear provenance, and MIT licensing lower the barrier for contribution and adoption.

## What Savant Delivers

- **Agent Genomes**: Portable, versioned units of specialized capability. Each Genome combines a structured framework, high-signal reasoning patterns, proven tool compositions, evaluation data, and full provenance.
- **Living Registry**: A discoverable, forkable collection of Genomes that agents and teams can browse, adopt, adapt, and contribute improvements to.
- **Evolutionary Engine**: Mechanisms for scanning successful runs, proposing improvements, merging compatible Genomes, and applying selection pressure based on measured performance.
- **Orchestration Layer**: A typed, genome-aware orchestrator that selects, composes, and dispatches work to the most appropriate worker agents while tracking effectiveness.

## Relationship to Existing Work

Savant builds directly on two strong foundations:

- The structured framework approach for typed, reproducible agent work (YAML definitions, deterministic steps, output schemas, public registry model).
- Deep patterns from high-quality agent systems (autonomous improvement loops, rich tool surfaces, memory management, observability, and interruptible execution).

Savant is designed to work *with* capable worker agents rather than replace them. Worker agents (rich external or custom) can both contribute to and benefit from the Genome ecosystem.

## Current Status

Early foundation stage. We are building the Savant Framework with a strong emphasis on:

- Professional-grade terminal experience (TUI/CLI)
- A first-class, evolvable Genome data model
- Clean separation between orchestration and evolutionary learning
- High-quality patterns for agent ecosystems

## Installation

Savant follows the same high-quality installation experience as Hermes.

### One-line Install (Recommended)

```bash
curl -fsSL https://vektraindustries.com/savant/install | bash
# or
curl -fsSL https://vektraindustries.com/savant/install.sh | bash
```

This is the canonical, production-grade installer. It:
- Verifies Python ≥ 3.11
- Installs the latest Savant from source
- Sets up your PATH correctly (bash, zsh, fish)
- Creates `~/.savant/` with proper structure
- Offers to launch the TUI immediately

After installation, just run:

```bash
savant
```

You will be greeted with the professional onboarding flow and the dedicated first-launch welcome screen.

### Manual Installation

If you prefer not to use the installer:

```bash
python3 -m pip install --user git+https://github.com/PabloTheThinker/savant.git
export PATH="$HOME/.local/bin:$PATH"
savant
```

**Requirements**
- Python 3.11 or newer
- pip

**Once on PyPI** (coming soon):
```bash
pip install savant
savant
```

### Quick Verification

```bash
savant doctor          # Health check
savant --help
savant pool status     # Your DNA pools
```

The first run will trigger the full Hermes-style setup wizard and create your initial global Savant Pool.

### Updating

Re-run the one-line installer at any time — it is safe and will upgrade in place.

### Platform Notes

- **Linux / macOS**: Full support.
- **Termux (Android)**: Works with some limitations (no heavy browser extras).
- **Windows**: Use WSL2 (recommended) or Git Bash + Python.

For the absolute latest development version or to contribute, see the [Development](#development) section below.

```bash
savant --version
savant doctor          # Health check, config, workers (external adapters), registry
savant genomes list
savant config show
savant workers list
savant tui             # Launch the interactive professional TUI
```

### Using the CLI

```bash
# Genome operations
savant genomes list
savant genomes info security-incident-postmortem-1.0.0

# Scan runs for new genomes (stub in v0.1, full scanners + external run ingestion soon)
savant scan /path/to/agent/run

# Configuration (stored in $SAVANT_HOME/config.yaml, default ~/.savant/)
savant config show
savant config set savant.log_level DEBUG
SAVANT_HOME=/tmp/my-savant savant doctor   # fully isolated home for testing/CI

# Worker / external agent adapters (key extension point)
savant workers list
```

### Environment

- `SAVANT_HOME` — override the data directory for full isolation
- All data lives under `$SAVANT_HOME/{genomes,logs,cache,config.yaml,.env}`

### Running Tests

```bash
python -m pytest tests/ -q
# or after `pip install -e ".[test]"`
pytest
```

The test suite uses fully isolated temporary `SAVANT_HOME` per test via contextvar overrides.

### Extension Points (for external & other agents)

- **Workers**: Implement `savant.workers.base.Worker` or use `ExternalAgentAdapter` / `get_default_adapter()`
- **Scanners**: Register via `entry_points."savant.scanners"` or subclass `BaseScanner`
- **Adapters**: `savant.workers.adapters` — contribute runs from any instrumented agent to the genome pool
- Config, logging, and errors are production-ready from `savant.config` and `savant.constants`

See `ARCHITECTURE.md`, `GENOME-SPEC.md`, and the `src/savant/` package for deeper integration.

## The Savant Pool + Harness (The Living Ecosystem Layer)

This is the heart of Savant’s power:

- **SavantPool**: The central, persistent repository where all valuable DNA (Genomes) flows in from every agent and run in the ecosystem.
- **SavantHarness**: The lightweight execution adapter any agent can use to:
  1. Dynamically pull the most relevant Genomes for its current task.
  2. Adapt its reasoning, prompts, or tool selection using that DNA.
  3. Record outcomes so the pool learns and the collective intelligence improves.

Any capable worker (rich external, custom agents, etc.) can participate simply by wrapping its work with the harness.

Example usage:

```python
from savant import SavantHarness

harness = SavantHarness(agent_id="my-rich-worker")

with harness.task_context("Deep security incident postmortem"):
    dna = harness.pull_relevant_dna()                    # pull from the living pool
    prompt = harness.inject_into_context(base_prompt)    # adapt using real frameworks + patterns
    result = do_the_actual_work(prompt)
    harness.record_outcome(result)                       # feed value back → pool evolves
```

The pool grows smarter with every run. The harness gives agents a standard, powerful way to benefit from (and contribute to) that collective intelligence while still getting their job done.

See `examples/rich_agent_with_savant_pool.py` and `examples/savant_pool_demo.py` for runnable demonstrations.

## Getting Started with Swarms (Quickstart)

Savant’s killer feature is giving **every sub-agent its own living, private DNA pool**.

### 1. Install & Verify
```bash
curl -fsSL https://vektraindustries.com/savant/install | bash
savant doctor
savant              # or savant tui
```

### 2. Spawn a Swarm (Conceptual — any parent runtime)

Tell your primary agent (Grok, Claude, custom orchestrator):

> “For this mission, use swarm_id = 'payments-review-2026-05-23'. Spawn 3 sub-agents with distinct subagent_ids. For each child, set the environment variables SAVANT_SWARM_ID and SAVANT_SUBAGENT_ID, then wrap its execution with the SavantHarness so it pulls relevant DNA at the start and records outcomes at the end. Use the pool settings in my ~/.savant/config.yaml.”

### 3. Minimal Manual Sub-Agent (Python)

```python
import os
from savant import SavantHarness
from savant.constants import get_swarm_pool_path
from savant.pool.pool import SavantPool

swarm_id = os.getenv("SAVANT_SWARM_ID", "demo-swarm")
sub_id   = os.getenv("SAVANT_SUBAGENT_ID", "worker-1")

pool = SavantPool(pool_dir=get_swarm_pool_path(swarm_id, sub_id))
harness = SavantHarness(agent_id=f"{swarm_id}:{sub_id}", pool=pool)

with harness.task_context("Your sub-task here"):
    dna = harness.pull_relevant_dna(top_k=5)
    enriched = harness.inject_into_context(base_prompt)
    result = do_your_work(enriched)
    harness.record_outcome(result)   # auto-improves this sub-agent’s pool (and upward if allowed)
```

### 4. Configure Swarm Policies

```bash
savant config set pool.global.isolation_level subagent
savant config set pool.swarms.payments-review-2026-05-23.isolation_level swarm
savant config set pool.swarms.payments-review-2026-05-23.sharing_policy selective
```

Or open the TUI → Pool view → Settings panel.

### 5. Watch It Grow

- `savant pool stats`
- `savant tui` → Pool view (global + per-swarm tabs, live queries, ingest history)
- Each sub-agent’s private directory: `~/.savant/swarms/<swarm_id>/<sub-id>/pool/`

Full details: `docs/SWARM.md`, `docs/POOL.md`, `docs/SETTINGS.md`, `docs/INTEGRATION.md`.

## License

MIT License for the core framework.

---

Savant exists to make specialized agent intelligence a shared, compounding, and systematically improvable resource — rather than something rediscovered repeatedly in isolation.