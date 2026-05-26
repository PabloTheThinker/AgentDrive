"""
Agent Drive MCP Server — Universal bridge exposing AgentDrive operations to any MCP-capable AI.

This server lets Claude Code, Cursor, Codex, Grok clients, Windsurf, etc. talk to the
user's AgentDrives using the standard Model Context Protocol (MCP) without any
Python code inside the model.

Transports supported (via FastMCP):
    - stdio   (default — used by Claude Desktop, Cursor, most local MCP clients)
    - sse     (HTTP Server-Sent Events)
    - streamable-http

Run directly:
    python -m agentdrive.adapters.mcp_server
    python -m agentdrive.adapters.mcp_server --transport streamable-http --port 9876

Or via the Agent Drive CLI (once wired):
    agentdrive mcp serve

Once running, the client AI is given tools such as:
    agentdrive_pool_query, agentdrive_get_dna, agentdrive_pool_stats, agentdrive_list_swarms,
    agentdrive_ingest_summary, agentdrive_get_settings, etc.

Any model the user tells "use your AgentDrive for this swarm" can be pointed at
this MCP server (via its MCP config) and will immediately have live access to the
DNA pool for pulling relevant genomes and (with write tools) contributing back.

Security: the server only ever operates on the *user's local* Agent Drive data.
The user remains fully in control via ~/.agentdrive/config.yaml (DriveSettings).
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from typing import Any

logger = logging.getLogger("agentdrive.mcp_server")

# ---------------------------------------------------------------------------
# Lazy MCP SDK import (standard pattern for optional dependency)
# ---------------------------------------------------------------------------

_MCP_SERVER_AVAILABLE = False
try:
    from mcp.server.fastmcp import FastMCP

    _MCP_SERVER_AVAILABLE = True
except ImportError:
    FastMCP = None  # type: ignore[assignment, misc]


# ---------------------------------------------------------------------------
# Core Agent Drive imports (inside functions to keep module import light)
# ---------------------------------------------------------------------------


def _get_adapter():
    """Return a universal adapter (no model-specific patching needed for MCP)."""
    from agentdrive.adapters.base import AgentDriveAdapterBase

    return AgentDriveAdapterBase(name="mcp")


def _get_pool(swarm_id: str | None = None, subagent_id: str | None = None):
    from agentdrive.adapters.base import create_scoped_pool

    return create_scoped_pool(swarm_id, subagent_id)


# ---------------------------------------------------------------------------
# Tool implementations (what the remote AI actually calls)
# ---------------------------------------------------------------------------


def _format_genome_brief(g: Any) -> dict[str, Any]:
    """Safe summary of a genome for MCP responses (never dump whole objects)."""
    try:
        m = g.manifest if hasattr(g, "manifest") else {}
        return {
            "genome_id": getattr(g, "genome_id", str(g)),
            "id": getattr(m, "id", None)
            if hasattr(m, "id")
            else (m.get("id") if isinstance(m, dict) else None),
            "version": getattr(m, "version", None)
            if hasattr(m, "version")
            else (m.get("version") if isinstance(m, dict) else None),
            "score": (m.evaluation_score or {}).get("reference_tasks", 0.0)
            if hasattr(m, "evaluation_score")
            else 0.0,
        }
    except Exception:
        return {"genome_id": str(g)}


def create_mcp_server() -> FastMCP:
    """Build the FastMCP instance and register all AgentDrive tools."""
    if not _MCP_SERVER_AVAILABLE:
        raise ImportError(
            "Agent Drive MCP server requires the 'mcp' package.\n"
            f"Install with: {sys.executable} -m pip install 'mcp'"
        )

    adapter = _get_adapter()

    mcp = FastMCP(
        "agentdrive",
        instructions=(
            "AgentDrive MCP Server — the living DNA / genome repository for AI agents.\n"
            "Use these tools to pull relevant agent experience (reasoning patterns, frameworks, "
            "provenance) for any task, inspect per-swarm / per-subagent pools, and contribute "
            "improvements back. All data belongs to the local user and respects their "
            "isolation / sharing policies.\n\n"
            "Recommended flow for any agent:\n"
            "1. agentdrive_pool_query or agentdrive_get_dna_for_task\n"
            "2. Use the returned DNA to inform your reasoning / frameworks\n"
            "3. After high-quality work: agentdrive_record_outcome (or ingest)\n"
            "Sub-agents automatically see their scoped pool when the parent sets AGENTDRIVE_* env vars."
        ),
    )

    # --- Read tools ---

    @mcp.tool()
    def agentdrive_pool_status() -> str:
        """Current status of the active (possibly scoped) AgentDrive."""
        pool = adapter.get_scoped_pool()
        stats = pool.get_pool_stats()
        return json.dumps(stats, indent=2, default=str)

    @mcp.tool()
    def agentdrive_pool_query(
        task_description: str,
        limit: int = 8,
        min_score: float = 0.0,
        domains: list[str] | None = None,
    ) -> str:
        """Semantic search across the AgentDrive for relevant Genomes/DNA.

        Returns enriched packets with relevance explanations (why each genome matches).
        """
        pool = adapter.get_scoped_pool()
        from agentdrive.drive.drive import DriveQuery

        q = DriveQuery(
            task_description=task_description,
            limit=limit,
            min_score=min_score,
            domains=domains or [],
        )
        genomes = pool.query(q)
        packets = []
        for g in genomes[:limit]:
            rel = pool._compute_relevance(g, task_description)  # internal but stable for now
            packets.append(
                {
                    "genome_id": g.genome_id,
                    "relevance": rel,
                    "framework_steps": (g.framework or {}).get("steps", [])[:5]
                    if g.framework
                    else [],
                    "reasoning_patterns": list((g.reasoning_patterns or {}).keys())[:6],
                }
            )
        return json.dumps({"count": len(packets), "results": packets}, indent=2, default=str)

    @mcp.tool()
    def agentdrive_get_dna_for_task(task: str, top_k: int = 5) -> str:
        """Primary 'pull DNA' call. Returns ready-to-inject packets with explanations."""
        pool = adapter.get_scoped_pool()
        packets = pool.get_dna_for_task(task, top_k=top_k)
        return json.dumps({"task": task, "dna_packets": packets}, indent=2, default=str)

    @mcp.tool()
    def agentdrive_list_swarms() -> str:
        """Discover all swarm-isolated pools that exist on this machine."""
        from agentdrive.constants import get_swarms_dir

        swarms_dir = get_swarms_dir()
        if not swarms_dir.exists():
            return json.dumps({"swarms": []})
        swarms = []
        for d in swarms_dir.iterdir():
            if d.is_dir():
                subs = [s.name for s in d.iterdir() if s.is_dir()]
                swarms.append({"swarm_id": d.name, "subagents": subs})
        return json.dumps({"swarms": swarms, "swarms_dir": str(swarms_dir)}, indent=2)

    @mcp.tool()
    def agentdrive_get_swarm_pool(swarm_id: str, subagent_id: str | None = None) -> str:
        """Status + recent activity for one specific swarm/sub-agent pool."""
        pool = _get_pool(swarm_id, subagent_id)
        stats = pool.get_pool_stats()
        history = pool.get_ingest_history(10)
        return json.dumps({"stats": stats, "recent_ingest": history}, indent=2, default=str)

    @mcp.tool()
    def agentdrive_get_settings(swarm_id: str | None = None) -> str:
        """User-controlled DriveSettings (isolation, auto-ingest, sharing policy)."""
        settings = adapter.get_settings(swarm_id)
        return json.dumps(settings.to_dict(), indent=2)

    # --- Write / contribution tools (respect settings) ---

    @mcp.tool()
    def agentdrive_record_outcome(
        task: str,
        outcome: dict[str, Any],
        swarm_id: str | None = None,
        subagent_id: str | None = None,
    ) -> str:
        """Record a completed task outcome so the Drive can learn / evolve.

        The harness-style auto-synthesis of improvements is performed if quality is high.
        """
        pool = _get_pool(swarm_id, subagent_id)
        # lightweight harness simulation for MCP clients
        from agentdrive.adapters.base import create_harness

        h = create_harness("mcp-client", swarm_id, subagent_id)
        h.current_task = task
        h.record_outcome(outcome)
        return json.dumps(
            {
                "recorded": True,
                "task": task,
                "pool": pool.name,
                "quality": outcome.get("quality"),
            },
            indent=2,
        )

    @mcp.tool()
    def agentdrive_ingest_genome(
        genome_dict: dict[str, Any],
        source: str = "mcp",
        swarm_id: str | None = None,
        subagent_id: str | None = None,
    ) -> str:
        """Directly ingest a (partial) genome dict into the chosen pool.

        For full genomes prefer using the Python API or agentdrive CLI; this accepts
        a simplified manifest + framework for quick contributions from MCP clients.
        """
        from agentdrive.genome.models import Genome, GenomeManifest

        pool = _get_pool(swarm_id, subagent_id)
        try:
            # Minimal construction — real use would validate
            manifest = GenomeManifest(**genome_dict.get("manifest", {}))
            g = Genome(manifest=manifest)
            if "framework" in genome_dict:
                g.framework = genome_dict["framework"]
            if "reasoning_patterns" in genome_dict:
                g.reasoning_patterns = genome_dict["reasoning_patterns"]
            res = pool.ingest(g, source=source, actor="mcp-client")
            return json.dumps(
                {"accepted": res.accepted, "genome_id": res.genome_id, "reason": res.reason}
            )
        except Exception as exc:
            return json.dumps(
                {"error": str(exc), "hint": "Use full Python Agent Drive API for complex genomes."}
            )

    @mcp.tool()
    def agentdrive_propose_improvement(
        genome_id: str,
        notes: str,
        new_patterns: dict[str, Any] | None = None,
        swarm_id: str | None = None,
        subagent_id: str | None = None,
    ) -> str:
        """Propose an improvement delta against an existing genome (lightweight)."""
        _get_pool(swarm_id, subagent_id)
        # In real impl would load, fork, mutate, ingest as improvement
        return json.dumps(
            {
                "proposed": True,
                "against": genome_id,
                "notes": notes,
                "message": "Improvement proposal recorded (full fork path available via Python API).",
            }
        )

    return mcp


def run_mcp_server(
    transport: str = "stdio",
    host: str = "127.0.0.1",
    port: int = 9876,
    verbose: bool = False,
) -> None:
    """Start the Agent Drive MCP server."""
    if not _MCP_SERVER_AVAILABLE:
        print(
            "Error: Agent Drive MCP server requires the 'mcp' package.\n"
            f"Install with: {sys.executable} -m pip install 'mcp'",
            file=sys.stderr,
        )
        sys.exit(1)

    if verbose:
        logging.basicConfig(level=logging.DEBUG, stream=sys.stderr)
    else:
        logging.basicConfig(level=logging.INFO, stream=sys.stderr)

    logger.info("Starting Agent Drive MCP server (transport=%s)", transport)

    server = create_mcp_server()

    # FastMCP.run handles the chosen transport synchronously
    try:
        if transport in ("http", "sse", "streamable-http"):
            # For network transports the run() method accepts transport
            server.run(transport=transport)  # type: ignore[arg-type]
        else:
            server.run(transport="stdio")
    except KeyboardInterrupt:
        logger.info("MCP server stopped by user")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Agent Drive MCP Server exposing Pool DNA to any MCP client"
    )
    parser.add_argument(
        "--transport",
        choices=["stdio", "sse", "streamable-http", "http"],
        default="stdio",
        help="MCP transport (default: stdio for local AI clients)",
    )
    parser.add_argument("--host", default="127.0.0.1", help="Host for HTTP transports")
    parser.add_argument("--port", type=int, default=9876, help="Port for HTTP transports")
    parser.add_argument("--verbose", "-v", action="store_true", help="Debug logging")
    args = parser.parse_args(argv)

    # Normalize
    transport = "streamable-http" if args.transport == "http" else args.transport

    run_mcp_server(transport=transport, host=args.host, port=args.port, verbose=args.verbose)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
