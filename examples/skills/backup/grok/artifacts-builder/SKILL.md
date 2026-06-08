---
name: grok-artifacts-builder
description: >
  Build self-contained web artifacts (HTML/Tailwind or React) — prototypes, dashboards, interactive UIs with accessibility and dark mode. Hive copy.
category: backup
role: shared
source: grok-backup
backup_of: artifacts-builder
backup_path: ~/.grok/skills/artifacts-builder/SKILL.md
tags: [grok, artifacts, html, prototype, dashboard]
when_to_call: interactive prototype, dashboard, or live-preview web artifact
---

# Grok backup — artifacts-builder

This skill mirrors the operator's Grok harness skill so **pawn subagents** and other
AgentDrive-connected agents can load the same playbook from the shared hive bench.

**Original path:** `~/.grok/skills/artifacts-builder/SKILL.md`

---

# Artifacts Builder Skill (Claude Artifacts + Design inspired)

Teaches building high-quality, self-contained or componentized frontend artifacts.

## Core Principles
- **Self-contained for preview**: For live canvas/iframe (Grok Brush style): full HTML + Tailwind CDN + minimal JS. Fully interactive, sandbox-safe. Include the DESIGN tokens as inline CSS vars.
- **Clean for handoff**: For code export: proper React/TSX + Tailwind (or shadcn/ui patterns), TypeScript, hooks, composition, accessibility (ARIA, keyboard, contrast), responsive (mobile-first + breakpoints), dark mode (class or media), performance (lazy, memo where sensible).
- **No slop**: Follow frontend-design aesthetics strictly. Use tokens from DESIGN.md or system.
- **Architecture**:
  - Small, composable components.
  - Clear prop interfaces.
  - State management appropriate to scope (useState, context, or minimal external).
  - No unnecessary abstractions.
  - Proper error boundaries/states if complex.
- **Interactive & Live**: Support real interactions (forms, modals, animations via CSS/Framer, data viz). For Artifacts: make "AI-powered" if possible (e.g., embed simple logic or note for Grok integration).
- **Iteration friendly**: Generate with clear sections/comments so easy to patch. Support "update this part only".

## Output Formats
- **Preview Artifact (HTML)**: <!DOCTYPE html> ... with Tailwind play CDN. Inject current DESIGN tokens as :root vars. Make beautiful and functional out of box.
- **Code Artifact (React/TSX)**: Folder-like structure or single file + imports. Include types, stories or examples if fitting.
- Always provide both if possible, or toggleable.
- Include "Preview / Code" guidance in comments.
- Exports: standalone HTML (runnable), ZIP with assets, clean source for Claude Code / Git handoff.

## Process
1. Read DESIGN.md / tokens / existing components first (use design-system skill).
2. Apply frontend-design aesthetics.
3. Build architecture per this skill.
4. Make live/preview-ready.
5. For updates: reference previous artifact, apply precise diffs/patches.
6. Suggest or implement DESIGN.md updates if new patterns/tokens added.

## Specific Patterns (Claude community + best practices)
- React + Tailwind + shadcn/ui or headless (Radix-like): data-slot, variants, composition over inheritance.
- Responsive: mobile first, clamp() for fluid, proper breakpoints.
- Dark mode: CSS vars + class strategy.
- Motion: CSS transitions first, framer-motion for complex/React.
- Accessibility: semantic HTML, ARIA, focus management, reduced motion respect.
- State: derive where possible; lift only when needed.
- For prototypes: simulate data, make forms work, add micro-interactions.
- Avoid: over-nesting, magic strings (use tokens), layout thrashing.

## Grok Brush / Live Canvas Integration
- Generate HTML that works perfectly in the app's sandboxed iframe.
- Support inline "comments": structure HTML with data-commentable or IDs so app can overlay click-to-refine.
- Dynamic params: expose CSS vars or data-attrs for sliders (spacing-multiplier, accent-hue) that the app can control live.
- Versions & persistence: output with metadata for the app's version system.
- AI-powered: If embedding logic, note how to connect to Grok (e.g., simple fetch to local endpoint or comment for MCP).

## Examples of Use
- "Build a dashboard artifact using current DESIGN.md, React + shadcn patterns, live sortable table + charts."
- "Create self-contained HTML prototype for onboarding flow, with the brand tokens, interactive steps, and micro-animations."
- In iteration: "Update the hero in the previous artifact: make button use primary token, add subtle hover lift."

## With Other Tools
- Use image_gen/imagine for hero visuals or references inside artifacts.
- Canva MCP for further polish/export.
- Terminal: npm run dev/build to test React artifacts.
- For handoff: produce bundle ready for Claude Code style or git.

This replicates Claude's Artifacts (live preview + code) + strong component architecture skills. Always compose with frontend-design (aesthetics) and design-system (tokens) for Claude-Design level results.

Load when generating any web UI artifact or prototype.
