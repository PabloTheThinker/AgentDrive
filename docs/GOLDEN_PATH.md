# AgentDrive Golden Path

**~10 minutes from zero to a working agent memory loop.**

This is the canonical first-run path. Everything else (AD-Grid, Mission Control, federation, dream cycles) builds on top of it.

## What you get at the end

After completing the golden path you will have:

1. A local AgentDrive home at `~/.agentdrive/`
2. MCP wired into your AI CLI (Grok, Cursor, Claude, Continue)
3. An experience-layer seed so `think` has substrate to reason over
4. One cited synthesis with explicit gaps
5. One operational learning recorded for future sessions
6. One semantic drive query returning relevant genomes

That loop — **synthesize → record → query** — is the product magic.

---

## The seven steps

| # | Step | Command |
|---|------|---------|
| 1 | Install | `curl -fsSL https://vektraindustries.com/agentdrive/install.sh \| bash` |
| 2 | Health | `agentdrive doctor` |
| 3 | MCP | `agentdrive mcp install && agentdrive mcp doctor` |
| 4 | Seed *(optional)* | `agentdrive reconcile seed-experience-v3` |
| 5 | Think | `agentdrive think "What does my AgentDrive contain?"` |
| 6 | Learnings | `agentdrive learnings log --key first-run --insight "Golden path complete"` |
| 7 | Query | `agentdrive drive query "dedup identical agent outputs"` |

**Step 4 is optional** because the experience seed auto-runs on first Drive access (onboarding, setup, or any command that opens the Drive). Run it explicitly only if `agentdrive doctor` shows an empty registry.

---

## Fastest way (automated)

```bash
# Show the numbered steps
agentdrive golden-path steps

# Verify what's already done
agentdrive golden-path verify

# Run the walkthrough (live writes)
agentdrive golden-path run

# Plan without mutating (good for CI)
agentdrive golden-path run --dry-run
```

Or run the shell script:

```bash
bash examples/00_golden_path.sh
```

---

## Step-by-step (manual)

### 1. Install

```bash
curl -fsSL https://vektraindustries.com/agentdrive/install.sh | bash
```

Creates `~/.agentdrive/venv`, installs `agentdrive[mcp]`, and adds `agentdrive` + `agentdrive-mcp` to `~/.local/bin`.

**Dev clone instead:**

```bash
git clone https://github.com/PabloTheThinker/AgentDrive.git
cd AgentDrive
python3 -m venv ~/.agentdrive/venv
~/.agentdrive/venv/bin/pip install -e ".[mcp]"
```

### 2. Doctor

```bash
agentdrive doctor
```

Expect home directory, config, and registry checks. Warnings on a fresh install are normal. The doctor panel will point you at `golden-path` if the registry is empty.

### 3. Wire MCP

```bash
agentdrive mcp install
agentdrive mcp doctor
```

Restart your AI client. Verify inside MCP with `agentdrive_think` or `experience_graph_get_context_pack`.

See [MCP.md](MCP.md) for per-client config paths.

### 4. Seed (if needed)

```bash
agentdrive reconcile seed-experience-v3
```

Skip if `agentdrive drive status` already shows genomes. Auto-seed runs silently during onboarding.

### 5. First think

```bash
agentdrive think "What does my AgentDrive contain after first install?"
```

This calls `Drive.think()` with mandatory gap analysis. You get citations, gaps, and contradictions — not a generic LLM answer.

**No provider yet?** `agentdrive golden-path run` skips live `think` and prints a hint. Use `--dry-run` or configure a provider:

Provider required for live synthesis (not dry-run). Configure with:

```bash
agentdrive provider set openai --model gpt-4o
# or use a local model via agentdrive models list
```

### 6. Record a learning

```bash
agentdrive learnings log \
  --key first-run \
  --insight "Completed golden path — Drive seeded, MCP wired, first think done" \
  --type operational
```

Stored at `~/.agentdrive/learnings/<project-slug>.jsonl`. Harness preloads these on `harness compose`.

### 7. Query the Drive

```bash
agentdrive drive query "dedup identical agent outputs"
```

Semantic search across ingested genomes. After `examples/01_hello_drive.py`, this query should surface the dedup genome.

**API equivalent:**

```bash
python3 examples/01_hello_drive.py
```

---

## The compounding loop (why this matters)

```
Session N:   think → learnings log → drive query
Session N+1: harness compose (pulls learnings) → think (cites prior work) → ...
```

AgentDrive is not "remember this paragraph." It is **structural memory** — genomes, experience graph edges, operational learnings — that future agents can query, cite, and extend.

---

## What comes after the golden path

| When you're ready | Command / doc |
|-------------------|---------------|
| Connect AI in editor | [MCP.md](MCP.md), [FOR_AI_MODELS.md](FOR_AI_MODELS.md) |
| Ingest your own DNA | `agentdrive drive ingest <genome-dir>` |
| Fabric patterns | `agentdrive patterns list` |
| Ship workflow | `agentdrive sprint ship` |
| Maintenance cycle | `agentdrive dream run --dry-run` |
| Full AD-Grid world | [AD_GRID_JOIN.md](AD_GRID_JOIN.md) |

Do not start with AD-Grid unless you have completed the golden path. The grid assumes a seeded drive and MCP literacy.

---

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| `doctor` shows 0 genomes | `agentdrive reconcile seed-experience-v3` then re-run doctor |
| `mcp doctor` fails | `agentdrive mcp install` |
| `think` errors on provider | `agentdrive provider set <name>` or `agentdrive setup ai` |
| Empty `drive query` | Run `python3 examples/01_hello_drive.py` to ingest demo genome |
| Lost in CLI surface | `agentdrive commands search <keyword>` |

---

## CI / smoke reference

`scripts/install_smoke.sh` validates install + doctor + MCP + dream dry-run + hello example. The golden path extends that with think, learnings, and query verification:

```bash
agentdrive golden-path run --dry-run
```