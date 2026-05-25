# Savant — cmux-style pivot evaluation

**Status:** draft for Pablo's review. No code touched. No commits.
**Date:** 2026-05-24

---

## 1. What cmux actually is

cmux (manaflow-ai/cmux) is a **native macOS terminal application** built in
Swift + AppKit on top of libghostty (Ghostty's GPU-accelerated rendering
engine). Hierarchy mirrors tmux conceptually — Workspaces → Surfaces (tabs) →
Panes (splits) — but rendered as a real macOS app with vertical sidebar tabs
showing per-workspace git branch, PR status, working dir, listening ports, and
latest notification text. Control plane is a Unix socket (`/tmp/cmux.sock`)
speaking JSON-RPC. Core agent feature is `cmux read-screen`, which lets one
pane read another pane's content for inter-agent communication. Notifications
flow through OSC 9/99/777 sequences plus a `cmux notify` CLI wired into Claude
Code, Codex, OpenCode, Aider, and Gemini hooks. Includes an in-app WebKit
browser with a scriptable accessibility-tree API. **No memory, no learning,
no provenance.** Stated philosophy: *primitive-first* — provide the building
blocks, let developers build workflows. Stack: Swift 81%, Python 10%,
TypeScript 4%. macOS-only.

## 2. What Savant currently is

Savant is a Python agent-DNA-pool framework: every agent and sub-agent gets a
private, persistent, file-on-disk pool of typed, versioned **Genomes**
extracted from successful runs, with isolation under `~/.savant/swarms/`. The
pool-evolution stack already shipped (or specced and partially built) covers
encounter-graded per-genome confidence, inheritance manifests on sub-agent
hand-off, trust-gated quarantine of foreign DNA via a sandboxed evaluator,
opt-in federated peer registry, and a background reconciliation routine that
continuously absorbs new DNA through the trust gate. The reframe is explicit:
Savant is becoming a **federated learning organism**, not a lookup library.
Current UI is a Rich + prompt_toolkit chat surface plus a Mission Board.
Python 3.11+, Linux/macOS/Termux/WSL, MIT, local-first.

## 3. The pivot question

### Option A — Full pivot

Rebuild Savant's user-facing layer as a cmux-style multiplexer. Wins:
parallel agents become legible and demoable. Loses: the federated-learning
moat goes invisible or vestigial; Python is the wrong stack for native
terminal rendering; we enter a crowded category (tmux, zellij, cmux, Warp,
Wave) with high baseline and thin differentiation. **Months, not weeks.
Identity reset.**

### Option B — Layered fit (recommended)

Keep the pool/evolution core as the federated memory backplane. Build a
cmux-shaped interaction shell on top whose primitives map cleanly: workspace
= swarm, surface = mission, pane = sub-agent, pane-start = `pull_relevant_dna`,
pane-end = `record_outcome`, hand-off = inheritance manifest, peer-pull =
quarantine intake. **The shell exists to make the learning organism visible.**
Risk: shell work is endless and will try to eat the roadmap.

### Option C — No-go

Stay on Rich + prompt_toolkit; pursue the existing UX-PROPOSAL plan. Safe.
Preserves focus on the moat. Cost: invisibility — a stronger orchestrator
could bolt on lightweight memory later and reduce Savant to a backend
without a front door.

**Recommendation: Option B, executed as integration-not-clone.** See §7.

## 4. Codex's take

Codex (gpt-5.4, high-effort) was sent the full context and asked to argue
all three sides and propose a fourth path if one existed. Verdict:

> Option 1 is seductive and wrong. Option 2 is the strongest strategic fit.
> Option 3 is defensible but leaves growth on the table. The best execution
> is a third path: do not clone cmux; integrate with shells and keep Savant
> as the memory/control substrate.

On the full pivot:

> If you do this, Savant stops being Savant. You gain a better shell and
> lose the only thing that is hard to copy.

On the layered fit — and the right framing:

> This is the right strategy only if the shell stays a layer, not the
> identity. The moment the shell becomes the main event, you start losing.

On the third path — integrate instead of clone:

> Make Savant headless first. Ship a control-plane protocol (Unix socket
> or local HTTP/JSON-RPC, first-class event model). Build adapters, not
> a renderer — cmux adapter, tmux adapter, Claude Code / Codex / Aider /
> OpenCode hooks. Build an observability console (Mission Board, lineage
> graph, quarantine inbox, promotion log, peer sync status, genome
> confidence heatmap) — TUI or web is enough. The job is to reveal the
> learning organism, not replace Ghostty.

**My reaction:** agree on substance, disagree on sequencing. Codex's
"headless first, adapters second, console third" is right architecturally but
understates Pablo's current pain — Savant already feels invisible, and
shipping a protocol without a felt UX upgrade trades elegance for another
quarter of users not seeing the pool grow. Invert: ship the observability
console (UX-PROPOSAL Patterns 3+4 — pool ribbon + live sub-agent tree) on
the existing Rich surface first, then extract the control-plane protocol
when a second adapter demands it. Build the protocol on demand, not on spec.

## 5. If we pivot — the migration shape

**Survives:** `savant.events`, `SavantPool`, `Harness`, encounter
confidence, inheritance manifests, quarantine, peer registry, reconciliation,
genome schema, swarm isolation, Mission Board data model, CLI subcommands.

**Changes:** `chat.py` becomes one pane (or one adapter target). CLI
subcommands get exposed as in-pane slash commands via the shared
skills/genomes router (UX-PROPOSAL Pattern 5). Mission Board becomes the
landing surface; chat is a pane on top. The event bus (Pattern 1) becomes
source-of-truth for an eventual control-plane protocol over a local socket.

**Thrown away:** the current single-window prompt_toolkit composer as the
*only* surface, the one-terminal-equals-one-Savant-session assumption, and
the polite turn-taking model.

**Honest cost:** Option B is a 2-week visible rebuild on top of the ~5 days
of UX-PROPOSAL groundwork. Option A is two months minimum and the wrong
company.

## 6. Naming options

Five from Codex (verbatim) plus three from this pass. All Vektra-register —
short, declarative, technical. No franchise references. No animal/coffee
cuteness.

**From Codex:**

1. **Axon** — directed signal transmission: learned capability moving forward through an operational nervous system.
2. **Lattice** — a federated mesh where local improvements propagate, reconcile, and harden into shared structure.
3. **Relay** — controlled exchange and handoff between agents, operators, and peer systems.
4. **Lineage** — inherited capability, provenance, and versioned descent across runs and sub-agents.
5. **Mycel** — quiet distributed growth: a hidden network that absorbs, routes, and strengthens useful patterns over time.

**Additional:**

6. **Synapse** — the gap where signals cross and learning is encoded; evokes the moment a sub-agent's lesson becomes the parent's reflex.
7. **Confluence** — many flows merging into one: sub-agent runs, peer pools, and quarantine intake all converging into the operator's pool.
8. **Plexus** — a dense intersection of nerves; evokes the operator's pool as the convergence point of every connected learning channel.

Shortlist: **Axon** (cleanest single-word product name), **Lattice** (best
captures the federated mesh), **Mycel** (best captures the reconciliation feel).

## 7. Recommendation

**Option B, executed as Codex's integrate-not-clone path, with the sequence
inverted: ship the observability layer on the existing Rich surface first,
extract the protocol when the second adapter demands it.**

Concretely: finish UX-PROPOSAL Patterns 1+2+3+4 (event bus, keep-typing,
pool activity ribbon, live sub-agent tree) on the current Rich stack. That
gives Savant visible parallelism, visible learning, and an event vocabulary
suitable for later protocol extraction. Then — *only* if a real cmux/tmux
adapter user materializes — promote the event bus to a Unix-socket JSON-RPC
control plane and ship a cmux adapter. Do not build a Savant-branded
multiplexer. Do not rewrite in Swift. Do not become a terminal company.

**Open question Pablo has to answer to lock this in:** does the umbrella
product brand change? If Savant remains the umbrella, §6 is dead and the
naming work is just for an eventual shell adapter. If the federated-learning
substrate gets a new umbrella name (Axon / Lattice / Mycel) and "Savant"
narrows to the Python framework / chat surface, then §6 is the live
decision and the next move is picking one and updating ARCHITECTURE.md +
VISION.md accordingly.
