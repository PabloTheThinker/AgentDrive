# Savant Pool & Swarm Settings — Complete User Reference

All user-controllable behavior for the Savant Pool system lives under the `pool:` section of your Savant configuration (`~/.savant/config.yaml` or `$SAVANT_HOME/config.yaml`).

**Core principle**: The pool starts empty. You (the owner) are the sole authority. Any connected AI (Grok, Claude, Codex, local agents) must respect and can be instructed to read/write these settings on your behalf.

## Configuration Location & Format

File: `~/.savant/config.yaml`

```yaml
pool:
  global:                    # defaults applied to all pools
    isolation_level: subagent
    auto_ingest_on_success: true
    min_quality_for_ingest: 0.75
    sharing_policy: selective
    retention_days: 0
    allow_upward_proposals: true

  swarms:                    # per-swarm overrides (keyed by swarm_id)
    "mission-payments-20260523":
      isolation_level: swarm
      sharing_policy: read
      min_quality_for_ingest: 0.85

  # Future: per-subagent overrides under swarms.<id>.subagents.<sub-id>
```

Changes are persisted atomically. Use the CLI, TUI, or Python API.

## PoolSettings Dataclass (Source of Truth)

Defined in `src/savant/pool/settings.py`:

| Field                    | Type                  | Default     | Description |
|--------------------------|-----------------------|-------------|-------------|
| `isolation_level`        | "none" \| "swarm" \| "subagent" | `"subagent"` | How isolated each sub-agent’s pool is from siblings and parent. |
| `auto_ingest_on_success` | bool                  | `true`      | Automatically accept high-quality outcomes into the pool via harness or scanners. |
| `min_quality_for_ingest` | float (0–1)           | `0.75`      | Minimum self-reported or evaluated quality required for auto-ingest / auto-delta. |
| `sharing_policy`         | "none" \| "read" \| "selective" \| "full" | `"selective"` | What other pools in the same swarm/family may do with this pool’s DNA. |
| `retention_days`         | int                   | `0`         | Days to keep old genomes (0 = forever). Pruning is a future background job. |
| `allow_upward_proposals` | bool                  | `true`      | Sub-agents may propose improvements back to parent/family pools. |

## isolation_level Explained

- **`subagent`** (recommended default): Every spawned child gets a completely private pool. No automatic cross-talk. Maximum sovereignty and safety.
- **`swarm`**: All sub-agents sharing the same `swarm_id` may read (and selectively write) each other’s DNA according to the active `sharing_policy`.
- **`none`**: Everything collapses to a single global pool. Maximum knowledge sharing, minimum isolation. Use only when you explicitly want one big brain.

You can set a global default and then override per `swarm_id` for fine-grained control (e.g., one high-stakes swarm stays fully isolated while exploratory swarms share freely).

## sharing_policy Explained

- **`none`**: This pool’s DNA is invisible to everyone else.
- **`read`**: Others may query this pool but may not propose changes into it.
- **`selective`** (default): Others may read; proposals are accepted only after quality gates or explicit user/AI approval.
- **`full`**: Any qualified member of the swarm/family may both read and directly ingest improvements.

Combined with `allow_upward_proposals`, this gives precise control over the direction and volume of knowledge flow.

## Managing Settings

### Via CLI (`savant config`)

```bash
# View everything
savant config show

# Read a specific value
savant config get pool.global.isolation_level

# Set (creates the section if needed)
savant config set pool.global.isolation_level subagent
savant config set pool.global.sharing_policy selective
savant config set pool.swarms.my-mission.isolation_level swarm

# Edit the raw file in $EDITOR
savant config edit
```

### Via Python API (agents or scripts)

```python
from savant.pool.settings import (
    get_pool_settings_manager,
    PoolSettings,
    get_effective_pool_settings,
)

mgr = get_pool_settings_manager()

# Global
global_settings = mgr.get_global()
mgr.set_global(PoolSettings(isolation_level="subagent", sharing_policy="selective"))

# Per-swarm
mgr.set_for_swarm("mission-xyz", PoolSettings(isolation_level="swarm", allow_upward_proposals=True))

# Effective for a running sub-agent
effective = get_effective_pool_settings(swarm_id="mission-xyz", subagent_id="worker-7")
print(effective)
```

### Via TUI

Launch `savant tui`, navigate to the Pool view, select “pool settings”. Interactive editor for global and per-swarm values with live preview of effective policy.

### Via Natural Language (Any Connected AI)

Give the AI this instruction (or let it read the manager’s `as_user_instructions()`):

> “You are participating in the user’s Savant Pool system. All settings live in the user’s `~/.savant/config.yaml` under the `pool:` section. The user is sovereign. If the user tells you to change isolation_level, auto_ingest_on_success, sharing_policy, min_quality_for_ingest, retention, or allow_upward_proposals for the global pool or for a specific swarm_id, you MUST use the Savant Python API (`get_pool_settings_manager().set_global()` / `set_for_swarm()`) or the `savant config set` CLI to make the change. Never hard-code or ignore user policy instructions.”

The `PoolSettingsManager.as_user_instructions()` method returns a ready-to-use paragraph for system prompts.

## Per-Swarm & Per-Subagent Granularity

- `pool.global.*` — baseline for everything.
- `pool.swarms.<swarm_id>.*` — overrides for an entire swarm family.
- Future: `pool.swarms.<swarm_id>.subagents.<subagent_id>.*` for individual child tuning.

`get_effective_pool_settings(swarm_id, subagent_id=None)` performs the correct merge (most specific wins).

## Other Related Savant Settings

While not under `pool:`, these affect the overall experience:

In `savant:` top-level:
- `log_level`
- `default_worker`

In `registry:`, `scanners:`, `orchestrator:`, `tui:`, `integration:` — see `savant config show` for the full merged defaults.

`SAVANT_HOME` environment variable (or context override) lets you run completely isolated configurations (useful for testing or multiple personas).

## Persistence & Reload

- Settings are read on every `load_config()` / manager instantiation.
- Changes via `save_config()` invalidate caches.
- Running agents that hold a `PoolSettingsManager` instance should call `load_config(force_reload=True)` or recreate the manager after policy changes if live reactivity is required.

## Safety & Defaults

Sensible, conservative defaults are chosen so a brand-new Savant installation is safe:

- Private per-subagent pools
- Auto-ingest only on clearly successful runs
- Selective sharing (requires explicit policy upgrade)
- Upward proposals allowed (but still gated by quality)

You can lock everything down further (`isolation_level: subagent`, `sharing_policy: none`, `auto_ingest_on_success: false`) with a single config command.

## Example: High-Security Research Swarm

```yaml
pool:
  global:
    isolation_level: subagent
    auto_ingest_on_success: true
    min_quality_for_ingest: 0.80
    sharing_policy: selective
    allow_upward_proposals: true
  swarms:
    "red-team-research-2026":
      isolation_level: swarm
      sharing_policy: read          # read-only lateral sharing inside the red team
      min_quality_for_ingest: 0.90  # higher bar for this sensitive swarm
```

## Example: Exploratory Creative Swarm

```yaml
pool:
  swarms:
    "creative-proto-42":
      isolation_level: none         # full cross-pollination
      sharing_policy: full
      auto_ingest_on_success: true
      min_quality_for_ingest: 0.60  # lower bar to encourage rapid experimentation
```

## Viewing Effective Policy at Runtime

```python
from savant.pool.settings import get_effective_pool_settings
print(get_effective_pool_settings("my-swarm").to_dict())
```

Or from CLI/TUI as shown above.

## Future Enhancements (Roadmap)

- Live policy hot-reload for long-running agents
- Per-subagent overrides in the data model
- Signed / auditable policy changes
- UI wizard in TUI for “Create new swarm with these rules”
- Export/import of pool policies alongside genome bundles

---

**These settings give you complete, granular, persistent control over how your agents and their entire swarms of sub-agents share and evolve intelligence.** Change them at any time — the pools will obey.
