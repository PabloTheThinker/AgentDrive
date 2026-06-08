---
name: grok-design-system
description: "Backup of Grok harness skill `design-system` for swarm pawns and hive bench."
source: grok-backup
role: shared
category: backup
tags: [grok, backup, hive, pawn]
backup_of: design-system
backup_path: ~/.grok/skills/design-system/SKILL.md
when_to_call: when a pawn or connected agent needs the same workflow Grok uses for design-system
---

# Grok backup — design-system

This skill mirrors the operator's Grok harness skill so **pawn subagents** and other
AgentDrive-connected agents can load the same playbook from the shared hive bench.

**Original path:** `~/.grok/skills/design-system/SKILL.md`

---

# Design System Skill (Claude Design / Artifacts inspired)

Guides ingestion of existing design language into a persistent DESIGN.md (or tokens.css / design tokens file) and enforces it in all frontend work.

## When to Use
- User provides codebase, CSS, screenshots, Figma exports, slides, or existing UI.
- Starting a new project that needs brand consistency.
- Updating or refactoring design tokens/components.
- Before any major frontend generation (pair with frontend-design skill).

## Process (ALWAYS follow)
1. **Ingest**:
   - Read provided files (use read_file, grep, list_dir, or vision tools for images/screenshots).
   - Parse for:
     - Colors: primary, secondary, accent, semantic (success/error), neutrals. Prefer OKLCH/HSL for theming. Extract hex/rgb if given.
     - Typography: font families (display/body/mono), sizes, weights, line-heights, letter-spacing.
     - Spacing: base unit (4px/8px), scale, fluid clamps if used.
     - Radii, shadows, borders, motion (durations, easings).
     - Components: buttons, cards, inputs, nav, modals, etc. — their variants, states, usage rules.
     - Layout patterns: grids, containers, responsive breakpoints.
     - Existing DESIGN.md, tokens.css, theme files — prioritize and merge.
   - For screenshots/UI images: describe visible styles (use image analysis or describe), extract approximate tokens.

2. **Generate/Update DESIGN.md**:
   - Create or update `DESIGN.md` in project root (or specified path).
   - Structure (use consistent format):
     ```markdown
     # DESIGN.md — [Project/Brand] Design System

     ## Tokens
     ### Colors
     - --color-primary: oklch(0.6 0.2 240); /* or hex */
     - Use CSS vars or Tailwind config.
     ### Typography
     - --font-display: 'Instrument Serif', serif;
     - Sizes, weights, etc.
     ### Spacing, Radii, etc.

     ## Components
     - Button: primary/secondary/ghost, sizes, states. Example code.
     - Card: ...
     (Include accessibility, responsive notes.)

     ## Patterns & Rules
     - Layout: ...
     - Motion: ...
     - Anti-patterns / NEVER: ...

     ## Usage
     - Always read this DESIGN.md before generating UI.
     - Use only defined tokens.
     ```
   - Also output tokens.css or update tailwind config if appropriate.
   - For multiple brands: support DESIGN-brand1.md etc.

3. **Enforce in Generation**:
   - In prompts: "Strictly follow DESIGN.md. Use only tokens and patterns defined there. Update DESIGN.md for any new elements."
   - Validate output against it.
   - For handoff: include DESIGN.md in bundles.

4. **Iterate**:
   - When changes requested: update DESIGN.md first if tokens/patterns change, then regenerate UI.
   - Support "remix" or evolve the system.

## Integration with Other Skills
- Pair with **frontend-design**: This handles the "what" (system), that handles "how" (aesthetics execution).
- With **web-artifacts-builder**: For implementation patterns on top of the system.
- In Grok Brush / Artifacts apps: Expose "Ingest Design System" button (upload/paste files or describe) that runs this skill to populate the kit/panel and save DESIGN.md.

## Grok-Specific Execution
- Use tools: read_file/grep for code, open_page for web refs, image_gen/imagine or vision for screenshots (describe "extract tokens from this UI").
- Output: Complete DESIGN.md + any supporting files (tokens.css snippet).
- For live apps: Generate self-contained previews that use the tokens (CSS vars injected).
- Test: After, run dev/build and verify consistency.

## Examples
- Ingest from Tailwind theme or shadcn: Extract to DESIGN.md.
- From screenshot: "Analyze this image and create DESIGN.md with approximate tokens."
- From codebase: Scan for CSS vars, class usage.

This skill replicates Claude Design's "build design system from codebase/design files" for on-brand, consistent output without repetition. Use proactively for any UI work.

Load on demand. Combine for best results.
