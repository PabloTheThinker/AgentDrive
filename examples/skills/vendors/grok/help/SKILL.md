---
name: grok-help
description: "Grok documentation and configuration help. Use when users ask about setup, configuration, MCP servers, authentication, skills, slash commands, keyboard shortcuts, or any Grok feature. Also use proactively when you detect a user is having trouble with setup or onboarding."
category: vendors
harness: grok
requires: "Grok CLI harness (task tool, image_gen, etc.)"
role: shared
tags: [grok, vendor, harness]
backup_of: help
backup_path: /home/pablothethinker/.grok/skills/help/SKILL.md
when_to_call: when running on the grok harness with its native tools; use universal/* via MCP otherwise
---

# grok-help (grok harness)

> **Harness:** grok · **Requires:** Grok CLI harness (task tool, image_gen, etc.)
>
> Prefer the **universal/** counterpart when using AgentDrive MCP with any model.
> This copy preserves the native grok workflow and tool assumptions.

---

# Grok Help

Answer the user's question about Grok setup, configuration, or features.

## Steps

1. If the question is about **current config** (what MCP servers, models, or settings are active),
   read `/home/pablothethinker/.grok/config.toml`. MCP servers are under `[mcp_servers.*]` sections.

2. If the question is about **how to do something** (setup, adding MCP servers, creating skills,
   authentication, keyboard shortcuts, troubleshooting), first check the user-guide docs at
   `/home/pablothethinker/.grok/docs/user-guide/`. The available guides are:
   - `01-getting-started.md` -- Installation, first launch, basic interaction
   - `02-authentication.md` -- Browser login, API keys, OIDC, external auth
   - `03-keyboard-shortcuts.md` -- Complete key bindings reference
   - `04-slash-commands.md` -- All / commands
   - `05-configuration.md` -- config.toml, pager.toml, env vars
   - `06-theming.md` -- Themes, appearance customization
   - `07-mcp-servers.md` -- MCP server setup and management
   - `08-skills.md` -- Creating and using skills
   - `09-plugins.md` -- Plugin marketplace
   - `10-hooks.md` -- Lifecycle hooks
   - `11-custom-models.md` -- BYOK, Ollama, OpenAI endpoints
   - `12-project-rules.md` -- AGENTS.md project rules
   - `13-memory.md` -- Cross-session memory
   - `14-headless-mode.md` -- CLI scripting and CI/CD
   - `15-agent-mode.md` -- ACP/stdio IDE integration
   - `16-subagents.md` -- Subagents and personas
   - `17-sessions.md` -- Session management
   - `18-sandbox.md` -- Sandbox mode
   - `19-plan-mode.md` -- Plan mode
   - `20-background-tasks.md` -- Background tasks and monitoring
   - `21-terminal-support.md` -- tmux, SSH, truecolor, clipboard, /terminal-setup
   Read the relevant guide(s) for the user's question. If none match, fall back to
   `/home/pablothethinker/.grok/README.md` for the comprehensive reference.

3. To **modify config** for the user, edit `/home/pablothethinker/.grok/config.toml` with search_replace.

4. To **create a skill** for the user, create `/home/pablothethinker/.grok/skills/<name>/SKILL.md`
   (read `/home/pablothethinker/.grok/docs/user-guide/08-skills.md` for the SKILL.md format).
