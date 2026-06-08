---
name: grok-universal-brush
description: "Backup of Grok harness skill `universal-brush` for swarm pawns and hive bench."
source: grok-backup
role: shared
category: backup
tags: [grok, backup, hive, pawn]
backup_of: universal-brush
backup_path: ~/.grok/skills/universal-brush/SKILL.md
when_to_call: when a pawn or connected agent needs the same workflow Grok uses for universal-brush
---

# Grok backup — universal-brush

This skill mirrors the operator's Grok harness skill so **pawn subagents** and other
AgentDrive-connected agents can load the same playbook from the shared hive bench.

**Original path:** `~/.grok/skills/universal-brush/SKILL.md`

---

# Universal Brush skill (early integration)

Starts the local Next.js dev server for the Universal Brush project (in Projects/universal-brush) if needed and/or proxies a design request.

## Usage
- `/universal-brush` or `/brush "create a landing page for my SaaS, dark, cyan accents"`
- The skill will attempt to launch `npm run dev` in the project (background) and open the URL, or use MCP tools (universal-brush__generate_design etc.) if registered for direct agentic control.
- Supports Claude Design-like flows: clarifying questions, dynamic per-project sliders, rich imports (images/web/docs), DESIGN systems, exports/handoff.

See the project README (in Projects/universal-brush) and DESIGN_PRD.md for full details, MCP registration, and how it integrates with the replicated Claude frontend skills (design-system, artifacts-builder, frontend-design).

Usage example: cd Projects/universal-brush ; npm run dev

The project was renamed from Grok Brush; this skill updated accordingly. See DESIGN_PRD.md in the project for the full history and Claude skills replication details.

## Deeper Grok Build Integration (OpenClaw / Hermes style)

When the MCP is registered via the project's .grok/config.toml (or a matching global entry):

- Prefer direct tool calls when available: search_tool for universal-brush tools, then use_tool("universal-brush__generate_design", {...}).
- This gives the agent a true tool surface (generate, ingest DESIGN, tweak kit, export) without necessarily opening the browser.
- The web UI (chat + heroic canvas + live tweaks + comment mode) is still the premium human experience.
- Auth via UNIVERSAL_BRUSH_API_KEY passed through the MCP header config (secrets isolated, like OpenClaw auth-profiles + Ren vault discipline).
- Always compose: /frontend-design + /design-system + /artifacts-builder + this.

Fallback: if MCP tools not present in the session, the classic behavior (launch dev server in background + open http://localhost:3000) still applies.

To activate deeper mode: start the brush server first (`npm run dev` in its dir with keys in env), then use Grok Build from a cwd inside or under the project.
