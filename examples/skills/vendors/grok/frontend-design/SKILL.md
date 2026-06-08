---
name: grok-frontend-design
description: "Create distinctive, production-grade frontend interfaces with high design quality that avoid generic \"AI slop\". Use this skill (or invoke /frontend-design) when the user asks to build web components, pages, applications, UIs, or landing pages (especially Next.js/React/Tailwind/TSX). Forces bold aesthetic commitment, exceptional attention to typography/motion/spatial details, and creative choices before any code. Integrates with Grok's tools for research, visuals, and project editing."
category: vendors
harness: grok
requires: "Grok CLI harness (task tool, image_gen, etc.)"
role: shared
tags: [grok, vendor, harness]
backup_of: frontend-design
backup_path: /home/pablothethinker/.grok/skills/frontend-design/SKILL.md
when_to_call: when running on the grok harness with its native tools; use universal/* via MCP otherwise
---

# grok-frontend-design (grok harness)

> **Harness:** grok · **Requires:** Grok CLI harness (task tool, image_gen, etc.)
>
> Prefer the **universal/** counterpart when using AgentDrive MCP with any model.
> This copy preserves the native grok workflow and tool assumptions.

---

This skill guides creation of distinctive, production-grade frontend interfaces that avoid generic "AI slop" aesthetics (purple gradients, Inter font, centered boxes, predictable layouts). Implement real working code with exceptional attention to aesthetic details and creative choices. Match the precision and intentionality of senior designers.

The user provides frontend requirements: a component, page, application, or interface to build. They may include context about the purpose, audience, brand (e.g. REN's calm premium graph-focused operator vibe), or technical constraints (Next.js 16, React 19, Tailwind 4, TypeScript, Geist font, etc.).

## Design Thinking (ALWAYS do this FIRST, before any code)

Before generating or editing any code, pause and explicitly:

- **Purpose**: What problem does this interface solve? Who uses it? (e.g. for REN: premium operator for brands managing living identity + Interest Graph; calm, protective, human-in-control gates).
- **Tone / Aesthetic Direction**: Pick an *extreme* and commit boldly. Examples: brutally minimal (Linear-inspired calm restraint), maximalist chaos (expressive, layered), retro-futuristic, organic/natural (connection/graph motifs), luxury/refined (elegant Japanese sensibility, precise), playful, editorial/magazine, brutalist/raw, art deco/geometric, soft/pastel, industrial/utilitarian, dark premium operator (indigo/violet + emerald/amber status accents). Use these for inspiration but design one true to the direction. **CRITICAL: State your choice explicitly and execute with precision. Bold maximalism and refined minimalism both work — the key is intentionality, not intensity or safe averages.**
- **Constraints**: Technical (framework like Next.js/Tailwind/shadcn, performance, a11y, responsive, dark/light), brand (no character photos if specified, use graph sigil/mark, specific palette), project (edit via search_replace, match existing code style).
- **Differentiation**: What makes this UNFORGETTABLE? What's the one thing someone will remember and talk about? (e.g. living animated Interest Graph as central interactive element, "gate as the feature" ritual, while-you-sleep operator status that feels alive).

**CRITICAL**: Choose a clear conceptual direction and execute it with precision. Never default to generic. Interpret the requirements creatively.

Then implement working code (Next.js/React/TSX + Tailwind, vanilla HTML/CSS/JS, or other as specified) that is:
- Production-grade, functional, accessible, performant, and type-safe.
- Visually striking, memorable, and cohesive with a clear aesthetic point-of-view.
- Meticulously refined in every detail (spacing, alignment, micro-details, states).
- Testable/editable in the current project environment (use terminal to run builds/dev if needed).

## Frontend Aesthetics Guidelines (Focus on these dimensions)

Guide your choices explicitly in these areas. Commit to one cohesive aesthetic and vary it creatively per project — no two should feel the same.

- **Typography**: Choose fonts that are beautiful, unique, and interesting. Avoid generic (Inter, Roboto, Arial, system fonts). Opt for distinctive, characterful choices that elevate (e.g. pair bold display like Instrument Serif or Clash with refined body; use Geist as base but layer interesting variables if project allows; load Google fonts or use system creatively). Unexpected pairings, high contrast weights (100/900 extremes), large size jumps. State your font choices before coding.

- **Color & Theme**: Commit to a cohesive aesthetic. Use CSS variables/tailwind config for consistency. Dominant colors with sharp accents outperform timid, evenly-distributed palettes. Draw from IDE themes, cultural references, or brand (for REN: deep indigo/ink #0A0F1E + violet #8b5cf6 accents, emerald for "operating", amber for "gates/attention", refined neutrals). Dark premium or light refined as fits tone. Avoid clichéd purple gradients on white.

- **Motion**: Use animations for effects and micro-interactions that delight. Prioritize CSS-only (transitions, @keyframes, scroll-driven) for HTML. For React/Next: use framer-motion/Motion library when available in project. Focus on *high-impact moments*: one well-orchestrated page load with staggered reveals (animation-delay, opacity/translate), purposeful hovers, scroll-triggered, state changes that feel alive (e.g. graph edges pulsing on "cycle complete"). Avoid scattered or gimmicky micro-interactions. One signature motion > many.

- **Spatial Composition / Layout**: Unexpected layouts. Asymmetry where it serves (not random). Overlap, diagonal flow, grid-breaking elements. Generous negative space *or* controlled high density. Breathe like premium Japanese design or bold editorial. Break predictable centering/boxes.

- **Backgrounds & Visual Details**: Create atmosphere and depth rather than defaulting to solid colors or flat. Add contextual effects and textures that match the aesthetic: gradient meshes, subtle noise/grain, geometric patterns (inspired by Interest Graph nodes/connections), layered transparencies, dramatic but elegant shadows, decorative borders, custom cursors if fitting, atmospheric overlays. For graph-heavy (REN): make backgrounds or elements feel like living networks without clutter.

**NEVER use generic AI-generated aesthetics**:
- Overused font families (Inter, Roboto, Arial, system sans by default).
- Clichéd color schemes (especially purple gradients on white, safe blues).
- Predictable layouts and component patterns (centered hero + 3 cards, generic modals, cookie-cutter navs).
- Cookie-cutter design that lacks context-specific character or brand soul.
- "AI slop": timid, forgettable, overly safe, samey across projects.

**Interpret creatively and make unexpected choices** that feel genuinely *designed* for the context and audience. Vary between light/dark, fonts, aesthetics per request. Think outside the box — Grok is capable of extraordinary creative work. Don't hold back.

**IMPORTANT**: Match implementation complexity to the aesthetic vision.
- Maximalist/expressive: elaborate code, extensive animations/effects, rich details.
- Minimalist/refined/calm (e.g. Linear/REN operator): restraint, precision, obsessive attention to spacing/typography/subtle details. Elegance from executing the vision *well*, not more stuff.
- Always production: real working, responsive, accessible (ARIA, focus, contrast), no placeholders.

## Grok-Specific Execution (Use Your Tools & Environment)

- **Before code**: Explicitly reason through Design Thinking in your response (state choices). Use tools if helpful: web_search for current trends/inspirations/fonts (e.g. "best distinctive fonts 2026"), open_page on design refs, image_gen or imagine to create reference visuals/moodboards if user wants (or for your internal ideation).
- **Code generation**: For this env (Next.js/React/Tailwind/TSX common in projects like ren-web): generate complete, editable files. Prefer Tailwind + CSS vars. Use shadcn/ui patterns or native if project doesn't have. Make components composable.
- **Project integration**: When in a codebase (e.g. ren-web), first explore existing (use read_file, grep, list_dir on app/components, globals.css, layout, existing pages). Match style, tokens, fonts (Geist), routing. Use search_replace (or write for new) to edit precisely. Never overwrite without plan.
- **Testing/Iteration**: After generating, suggest or run commands (via terminal tool) like `npm run dev`, `npm run build` to verify. Use browser? No direct, but describe or use for feedback loop. For visuals, propose image_gen of the UI.
- **REN / Agentic context** (if relevant): Emphasize "operator" feel — calm status, living graphs (SVG/Canvas interactive nodes/edges with labels like narrative_bridge), gates as beautiful ritual (approve/refine with optimistic UI, explanations), "while you sleep" proactive elements, "we" voice in copy, privacy/containment. Graph as central strategic asset viz.
- **Output format**: Always wrap full self-contained examples in ```html or ```tsx. For projects, provide diffs or exact search_replace instructions. Include quality checklist at end: production? refined details? matches aesthetic? no slop?
- **Iteration**: Skills like this are for repeated use. After first version, user can refine ("make the motion more staggered", "shift tone to brutalist"). Re-apply the framework each time.

Remember: As Grok (xAI), you bring real-time tool access, humor where fitting, truth-seeking precision, and integration with the full engineering workflow (files, terminal, research). Use this to create frontends that feel *alive*, intentional, and superior to generic AI output. Commit fully to the vision — show what's possible when thinking outside the box.

You can’t perform that action at this time. (Adapt this note if in Claude env, but here use tools.)

## DESIGN.md for Persistent Design Systems (Claude-inspired)
Claude Design and community skills use `DESIGN.md` (or similar) as a living contract for brand tokens, components, patterns, and aesthetics. 

**Always**:
- Read any existing DESIGN.md, tokens.css, or design files in the project first.
- Generate or update DESIGN.md with:
  - **Tokens**: CSS custom properties or Tailwind config for colors (primary, semantic, neutrals with OKLCH/HSL for theming), typography (font stacks, sizes, weights, leading), spacing (4/8px scale or fluid), radii, shadows, motion tokens.
  - **Components**: List of core UI patterns (Button variants, Card, Input, Nav, Modal) with usage rules, props, accessibility notes, and example snippets.
  - **Aesthetics & Rules**: The committed direction (e.g., "brutalist minimal: sharp sans, high contrast monochrome + one accent, generous whitespace, CSS-only transitions, no gradients unless subtle noise").
  - **Anti-patterns**: Explicit "NEVER" list (generic fonts, purple slop, centered boxes, etc.).
- In every generation prompt: "Read and strictly follow the DESIGN.md in the project root. Output must use only defined tokens and patterns. Update DESIGN.md if new tokens/components are introduced."
- For multi-project or team: support multiple DESIGN.md or per-folder.

Example structure to output:
```markdown
# DESIGN.md — [Project] Design System

## Tokens
- Colors: --primary: oklch(...); etc.
- Typography: ...
## Components
- Button: ...
## Rules
- Always ...
```

Use this for brand consistency like Claude Design's automatic application after ingesting codebase/design files.

## Advanced Prompting Techniques (from Claude best practices)
- **Design Thinking first** (as above).
- **Commit to extreme aesthetic** and execute precisely.
- **Override defaults**: Claude (and models) default to "house style" (cream, serif, etc.). Always specify concrete alternative or "propose 3 directions first, then implement chosen".
- **Few-shot / examples**: Provide 1-3 concrete before/after or good examples wrapped in <example>.
- **XML structure**: Use <frontend_aesthetics>, <design_system>, <output_format> tags.
- **Anti-slop explicit**:
  <frontend_aesthetics>
  NEVER use generic AI-generated aesthetics like overused font families (Inter, Roboto, Arial, system fonts), clichéd color schemes (particularly purple gradients on white or dark backgrounds), predictable layouts and component patterns, and cookie-cutter design that lacks context-specific character. Use unique fonts, cohesive colors and themes, and animations for effects and micro-interactions.
  </frontend_aesthetics>
- **Propose options**: "Before building, propose 3-4 distinct visual directions (bg/accent/type — rationale). User picks, then implement only that."
- **For Artifacts-like**: Generate self-contained HTML/Tailwind for live preview (iframe sandbox), plus clean source for handoff. Include Preview/Code toggle in mind.
- **Iteration**: Support inline comments ("Refine this button: increase padding, use primary token"), direct edits, and param controls (sliders for spacing, hue).
- **Skills composition**: Combine with architecture skill (React patterns, shadcn, state), accessibility, brand guidelines.
- **Ingest**: When given code, screenshots, or files, parse for tokens/components and populate DESIGN.md or kit.

## Companion Skills to Create/Use
- **design-system-ingest**: For parsing codebase/CSS/screenshots into DESIGN.md + tokens.
- **web-artifacts-builder**: For React/Next + Tailwind + shadcn patterns, component composition, responsive, dark mode, TypeScript.
- **artifacts-iteration**: For live preview loops, version management, export bundles (HTML, code handoff).

## Usage
- Invoke explicitly: "Use /frontend-design" or "Apply frontend-design skill to [request]".
- Auto: Grok will reference when frontend UI work matches description.
- For ren-web or similar: "Build a new marketing section for REN using frontend-design skill, calm premium operator aesthetic, focus on graph."
- Combine with other skills (e.g. changelog after edits, imagine for visuals).
- In Grok Brush or similar apps: Use to generate artifacts compatible with chat+canvas UX (inline comments, DESIGN.md, live updates).

This skill is self-contained and powerful. Load on demand to keep context clean. Mirror and extend Claude's frontend-design + artifacts + design system approach for superior, distinctive results with Grok.
