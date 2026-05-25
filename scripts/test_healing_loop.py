"""End-to-end functional test of the AgentDrive healing loop.

Scripted scenario that walks every stage in docs/RECOVERY.md against
real (synthetic) data so each module's behavior is observable. NOT a
unit test — a runnable demo that surfaces what the healing flow looks
like to an operator.

Run::

    cd ~/savant && python3 scripts/test_healing_loop.py
"""

from __future__ import annotations

import json
import os
import random
import shutil
import subprocess
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional, Tuple

# Ensure src/ is on sys.path so the script runs from a checkout.
ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from rich.console import Console
from rich.live import Live
from rich.text import Text

from agentdrive.constants import (
    reset_agentdrive_home_override,
    set_agentdrive_home_override,
)
from agentdrive import local_models
from agentdrive.events import (
    ConfidenceUpdated,
    GenomeEvolved,
    PoolIngest,
    PoolOutcome,
    QuarantineSubmitted,
    SubagentDone,
    SubagentSpawn,
    SubagentTokens,
    SubagentTool,
    default_bus,
    emit,
    subscribe,
    unsubscribe,
)
from agentdrive.genome.models import Genome, GenomeManifest
from agentdrive.harness.harness import Harness
from agentdrive.drive.drive import AgentDrive
from agentdrive.quarantine import get_default_quarantine
from agentdrive.registry import GenomeRegistry
from agentdrive.tui.chrome import (
    Palette,
    Section,
    Tree,
    TreeRow,
    section_panel,
)
from agentdrive.tui.subagent_tree import SubagentTree
from agentdrive import confidence as confidence_module
from agentdrive import genomes_api


# ─────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────

console = Console()
palette = Palette(None)


def divider(phase: str) -> None:
    console.print()
    console.rule(f"[bold cyan]── {phase} ──[/]", style="cyan")
    console.print()


def stars(n: int) -> str:
    return "★" * n + "☆" * (5 - n)


def seed_genome(
    gid: str,
    domain: str,
    score: float = 0.7,
    version: str = "1.0.0",
) -> Genome:
    """Construct a valid Genome with the given domain and seed score."""
    manifest = GenomeManifest(
        id=gid,
        version=version,
        content_hash="sha256:" + "deadbeef" * 8,
        created=datetime.now(timezone.utc),
        authors=[],
        applicability={
            "domains": [domain],
            "problem_signatures": [f"{domain} incident response"],
        },
        evaluation_score={"reference_tasks": score},
        dependencies={
            "genomes": [],
            "agent_capabilities": ["reasoning", "writing"],
        },
    )
    g = Genome(
        manifest=manifest,
        framework={
            "id": f"{gid}-framework",
            "display_name": gid.replace("-", " ").title(),
            "steps": [
                {"id": "1", "name": "gather", "description": "collect evidence"},
                {"id": "2", "name": "analyze", "description": "synthesize findings"},
                {"id": "3", "name": "report", "description": "produce artifact"},
            ],
        },
        reasoning_patterns={
            "key_heuristics": [f"prefer {domain} primary sources"],
        },
    )
    g.finalize()
    return g


# ─────────────────────────────────────────────────────────────────────
# Event ribbons — proves the bus is the single surface
# ─────────────────────────────────────────────────────────────────────


def _ribbon_ingest(ev: PoolIngest) -> None:
    console.print(
        f"  [dim]▸ pool · ingest[/] [magenta]{ev.genome_id}[/]  "
        f"[dim]src={ev.source} actor={ev.actor}[/]"
    )


def _ribbon_outcome(ev: PoolOutcome) -> None:
    console.print(
        f"  [dim]▸ pool · outcome[/] [magenta]{ev.genome_id}[/]  "
        f"[dim]score={ev.score:.3f}[/]"
    )


def _ribbon_confidence(ev: ConfidenceUpdated) -> None:
    console.print(
        f"  [dim]▸ confidence ·[/] [magenta]{ev.genome_id}[/] "
        f"[bold cyan]{stars(ev.stars)}[/] [dim]({ev.encounters} encounters)[/]"
    )


def _ribbon_evolved(ev: GenomeEvolved) -> None:
    uses = ev.evidence.get("uses", 0) if isinstance(ev.evidence, dict) else 0
    avg = ev.evidence.get("avg_score", 0.0) if isinstance(ev.evidence, dict) else 0.0
    console.print(
        f"  [bold magenta]▸ EVOLVED ·[/] [magenta]{ev.genome_id}[/] "
        f"[dim]→ ultimate · uses={uses} avg={avg}[/]"
    )


def _ribbon_quarantine(ev: QuarantineSubmitted) -> None:
    console.print(
        f"  [dim]▸ quarantine · submitted[/] [yellow]{ev.quarantine_id[:12]}[/]  "
        f"[dim]genome={ev.genome_id} src={ev.source_peer}[/]"
    )


def attach_ribbons() -> list:
    return [
        subscribe(_ribbon_ingest, [PoolIngest]),
        subscribe(_ribbon_outcome, [PoolOutcome]),
        subscribe(_ribbon_confidence, [ConfidenceUpdated]),
        subscribe(_ribbon_evolved, [GenomeEvolved]),
        subscribe(_ribbon_quarantine, [QuarantineSubmitted]),
    ]


# ─────────────────────────────────────────────────────────────────────
# Phase implementations
# ─────────────────────────────────────────────────────────────────────


def setup_home() -> Path:
    home = Path(f"/tmp/healing-demo-{os.getpid()}")
    if home.exists():
        shutil.rmtree(home)
    home.mkdir(parents=True)
    for sub in ("genomes", "logs", "cache", "pool", "swarms", "inheritance", "quarantine"):
        (home / sub).mkdir(parents=True, exist_ok=True)
    set_agentdrive_home_override(home)
    return home


def seed_phase(pool: AgentDrive, harness: Harness, ribbon_tokens: list) -> None:
    divider("PHASE 1: SEED")
    console.print(
        "[dim]Building substrate. Each genome ingested, then graded via "
        "harness.record_outcome to accrue encounter history. Per-encounter "
        "ribbons are silenced during seeding to keep this readable; a single "
        "summary line per genome shows the final confidence rating.[/]"
    )
    console.print()
    # Silence the firehose during seeding.
    for t in ribbon_tokens:
        unsubscribe(t)

    # Encounter counts chosen so the ConfidenceRule (3 stars requires
    # 25+ encounters + ≥75% success_rate under SUCCESS_THRESHOLD=0.6)
    # gives the rating tiers expected by RECOVERY.md.
    spec = [
        # (gid, domain, base_score, encounters, score_distribution)
        ("incident-postmortem",  "security", 0.72, 28, "high"),
        ("evidence-trace",       "security", 0.68, 26, "high"),
        ("risk-scorer",          "security", 0.82, 55, "high"),
        ("postmortem-author",    "security", 0.70, 2,  "high"),
        ("embed-bulk",           "embedding", 0.75, 5,  "high"),
    ]

    for gid, domain, base, encounters, dist in spec:
        g = seed_genome(gid, domain=domain, score=base)
        pool.ingest(g, source="seed", actor="demo")

        # Drive encounter history through the harness so confidence accrues.
        for i in range(encounters):
            if dist == "high":
                score = 0.85 + random.uniform(0.0, 0.10)
            elif dist == "mixed-high":
                score = 0.78 if i % 3 != 0 else 0.55
            else:  # mixed-mid
                score = 0.65 if i % 2 == 0 else 0.55

            with harness.task_context(f"task-{gid}-{i}"):
                harness.record_outcome({
                    "status": "success",
                    "quality": score,
                    "used_genomes": [g.genome_id],
                    "result": f"synthetic outcome {i}",
                })

        rating = confidence_module.get_rating(g.genome_id, pool.registry)
        srep = stars(rating.stars) if rating else "☆☆☆☆☆"
        encs = rating.encounters if rating else 0
        console.print(
            f"  [green]✓[/] [magenta]{gid:<22}[/] [dim]domain={domain:<10}[/]"
            f"  [cyan]{srep}[/]  [dim]{encs:>2} encounters[/]"
        )
    console.print()
    # Re-attach ribbons for the remainder of the demo.
    ribbon_tokens[:] = attach_ribbons()


def snapshot_pool(pool: AgentDrive, title: str) -> None:
    entries = genomes_api.list_genomes(pool.registry)
    rows = []
    for e in sorted(entries, key=lambda x: (-x.confidence_stars, -x.encounter_count)):
        promotion = " [bold magenta]◆ PROMOTED[/]" if e.is_ultimate else ""
        rows.append(TreeRow(
            label=f"[magenta]{e.id}[/]  [cyan]{stars(e.confidence_stars)}[/]{promotion}",
            secondary=f"{e.encounter_count} encounters · score {e.score:.3f}",
        ))
    console.print(section_panel(
        Section(title, [("genomes", str(len(entries)))], palette=palette),
        Tree(rows, palette=palette),
        title=f"◆ {title}",
        palette=palette,
    ))


def simulate_death(task_signature: str) -> None:
    divider("PHASE 3: AGENT DEATH")
    console.print(
        f"  [bold red]▸ AGENT DEATH[/] · [yellow]agent-paws-3[/] · "
        f"task: [italic]\"{task_signature}\"[/]"
    )
    console.print("  [dim]SubagentDone(ok=False) would fire here in production.[/]")


def filter_recovery_candidates(pool: AgentDrive, domain: str) -> list:
    """RECOVERY.md §2.2: stars ≥ 3 AND domain match."""
    entries = genomes_api.list_genomes(pool.registry)
    eligible = []
    for e in entries:
        if e.confidence_stars < 3:
            continue
        # domain match: look up the full genome info
        info = genomes_api.get_genome(e.dir_name, pool.registry)
        if info is None:
            continue
        if domain in info.domains:
            eligible.append((e, info))
    eligible.sort(key=lambda t: (-t[0].confidence_stars, -t[0].encounter_count))
    return eligible


def show_candidates(eligible: list) -> list:
    divider("PHASE 4: RECOVERY CANDIDATES PULLED")
    console.print(
        "  [dim]Filter: confidence_stars ≥ 3 AND domain=security (per RECOVERY.md §2.2)[/]"
    )
    console.print()
    rows = []
    for entry, info in eligible:
        prom = " [bold magenta]◆ PROMOTED[/]" if entry.is_ultimate else ""
        rows.append(TreeRow(
            label=f"[magenta]{entry.id}[/]  [cyan]{stars(entry.confidence_stars)}[/]{prom}",
            secondary=f"{entry.encounter_count} encounters · score {entry.score:.3f}",
        ))
    console.print(Tree(rows, palette=palette))
    return eligible[:3]


# ─────────────────────────────────────────────────────────────────────
# Real LLM backends for the repair swarm
# ─────────────────────────────────────────────────────────────────────


# External-agent CLI used by the repair swarm. Configurable via the
# AGENTDRIVE_REPAIR_CLI env var; otherwise the script falls back to a
# stub that reports "no backend configured" and the test still exercises
# the routing path (just without a real LLM in the loop).
import os
CODEX_TOOL = Path(os.environ.get("AGENTDRIVE_REPAIR_CLI", "")) if os.environ.get("AGENTDRIVE_REPAIR_CLI") else None
SUBAGENT_TIMEOUT_S = 90


def _build_repair_prompt(task_signature: str, genome_info, genome_id: str) -> str:
    """Build the prompt handed to each repair sub-agent.

    Each sub-agent receives the dead task's signature plus the pulled DNA
    (manifest excerpt + reasoning patterns) and is asked to draft the
    recovery output. Kept short and uniform so every backend sees the
    same wire format.
    """
    domains = ", ".join(genome_info.domains or [])
    reasoning = ", ".join(getattr(genome_info, "reasoning_pattern_keys", []) or [])
    framework_steps = []
    for s in getattr(genome_info, "step_previews", []) or []:
        if isinstance(s, dict):
            framework_steps.append(f"- {s.get('name','?')}: {s.get('description','')}")
        else:
            framework_steps.append(f"- {s}")
    steps_block = "\n".join(framework_steps) or "- (no framework steps)"

    return (
        "You are a recovery sub-agent in an AgentDrive healing swarm. "
        "A peer agent died mid-task. Your job is to draft the recovery "
        "output the dead agent should have produced, using the DNA "
        "(genome) pulled from the trusted pool.\n\n"
        f"## Task signature\n{task_signature}\n\n"
        f"## Pulled genome: {genome_id}\n"
        f"- domains: {domains}\n"
        f"- reasoning patterns: {reasoning}\n"
        f"- framework:\n{steps_block}\n\n"
        "## Instructions\n"
        "Produce the recovery deliverable in under 300 words. Be concrete: "
        "name the artifact, list the sections, and write the key content. "
        "Stay in the genome's domain. Do not ask questions — recover the "
        "work."
    )


def _call_local(spec: local_models.LocalModelSpec, prompt: str) -> str:
    """Dispatch one generation through the local-model adapter layer.

    Wrapped to surface a clean error string instead of raising into the
    thread-runner, matching the previous backend contract.
    """
    try:
        return local_models.generate(spec, prompt)
    except local_models.LocalModelError as exc:
        raise RuntimeError(str(exc)) from exc


def _call_codex(prompt: str, timeout: float) -> str:
    """Invoke Codex via the ilo runtime CLI per spec — subprocess shell-out."""
    cmd = [
        "python3",
        str(CODEX_TOOL),
        prompt,
        "--model", "gpt-5.4",
        "--effort", "medium",
        "--timeout", str(int(timeout)),
    ]
    proc = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    if proc.returncode != 0:
        raise RuntimeError(
            f"codex exited {proc.returncode}: {proc.stderr.strip()[:200]}"
        )
    return (proc.stdout or "").strip()


def _run_backend_in_thread(fn, *args, timeout: float) -> Tuple[bool, str, float]:
    """Run a backend callable in a daemon thread with a hard timeout.

    Returns (ok, output_text, elapsed_seconds). On timeout / exception
    returns (False, error_message, elapsed).
    """
    start = time.monotonic()
    result: dict = {"text": "", "err": None}

    def _target():
        try:
            result["text"] = fn(*args)
        except Exception as exc:  # pragma: no cover - exercised via real failures
            result["err"] = str(exc)

    th = threading.Thread(target=_target, daemon=True)
    th.start()
    th.join(timeout=timeout)
    elapsed = time.monotonic() - start
    if th.is_alive():
        return False, f"timeout after {timeout:.0f}s", elapsed
    if result["err"]:
        return False, f"error: {result['err']}", elapsed
    text = (result["text"] or "").strip()
    if not text:
        return False, "empty response", elapsed
    return True, text, elapsed


def _backend_codex(prompt: str) -> Tuple[bool, str, float]:
    return _run_backend_in_thread(_call_codex, prompt, SUBAGENT_TIMEOUT_S,
                                  timeout=SUBAGENT_TIMEOUT_S)


def _backend_local(spec: local_models.LocalModelSpec, prompt: str) -> Tuple[bool, str, float]:
    return _run_backend_in_thread(_call_local, spec, prompt,
                                  timeout=SUBAGENT_TIMEOUT_S)


def _build_subagent_lineup() -> List[tuple]:
    """Compose the sub-agent lineup from Codex + available local-model specs.

    Codex is always slot 1.  Slots 2 and 3 are filled with up to two
    reachable local-model specs from ``~/.agentdrive/local_models.yaml``.
    If fewer than two are reachable, the demo still runs — it just
    demonstrates the value prop with whatever survives.
    """
    lineup: List[tuple] = [
        # (sub_id, label, kind, payload)
        # payload is "gpt-5.4" for codex, a LocalModelSpec for "local"
        ("heal-sub-1", "codex gpt-5.4", "codex", "gpt-5.4"),
    ]
    try:
        specs = local_models.load_specs()
    except Exception as exc:
        console.print(f"  [dim](could not load local_models.yaml: {exc})[/]")
        specs = []
    available: List[local_models.LocalModelSpec] = []
    for spec in specs:
        if local_models.is_available(spec):
            available.append(spec)
        if len(available) >= 2:
            break
    for idx, spec in enumerate(available, start=2):
        sub_id = f"heal-sub-{idx}"
        label = f"{spec.backend} {spec.model}"
        lineup.append((sub_id, label, "local", spec))
    return lineup


def dispatch_repair_swarm(top3: list, task_signature: str) -> List[tuple]:
    divider("PHASE 6: REAL-LLM REPAIR SWARM")
    console.print(
        "[dim]Three sub-agents, three real model backends. "
        "Each receives the task signature + the pulled genome DNA and "
        "drafts the recovery deliverable. 90s hard timeout per agent.[/]"
    )
    console.print()
    swarm_id = "swarm-heal-001"

    tree = SubagentTree(root_id="orchestrator", root_label="recovery orchestrator")
    sub_specs = []

    # Pair each backend with a candidate genome. We always fire all
    # three sub-agents; if fewer than three candidates passed the filter
    # we cycle through what we have so every backend gets DNA to apply.
    paired = []
    if not top3:
        return []
    subagent_lineup = _build_subagent_lineup()
    if len(subagent_lineup) < 3:
        console.print(
            f"  [dim](only {len(subagent_lineup)} backend(s) reachable — "
            "demo still proceeds with what's available)[/]"
        )
        console.print()
    for i, lineup_row in enumerate(subagent_lineup):
        sub_id, label, kind, payload = lineup_row
        entry, info = top3[i % len(top3)]
        sub_specs.append((sub_id, entry.id, info))
        paired.append((sub_id, label, kind, payload, entry, info))
        spawn = SubagentSpawn(
            subagent_id=sub_id,
            parent_id="orchestrator",
            label=label,
            swarm_id=swarm_id,
        )
        emit(spawn)
        tree.apply(spawn)

    def _apply(ev):
        tree.apply(ev)

    tok1 = subscribe(_apply, [SubagentSpawn, SubagentTool, SubagentDone])

    # Outputs map keyed by sub_id; consumed downstream in PHASE 7.
    outputs: dict = {}

    try:
        # Print the lineup before launching — operator sees what's about to fire.
        for sub_id, label, _kind, _payload, entry, _info in paired:
            console.print(
                f"  [cyan]▸ spawn[/] [yellow]{sub_id}[/] → "
                f"[white]{label}[/] applying genome [magenta]{entry.id}[/]"
            )
        console.print()

        # Emit a "tool" event per sub-agent so the live tree shows which
        # model each one is talking to.
        for sub_id, label, _kind, _payload, _entry, _info in paired:
            emit(SubagentTool(
                subagent_id=sub_id,
                swarm_id=swarm_id,
                tool=label,
            ))

        # Build prompts, dispatch in parallel.
        prompts = {
            sub_id: _build_repair_prompt(task_signature, info, entry.id)
            for sub_id, _l, _k, _p, entry, info in paired
        }

        def _dispatch(spec):
            sub_id, label, kind, payload, entry, info = spec
            prompt = prompts[sub_id]
            if kind == "codex":
                ok, text, elapsed = _backend_codex(prompt)
            elif kind == "local":
                ok, text, elapsed = _backend_local(payload, prompt)
            else:
                ok, text, elapsed = False, f"unknown backend kind {kind}", 0.0
            return sub_id, label, ok, text, elapsed

        with Live(tree.render(palette), console=console, refresh_per_second=4) as live:
            with ThreadPoolExecutor(max_workers=len(paired)) as pool:
                futures = {pool.submit(_dispatch, spec): spec for spec in paired}
                for fut in as_completed(futures):
                    sub_id, label, ok, text, elapsed = fut.result()
                    outputs[sub_id] = {
                        "label": label,
                        "ok": ok,
                        "text": text,
                        "elapsed": elapsed,
                    }
                    # rough token estimate from response length
                    token_est = max(0, len(text) // 4)
                    emit(SubagentTokens(
                        subagent_id=sub_id,
                        swarm_id=swarm_id,
                        tokens=token_est,
                        cost_usd=0.0,
                    ))
                    emit(SubagentDone(
                        subagent_id=sub_id,
                        swarm_id=swarm_id,
                        ok=ok,
                        duration_s=elapsed,
                    ))
                    status = "[green]ok[/]" if ok else "[red]fail[/]"
                    console.print(
                        f"  ▸ [yellow]{sub_id}[/] {status} "
                        f"[dim]{label} · {elapsed:.1f}s · ~{token_est} tok[/]"
                    )
                    live.update(tree.render(palette))
            live.update(tree.render(palette))
            time.sleep(0.2)
    finally:
        unsubscribe(tok1)

    # Stash outputs onto sub_specs tuples so PHASE 7 can score the real text.
    enriched = []
    for sub_id, gid, info in sub_specs:
        enriched.append((sub_id, gid, info, outputs.get(sub_id, {
            "label": "?", "ok": False, "text": "", "elapsed": 0.0,
        })))
    return enriched


def _lexical_quality_score(text: str, task_signature: str) -> float:
    """Deterministic, reproducible lexical quality score in [0.0, 1.0].

    Three additive components, each capped:
      - length normalization: 0.0 → 0.4 as text grows from 0 → 600 chars
      - keyword coverage: presence of distinctive terms from the task
        signature (stopwords filtered)
      - basic coherence: penalize obvious failure shapes (very short,
        repeated whitespace, error tags) and reward sentence structure
    """
    if not text:
        return 0.0

    text_lower = text.lower()

    # length component
    length_score = min(len(text), 600) / 600.0 * 0.4

    # keyword coverage component
    stop = {
        "the", "a", "an", "for", "and", "or", "of", "in", "on", "to", "with",
        "is", "at", "by", "from", "into", "this", "that", "as", "be", "are",
    }
    terms = [
        t.strip(".,;:!?\"'()[]")
        for t in task_signature.lower().split()
        if len(t) > 3 and t.lower() not in stop
    ]
    if terms:
        hits = sum(1 for t in terms if t in text_lower)
        coverage = hits / len(terms)
    else:
        coverage = 0.0
    coverage_score = min(coverage, 1.0) * 0.4

    # coherence component
    coherence = 0.2
    if len(text) < 80:
        coherence -= 0.15
    if "error" in text_lower[:60] or "timeout" in text_lower[:60]:
        coherence -= 0.2
    # sentence punctuation as a weak structure signal
    if text.count(".") + text.count("\n") >= 3:
        coherence += 0.05
    coherence = max(-0.2, min(coherence, 0.2))

    raw = length_score + coverage_score + coherence
    return round(max(0.0, min(raw, 1.0)), 3)


def validate_and_record(
    enriched: List[tuple],
    pool: AgentDrive,
    harness: Harness,
    task_signature: str,
) -> tuple[list, list]:
    divider("PHASE 7: VALIDATION + OUTCOME RECORDING")

    console.print("[dim]Scoring real LLM outputs (lexical quality, 0.0–1.0):[/]")
    console.print()

    scored: list = []  # (sub_id, gid, info, output_meta, score, demoted_flag)
    for sub_id, gid, info, output in enriched:
        text = output.get("text", "") if output.get("ok") else ""
        score = _lexical_quality_score(text, task_signature)
        scored.append((sub_id, gid, info, output, score, False))

    # Force at least one FAIL so the quarantine path always exercises.
    if scored and all(s[4] >= 0.6 for s in scored):
        lowest_idx = min(range(len(scored)), key=lambda i: scored[i][4])
        sid, gid, info, out, score, _ = scored[lowest_idx]
        scored[lowest_idx] = (sid, gid, info, out, score, True)

    passed, failed = [], []
    for sub_id, gid, info, output, score, demoted in scored:
        effective_pass = (score >= 0.6) and not demoted
        verdict = "PASS" if effective_pass else "FAIL"
        color = "green" if effective_pass else "red"
        tag = " [dim](demoted for demo)[/]" if demoted else ""
        backend_status = "[green]ok[/]" if output.get("ok") else "[red]backend failed[/]"
        console.print(
            f"  [{color}]{verdict}[/] [magenta]{gid}[/] via [yellow]{sub_id}[/]  "
            f"[dim]score={score:.2f} · {output.get('label','?')} · {backend_status}[/]{tag}"
        )

        excerpt = (output.get("text") or "").strip().replace("\n", " ")
        if not excerpt:
            excerpt = f"<no output — {output.get('text','') or 'silent failure'}>"
        if len(excerpt) > 200:
            excerpt = excerpt[:200] + "…"
        console.print(f"    [dim]excerpt:[/] {excerpt}")

        if effective_pass:
            passed.append((sub_id, gid, info, score))
        else:
            failed.append((sub_id, gid, info, score))

    console.print()
    console.print("[dim]Recording outcomes for passing sub-agents via harness.record_outcome:[/]")
    console.print()

    before_state = {
        e.id: (e.confidence_stars, e.encounter_count)
        for e in genomes_api.list_genomes(pool.registry)
    }

    for sub_id, gid, info, score in passed:
        full_gid = info.genome_id
        with harness.task_context(f"recovery via {gid}"):
            harness.record_outcome({
                "status": "success",
                "quality": score,
                "used_genomes": [full_gid],
                "result": f"recovery delivered by {sub_id}",
            })

    console.print()
    console.print("[dim]Deltas:[/]")
    after = {
        e.id: (e.confidence_stars, e.encounter_count)
        for e in genomes_api.list_genomes(pool.registry)
    }
    for sub_id, gid, info, _ in passed:
        b = before_state.get(info.id, (0, 0))
        a = after.get(info.id, b)
        change = "unchanged" if b[0] == a[0] else f"★{b[0]}→★{a[0]}"
        console.print(
            f"  [magenta]{gid}[/]: {b[1]}→{a[1]} encounters, "
            f"[cyan]{stars(a[0])}[/] {change}"
        )

    return passed, failed


def quarantine_failed(failed: list, pool: AgentDrive) -> Optional[str]:
    divider("PHASE 8: FAILED OUTPUT → QUARANTINE")
    if not failed:
        console.print("  [dim]No failures — nothing to quarantine.[/]")
        return None

    sub_id, gid, info, score = failed[0]
    # Build a tiny fake "candidate genome" dir from a temp seed.
    candidate = seed_genome(
        gid=f"{gid}-recovery-candidate",
        domain="security",
        score=score,
        version="0.1.0",
    )
    staging = Path(f"/tmp/healing-demo-{os.getpid()}-staging") / candidate.manifest.id
    staging.mkdir(parents=True, exist_ok=True)
    candidate.save(staging)

    q = get_default_quarantine()
    entry = q.submit(staging, source_peer=f"recovery:{sub_id}")
    console.print(
        f"  [yellow]▸ quarantine entry created[/] [dim]{entry.quarantine_id[:16]}…[/]"
    )
    console.print(
        f"    genome={entry.genome_id}  status={entry.status.value}  src={entry.source_peer}"
    )
    return entry.quarantine_id


def final_summary(pool: AgentDrive, quarantine_id: Optional[str]) -> None:
    divider("PHASE 9: FINAL STATE")
    snapshot_pool(pool, "Pool state after healing")
    if quarantine_id is not None:
        q = get_default_quarantine()
        pending = q.list()
        rows = [
            TreeRow(
                label=f"[yellow]{e.quarantine_id[:16]}…[/]  [magenta]{e.genome_id}[/]",
                secondary=f"status={e.status.value} src={e.source_peer}",
            )
            for e in pending
        ]
        console.print(section_panel(
            Section("Quarantine ledger", [("pending", str(len(pending)))], palette=palette),
            Tree(rows, palette=palette),
            title="◆ Quarantine awaiting review",
            palette=palette,
        ))


# ─────────────────────────────────────────────────────────────────────
# main
# ─────────────────────────────────────────────────────────────────────


def main() -> int:
    random.seed(42)
    home = setup_home()
    console.print()
    console.print(f"[dim]AGENTDRIVE_HOME → {home}[/]")

    tokens = attach_ribbons()
    try:
        registry = GenomeRegistry()
        pool = AgentDrive(registry=registry)
        harness = Harness(agent_id="healing-demo-agent", pool=pool)

        seed_phase(pool, harness, tokens)

        divider("PHASE 2: SUBSTRATE READY")
        snapshot_pool(pool, "Pool snapshot")

        task = "draft Q4 vendor risk postmortem for payments-2025 incident"
        simulate_death(task)

        eligible = filter_recovery_candidates(pool, domain="security")
        top3 = show_candidates(eligible)

        if not top3:
            console.print("[bold red]No eligible recovery candidates — aborting demo.[/]")
            return 1

        enriched = dispatch_repair_swarm(top3, task)
        passed, failed = validate_and_record(enriched, pool, harness, task)
        qid = quarantine_failed(failed, pool)
        final_summary(pool, qid)

        divider("DONE")
        console.print("[bold green]✓ healing loop completed end-to-end[/]")
        return 0
    finally:
        for t in tokens:
            try:
                unsubscribe(t)
            except Exception:
                pass


if __name__ == "__main__":
    sys.exit(main())
