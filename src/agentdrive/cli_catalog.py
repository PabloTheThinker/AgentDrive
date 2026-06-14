"""
Discoverable CLI command catalog for AgentDrive.

Single source for ``agentdrive commands``, help epilog, and ops-registry alignment.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable


@dataclass(frozen=True)
class CatalogEntry:
    """One user-facing CLI command path."""

    command: str
    summary: str
    category: str
    operation: str | None = None
    read_only: bool | None = None


# Category display order (interfaces first, discovery last).
CATEGORY_ORDER: tuple[str, ...] = (
    "interfaces",
    "setup",
    "drive",
    "synthesis",
    "patterns",
    "learnings",
    "harness",
    "experience",
    "reconcile",
    "sprint",
    "dream",
    "eval",
    "mcp",
    "mission_control",
    "genomes",
    "config",
    "providers",
    "trust",
    "ops",
    "maintenance",
    "golden_path",
    "discovery",
)

CATEGORY_LABELS: dict[str, str] = {
    "interfaces": "Interfaces (TUI, web, grid)",
    "setup": "Setup & health",
    "drive": "Drive (persistent DNA pool)",
    "synthesis": "Synthesis",
    "patterns": "Patterns (Fabric-style)",
    "learnings": "Learnings (gstack JSONL)",
    "harness": "Harness composition",
    "experience": "Experience Graph",
    "reconcile": "Reconciliation",
    "sprint": "Sprint chains",
    "dream": "Dream cycle",
    "eval": "Evaluation",
    "mcp": "MCP (AI CLI integration)",
    "mission_control": "Mission Control",
    "genomes": "Genomes",
    "config": "Configuration",
    "providers": "Providers & models",
    "trust": "Trust & federation",
    "ops": "Operations registry",
    "maintenance": "Self-management",
    "discovery": "Discovery",
    "golden_path": "Golden path (first-run)",
}


CATALOG: tuple[CatalogEntry, ...] = (
    # interfaces
    CatalogEntry("mission", "Real-time Mission Control Tower (loop + fabric)", "interfaces"),
    CatalogEntry("board", "Mission Kanban Board (web UI)", "interfaces"),
    CatalogEntry("kanban", "Alias for board", "interfaces"),
    CatalogEntry("tui", "Professional TUI (genomes, chat, pool, MC view)", "interfaces"),
    CatalogEntry("repl", "Operator REPL (dispatch any subcommand interactively)", "interfaces"),
    CatalogEntry("session events", "List typed events.jsonl for a chat session", "interfaces"),
    CatalogEntry("session replay", "Replay session events as numbered timeline", "interfaces"),
    CatalogEntry("session panel", "Rich replay panel with type histogram", "interfaces"),
    CatalogEntry("grid", "AD-Grid persistent intelligence substrate", "interfaces"),
    # setup
    CatalogEntry("setup", "Interactive setup wizard", "setup"),
    CatalogEntry("onboard", "Lightweight first-run consent flow", "setup"),
    CatalogEntry("doctor", "Installation and subsystem health check", "setup", "doctor", True),
    CatalogEntry("doctor --verbose", "Extended diagnostics panel", "setup", "doctor_verbose", True),
    CatalogEntry("deps check", "Declared vs installed dependency report", "setup"),
    CatalogEntry("scan", "Scan runs/trajectories for candidate genomes", "setup"),
    # drive
    CatalogEntry("drive status", "Drive status and recent activity", "drive", "pool_status", True),
    CatalogEntry("drive stats", "Detailed pool and registry statistics", "drive", "pool_stats", True),
    CatalogEntry("drive query", "Semantic genome search for a task", "drive", "pool_query", True),
    CatalogEntry("drive ingest", "Ingest a genome directory into the Drive", "drive", "ingest_genome", False),
    CatalogEntry("pool", "Alias for drive (same subcommands)", "drive"),
    # synthesis
    CatalogEntry("think", "Cited Drive.think synthesis with gap analysis", "synthesis", "think", True),
    # patterns
    CatalogEntry("patterns list", "List Fabric-style pattern catalog", "patterns", "patterns_list", True),
    CatalogEntry("patterns show", "Show one pattern metadata and system.md", "patterns", "patterns_show", True),
    CatalogEntry("patterns apply", "Compose pattern prompt with {{input}}", "patterns", "patterns_apply", True),
    CatalogEntry(
        "patterns import-fabric",
        "Import Fabric patterns into ~/.agentdrive/patterns",
        "patterns",
        "patterns_import_fabric",
        False,
    ),
    # learnings
    CatalogEntry("learnings list", "Recent operational learnings for project slug", "learnings", "learnings_list", True),
    CatalogEntry("learnings log", "Append one learning entry", "learnings", "learnings_log", False),
    CatalogEntry("learnings search", "Token search over learnings key/insight", "learnings", None, True),
    # harness
    CatalogEntry("harness compose", "Compose harness prompt (DNA + learnings + Fabric)", "harness", "harness_compose", True),
    # experience
    CatalogEntry(
        "graph context-pack",
        "Dense Experience Graph context pack for briefings",
        "experience",
        "experience_graph_context_pack",
        True,
    ),
    CatalogEntry(
        "graph record",
        "Record structural reasoning into Experience Graph",
        "experience",
        "experience_graph_record_reasoning",
        False,
    ),
    CatalogEntry(
        "graph suggest",
        "Schema and examples for reasoning traces",
        "experience",
        "experience_graph_suggest_reasoning",
        True,
    ),
    CatalogEntry("experience", "Alias for graph (Experience Graph commands)", "experience"),
    # reconcile
    CatalogEntry("reconcile run", "Single reconciliation pass over local Drive", "reconcile", "reconcile_scan", False),
    CatalogEntry("reconcile status", "Persisted reconciliation state", "reconcile", "reconcile_status", True),
    CatalogEntry(
        "reconcile seed-experience-v3",
        "First-run recovery: experience layer v3 seed + KG bootstrap",
        "reconcile",
        "reconcile_seed",
        False,
    ),
    # sprint
    CatalogEntry("sprint ship", "Reconcile → test → think_gaps ship chain", "sprint", "sprint_ship", False),
    CatalogEntry("sprint status", "Pending sprint checkpoints", "sprint", "sprint_status", True),
    CatalogEntry("sprint ack", "Acknowledge a sprint checkpoint", "sprint"),
    # dream
    CatalogEntry("dream run", "Phased dream maintenance cycle", "dream", "dream_run", False),
    CatalogEntry("dream status", "Dream lock and last audit entry", "dream", "dream_status", True),
    CatalogEntry("dream phases", "List dream cycle phases", "dream"),
    # eval
    CatalogEntry("eval replay", "Re-score stored research artifact with harness", "eval"),
    # mcp
    CatalogEntry("mcp serve", "Start MCP server (stdio for AI CLIs)", "mcp"),
    CatalogEntry("mcp config", "Print MCP config snippets for Grok/Cursor/Claude", "mcp"),
    CatalogEntry("mcp install", "pip install [mcp] and write client configs", "mcp"),
    CatalogEntry("mcp doctor", "Verify MCP package, launcher, tools", "mcp"),
    CatalogEntry("mcp tools", "List MCP tools exposed by server", "mcp"),
    # mission_control
    CatalogEntry("cap mint-mission", "Mint Mission Control mutating-command cap", "mission_control", "cap_mint_mission", False),
    # genomes
    CatalogEntry("genomes list", "List registered genomes", "genomes"),
    CatalogEntry("genomes info", "Show one genome by ID", "genomes"),
    CatalogEntry("genomes search", "Search genomes by task description", "genomes"),
    # skills
    CatalogEntry("skills list", "List SKILL.md capabilities", "discovery"),
    CatalogEntry("skills show", "Show one skill metadata and body", "discovery"),
    CatalogEntry("skills run", "Run a skill (same path as /skill in chat)", "discovery"),
    CatalogEntry("skills review", "Review inherited skills using usage evidence", "discovery"),
    CatalogEntry("skills promote", "Promote a proven inherited skill", "discovery"),
    CatalogEntry("skills prune", "Disable a weak inherited skill without deleting it", "discovery"),
    CatalogEntry("skills dna", "Ingest an inherited/promoted skill into the DNA pool", "discovery"),
    CatalogEntry("skills init", "Scaffold a new SKILL.md under ~/.agentdrive/skills", "discovery"),
    # config
    CatalogEntry("config show", "Show configuration", "config"),
    CatalogEntry("config get", "Get one config key", "config"),
    CatalogEntry("config set", "Set one config key", "config"),
    CatalogEntry("config edit", "Open config in editor", "config"),
    CatalogEntry("workers", "List worker adapters", "config"),
    # providers
    CatalogEntry("provider list", "List AI model providers", "providers"),
    CatalogEntry("provider set", "Configure provider and default model", "providers"),
    CatalogEntry("provider key", "Set API key for a provider", "providers"),
    CatalogEntry("model list", "Active model and available models", "providers"),
    CatalogEntry("model set", "Switch active model", "providers"),
    CatalogEntry("models list", "Local LLM backends and reachability", "providers"),
    # trust
    CatalogEntry("quarantine list", "List quarantine entries", "trust"),
    CatalogEntry("quarantine show", "Show one quarantine entry", "trust"),
    CatalogEntry("quarantine validate", "Run validation rules on entry", "trust"),
    CatalogEntry("quarantine approve", "Approve and release into Drive", "trust"),
    CatalogEntry("quarantine reject", "Reject entry permanently", "trust"),
    CatalogEntry("quarantine hold", "Move entry to indefinite hold", "trust"),
    CatalogEntry("peers list", "List federated peers", "trust"),
    CatalogEntry("peers add", "Register a peer", "trust"),
    CatalogEntry("peers remove", "Unregister a peer", "trust"),
    CatalogEntry("peers trust", "Change peer trust level", "trust"),
    CatalogEntry("peers sync", "Pull genomes from peer into quarantine", "trust"),
    # ops
    CatalogEntry("ops list", "Table of contract-first operations", "ops"),
    CatalogEntry("ops describe", "JSON detail for one operation", "ops"),
    CatalogEntry("ops run", "Execute operation with key=value kwargs", "ops"),
    CatalogEntry("ops export", "Export operations manifest JSON", "ops"),
    # maintenance
    CatalogEntry("update", "Update AgentDrive from GitHub", "maintenance"),
    CatalogEntry("reinstall", "Reinstall AgentDrive from GitHub", "maintenance"),
    CatalogEntry("clean", "Clean cache and data (keeps config)", "maintenance"),
    CatalogEntry("uninstall", "Uninstall AgentDrive package", "maintenance"),
    CatalogEntry("demo-swarm", "Scripted sub-agent tree demo", "maintenance"),
    # golden_path
    CatalogEntry("golden-path steps", "Show numbered first-run golden path", "golden_path"),
    CatalogEntry("golden-path verify", "Check golden-path step completion", "golden_path"),
    CatalogEntry("golden-path run", "Execute golden-path walkthrough", "golden_path"),
    # discovery
    CatalogEntry("commands list", "All CLI commands by category", "discovery"),
    CatalogEntry("commands tree", "Indented command tree", "discovery"),
    CatalogEntry("commands search", "Search commands by keyword", "discovery"),
)


def catalog_by_category() -> dict[str, list[CatalogEntry]]:
    """Group catalog entries by category in display order."""
    grouped: dict[str, list[CatalogEntry]] = {cat: [] for cat in CATEGORY_ORDER}
    for entry in CATALOG:
        grouped.setdefault(entry.category, []).append(entry)
    return {cat: grouped[cat] for cat in CATEGORY_ORDER if grouped.get(cat)}


def search_catalog(query: str) -> list[CatalogEntry]:
    """Case-insensitive token search over command path and summary."""
    tokens = [t.lower() for t in query.split() if t.strip()]
    if not tokens:
        return list(CATALOG)
    hits: list[CatalogEntry] = []
    for entry in CATALOG:
        hay = f"{entry.command} {entry.summary} {entry.category} {entry.operation or ''}".lower()
        if all(tok in hay for tok in tokens):
            hits.append(entry)
    return hits


def format_epilog() -> str:
    """Compact epilog for ``agentdrive --help``."""
    lines = [
        "Quick start:",
        "  agentdrive                          Guided onboarding + TUI",
        "  agentdrive setup                    Full setup wizard",
        "  agentdrive doctor                   Health check",
        "",
        "Core workflows:",
        "  agentdrive think \"question\"         Cited synthesis + gaps",
        "  agentdrive drive query \"task\"       Semantic genome search",
        "  agentdrive learnings log --key K --insight \"...\"",
        "  agentdrive harness compose --task \"...\"",
        "  agentdrive graph context-pack       Experience Graph briefing pack",
        "  agentdrive sprint ship              gstack-style ship chain",
        "  agentdrive dream run                Phased maintenance cycle",
        "  agentdrive mcp install              Wire MCP into Grok/Cursor/Claude",
        "",
        "Golden path (first run):",
        "  agentdrive golden-path steps          Numbered walkthrough",
        "  agentdrive golden-path run            Execute install→think→query chain",
        "  agentdrive golden-path verify         Check what's done",
        "",
        "Discover everything:",
        "  agentdrive commands list              All commands by category",
        "  agentdrive commands search <query>    Find a command",
        "  agentdrive ops list                   Contract-first operations + MCP tools",
        "",
        "Isolated test:",
        "  AGENTDRIVE_HOME=/tmp/test agentdrive doctor",
    ]
    return "\n".join(lines)


def iter_tree_lines() -> Iterable[str]:
    """Yield indented tree lines for ``commands tree``."""
    for category, entries in catalog_by_category().items():
        label = CATEGORY_LABELS.get(category, category)
        yield f"[{label}]"
        for entry in entries:
            op = f"  ({entry.operation})" if entry.operation else ""
            yield f"  agentdrive {entry.command}{op}"
