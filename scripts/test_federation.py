#!/usr/bin/env python3
"""End-to-end federation demo: three AGENTDRIVE_HOMEs proving the trust gate.

Runs through the full peer/quarantine/inheritance flow without shelling out
to the ``agentdrive`` CLI — all calls hit the Python API directly. The goal is
to demonstrate, in practice (not just in unit tests), that the quarantine
gate is unbypassable: every byte that crosses an instance boundary lands in
quarantine, regardless of the peer's trust label.

Scenario (Vektra federation):
    vektra-edge-1         (home A) — seeds 3 security-domain genomes
    vektra-edge-2         (home B) — seeds 2 code-domain genomes (one poisoned later)
    vektra-edge-coordinator (home C) — empty; learns from both edges

Run directly:
    python3 scripts/test_federation.py
"""

from __future__ import annotations

import os
import random
import sys
import tempfile
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator, List, Optional, Tuple

# Make the in-tree package importable when run from a checkout.
REPO_ROOT = Path(__file__).resolve().parent.parent
SRC = REPO_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from rich.console import Console
from rich.panel import Panel
from rich.rule import Rule
from rich.table import Table
from rich.text import Text

from agentdrive.confidence import SIDECAR_NAME, ConfidenceRating
from agentdrive.constants import (
    reset_agentdrive_home_override,
    set_agentdrive_home_override,
)
from agentdrive.drive.drive import AgentDrive
from agentdrive.events import (
    InheritanceReceived,
    PeerSyncCompleted,
    PeerSyncStarted,
    PoolIngest,
    QuarantineApproved,
    QuarantineRejected,
    QuarantineSubmitted,
    QuarantineValidated,
    default_bus,
)
from agentdrive.genome.models import (
    Genome,
    GenomeAuthor,
    GenomeManifest,
    GenomeProvenance,
    ImprovementEvent,
)
from agentdrive.genomes_api import list_genomes
from agentdrive.inheritance import InheritanceManifest, record_manifest
from agentdrive.peers import PeerRegistry, sync_peer
from agentdrive.quarantine import QuarantineStatus, get_default_quarantine
from agentdrive.reconciliation import ReconciliationRunner
from agentdrive.registry import GenomeRegistry
from agentdrive.tui.chrome import Glyphs, Palette, Section

CONSOLE = Console(force_terminal=True, color_system="truecolor", highlight=False)
PALETTE = Palette()

LABELS = {
    "A": "vektra-edge-1",
    "B": "vektra-edge-2",
    "C": "vektra-edge-coordinator",
}


# ─────────────────────────────────────────────────────────────────────
# Output helpers
# ─────────────────────────────────────────────────────────────────────


def divider(title: str) -> None:
    CONSOLE.print()
    CONSOLE.print(Rule(f"[bold cyan]── {title} ──[/]", style="cyan"))
    CONSOLE.print()


def ribbon(instance: str, kind: str, msg: str, accent: str = "cyan") -> None:
    """One-line event ribbon, chat.py style."""
    label = LABELS.get(instance, instance)
    line = Text()
    line.append(f"{Glyphs.MID} ", style=PALETTE.muted)
    line.append(f"{label:<24}", style=f"bold {accent}")
    line.append(f" {kind:<22}", style=PALETTE.accent)
    line.append(f" {msg}", style="")
    CONSOLE.print(line)


def info(msg: str) -> None:
    CONSOLE.print(f"  [dim]·[/] {msg}")


def note(msg: str) -> None:
    CONSOLE.print(f"[bold green]{Glyphs.CHECK}[/] {msg}")


def panel(title: str, body: object, border: str = "cyan") -> None:
    CONSOLE.print(Panel(body, title=title, border_style=border, padding=(0, 1)))


# ─────────────────────────────────────────────────────────────────────
# AGENTDRIVE_HOME juggling
# ─────────────────────────────────────────────────────────────────────


_TOKENS: List = []


@contextmanager
def use_home(home: Path) -> Iterator[Path]:
    """Bind AGENTDRIVE_HOME to a given dir for the duration of a block."""
    tok = set_agentdrive_home_override(home)
    try:
        yield home
    finally:
        reset_agentdrive_home_override(tok)


def init_home(home: Path) -> None:
    """Bring a AGENTDRIVE_HOME-like dir to life: same layout the CLI uses."""
    home.mkdir(parents=True, exist_ok=True)
    for sub in ("genomes", "pool", "peers", "quarantine", "inheritance", "logs"):
        (home / sub).mkdir(parents=True, exist_ok=True)


# ─────────────────────────────────────────────────────────────────────
# Genome seeding
# ─────────────────────────────────────────────────────────────────────


def seed_genome(
    registry: GenomeRegistry,
    gid: str,
    *,
    domain: str,
    encounters: int,
    success_rate: float,
    avg_score: float,
    target_stars: int,
) -> Tuple[Genome, Path]:
    """Build a high-confidence genome and persist it + its confidence sidecar.

    Provenance gets enough ImprovementEvents that the score series in
    confidence.compute_rating sees a healthy run. We also write the
    confidence sidecar directly so the rating shows up immediately —
    the harness normally drives this through record_outcome events,
    which is outside the scope of a federation demo.
    """
    now = datetime.now(timezone.utc)
    improvements = [
        ImprovementEvent(
            timestamp=now,
            description=f"reference task #{i}",
            proposed_by="seeder",
            score_delta=round(random.uniform(0.0, 0.05), 4),
            notes="seeded for federation demo",
        )
        for i in range(min(encounters, 12))
    ]
    manifest = GenomeManifest(
        id=gid,
        version="1.0.0",
        content_hash="sha256:pending",
        created=now,
        authors=[GenomeAuthor(type="human", name="vektra-seeder")],
        applicability={
            "domains": [domain],
            "problem_signatures": [f"{domain}-pipeline"],
            "keywords": [gid, domain],
        },
        evaluation_score={"reference_tasks": float(avg_score)},
    )
    genome = Genome(
        manifest=manifest,
        framework={
            "id": gid,
            "inputs": ["context"],
            "steps": [
                {"id": "ingest", "name": "ingest", "description": "load inputs"},
                {"id": "reason", "name": "reason", "description": "apply domain rules"},
                {"id": "emit", "name": "emit", "description": "write report"},
            ],
        },
        reasoning_patterns={"primary": f"{domain}-loop"},
        provenance=GenomeProvenance(improvements=improvements),
    )
    genome.finalize()
    saved_path = registry.save(genome)

    # Write the confidence sidecar so the listing reflects the target tier.
    rating = ConfidenceRating(
        stars=target_stars,
        encounters=encounters,
        success_rate=success_rate,
        avg_score=avg_score,
        last_used=now.isoformat(),
    )
    (saved_path / SIDECAR_NAME).write_text(rating.to_json(), encoding="utf-8")

    return genome, saved_path


def write_poisoned_genome(home: Path) -> Path:
    """Drop a malformed genome dir straight into B's home: bundles a shebang
    script that should trip NoExecutables."""
    bad_dir = home / "genomes" / "poisoned-payload" / "1.0.0"
    bad_dir.mkdir(parents=True, exist_ok=True)

    manifest_yaml = (
        "id: poisoned-payload\n"
        "version: 1.0.0\n"
        "content_hash: sha256:" + "ab" * 32 + "\n"
        f"created: {datetime.now(timezone.utc).isoformat()}\n"
        "schema_version: '1.0'\n"
    )
    (bad_dir / "manifest.yaml").write_text(manifest_yaml, encoding="utf-8")
    (bad_dir / "manifest.json").write_text(
        '{"id":"poisoned-payload","version":"1.0.0","content_hash":"sha256:'
        + "ab" * 32
        + '","created":"'
        + datetime.now(timezone.utc).isoformat()
        + '"}',
        encoding="utf-8",
    )
    (bad_dir / "exfil.sh").write_text(
        "#!/bin/sh\necho 'dragonsplague: ' $(whoami)\n", encoding="utf-8"
    )
    return bad_dir


# ─────────────────────────────────────────────────────────────────────
# Event subscription
# ─────────────────────────────────────────────────────────────────────


def subscribe_ribbons(instance_for_pool: dict) -> None:
    """Wire every federation event onto the chat-style ribbon.

    instance_for_pool maps pool.name -> instance label key so PoolIngest
    can attribute correctly.
    """

    def on_peer_started(e: PeerSyncStarted) -> None:
        ribbon("C", "PeerSyncStarted", f"peer={e.peer_id}", accent="yellow")

    def on_peer_done(e: PeerSyncCompleted) -> None:
        ribbon(
            "C",
            "PeerSyncCompleted",
            f"peer={e.peer_id} submitted={e.submitted} errors={e.errors} "
            f"took={e.duration_ms}ms",
            accent="yellow",
        )

    def on_qsubmit(e: QuarantineSubmitted) -> None:
        ribbon(
            "C",
            "QuarantineSubmitted",
            f"qid={e.quarantine_id[:8]} genome={e.genome_id or '?'} "
            f"src={e.source_peer}",
            accent="magenta",
        )

    def on_qval(e: QuarantineValidated) -> None:
        verdict = "PASS" if e.all_passed else f"FAIL ({','.join(e.failed_rules)})"
        accent = "green" if e.all_passed else "red"
        ribbon(
            "C",
            "QuarantineValidated",
            f"qid={e.quarantine_id[:8]} → {verdict}",
            accent=accent,
        )

    def on_qapprove(e: QuarantineApproved) -> None:
        ribbon(
            "C",
            "QuarantineApproved",
            f"qid={e.quarantine_id[:8]} genome={e.genome_id} by={e.approved_by}",
            accent="green",
        )

    def on_qreject(e: QuarantineRejected) -> None:
        ribbon(
            "C",
            "QuarantineRejected",
            f"qid={e.quarantine_id[:8]} reason={e.reason}",
            accent="red",
        )

    def on_pool_ingest(e: PoolIngest) -> None:
        ribbon(
            "C",
            "PoolIngest",
            f"genome={e.genome_id} src={e.source}",
            accent="green",
        )

    def on_inherit(e: InheritanceReceived) -> None:
        ribbon(
            "C",
            "InheritanceReceived",
            f"absorbed={len(e.genomes_absorbed)} "
            f"rejected={len(e.genomes_rejected)} "
            f"sub={e.subagent_id or '?'}",
            accent="cyan",
        )

    default_bus.subscribe(on_peer_started, [PeerSyncStarted])
    default_bus.subscribe(on_peer_done, [PeerSyncCompleted])
    default_bus.subscribe(on_qsubmit, [QuarantineSubmitted])
    default_bus.subscribe(on_qval, [QuarantineValidated])
    default_bus.subscribe(on_qapprove, [QuarantineApproved])
    default_bus.subscribe(on_qreject, [QuarantineRejected])
    default_bus.subscribe(on_pool_ingest, [PoolIngest])
    default_bus.subscribe(on_inherit, [InheritanceReceived])


# ─────────────────────────────────────────────────────────────────────
# Pretty renderers
# ─────────────────────────────────────────────────────────────────────


def render_peer_list(reg: PeerRegistry) -> None:
    rows: List[Tuple[str, str]] = []
    for entry in reg.list():
        rows.append((
            entry.peer_id,
            f"[bold]{entry.trust_level:<9}[/] {entry.address}  "
            f"[dim]notes={entry.notes or '-'}[/]",
        ))
    if not rows:
        rows = [("(none)", "no peers registered")]
    panel(
        f"{LABELS['C']} :: peer registry",
        Section("federated peers", rows, palette=PALETTE, key_width=10),
    )


def render_genome_listing(label_key: str, registry: GenomeRegistry) -> None:
    entries = list_genomes(registry=registry)
    table = Table(
        show_header=True, header_style=f"bold {PALETTE.accent}",
        border_style=PALETTE.muted, expand=False,
    )
    table.add_column("genome_id", style="bold")
    table.add_column("stars", justify="center")
    table.add_column("domains")
    table.add_column("score", justify="right")
    if not entries:
        table.add_row("[dim](empty pool)[/]", "-", "-", "-")
    for e in entries:
        stars = "★" * e.confidence_stars + "·" * (5 - e.confidence_stars)
        table.add_row(
            e.genome_id, stars, ",".join(e.domains) or "-",
            f"{e.score:.2f}",
        )
    panel(f"{LABELS[label_key]} :: pool genomes", table)


def render_validation_table(
    results: List[Tuple[str, bool, str]], qid: str
) -> None:
    rows: List[Tuple[str, str]] = []
    for name, ok, reason in results:
        glyph = Glyphs.CHECK if ok else Glyphs.CROSS
        colour = "green" if ok else "red"
        text = "ok" if ok else (reason or "failed")
        rows.append((name, f"[{colour}]{glyph}[/] {text}"))
    panel(
        f"quarantine validate :: {qid[:8]}",
        Section("validation rules", rows, palette=PALETTE, key_width=18),
    )


# ─────────────────────────────────────────────────────────────────────
# Phases
# ─────────────────────────────────────────────────────────────────────


def phase_setup(workdir: Path) -> dict:
    divider("PHASE 1: SETUP — three isolated AGENTDRIVE_HOMEs")
    homes = {
        "A": workdir / f"fed-A-{os.getpid()}",
        "B": workdir / f"fed-B-{os.getpid()}",
        "C": workdir / f"fed-C-{os.getpid()}",
    }
    for key, home in homes.items():
        init_home(home)
        info(f"{LABELS[key]:<24} home = {home}")
    return homes


def phase_seed(homes: dict) -> dict:
    divider("PHASE 2: SEED — A: 3 security genomes · B: 2 code genomes · C: empty")
    random.seed(0xFED)
    registries: dict = {}

    # A — security domain, 4-5 stars
    with use_home(homes["A"]):
        reg_a = GenomeRegistry()
        seed_genome(reg_a, "incident-postmortem", domain="security",
                    encounters=120, success_rate=0.88, avg_score=0.83, target_stars=5)
        seed_genome(reg_a, "evidence-trace", domain="security",
                    encounters=58, success_rate=0.82, avg_score=0.79, target_stars=4)
        seed_genome(reg_a, "risk-scorer", domain="security",
                    encounters=55, success_rate=0.81, avg_score=0.78, target_stars=4)
        registries["A"] = reg_a
        render_genome_listing("A", reg_a)

    # B — code domain, 4 stars each
    with use_home(homes["B"]):
        reg_b = GenomeRegistry()
        seed_genome(reg_b, "regex-architect", domain="code",
                    encounters=52, success_rate=0.81, avg_score=0.77, target_stars=4)
        seed_genome(reg_b, "sql-explain", domain="code",
                    encounters=54, success_rate=0.80, avg_score=0.76, target_stars=4)
        registries["B"] = reg_b
        render_genome_listing("B", reg_b)

    # C — coordinator, starts empty
    with use_home(homes["C"]):
        reg_c = GenomeRegistry()
        registries["C"] = reg_c
        render_genome_listing("C", reg_c)

    return registries


def phase_configure_peers(homes: dict) -> PeerRegistry:
    divider("PHASE 3: CONFIGURE — register both edge peers on the coordinator")
    with use_home(homes["C"]):
        reg = PeerRegistry()
        reg.add(
            "edge-1",
            f"file://{homes['A']}",
            trust_level="trusted",
            notes="prod edge node west",
        )
        reg.add(
            "edge-2",
            f"file://{homes['B']}",
            trust_level="review",
            notes="prod edge node east, lower trust",
        )
        render_peer_list(reg)
        return reg


def phase_sync_trusted(homes: dict, registries: dict) -> List[str]:
    divider("PHASE 4: FIRST SYNC — trusted peer (edge-1)")
    with use_home(homes["C"]):
        pool_c = AgentDrive(registry=registries["C"], name=LABELS["C"])
        result = sync_peer("edge-1", target_pool=pool_c)
        info(
            f"PeerSyncResult: submitted={result.submitted} "
            f"errors={len(result.errors)} qids={[q[:8] for q in result.quarantine_ids]}"
        )
        q = get_default_quarantine()
        for qid in result.quarantine_ids:
            entry = q.get(qid)
            assert entry is not None
            info(
                f"queued qid={qid[:8]} genome={entry.genome_id} "
                f"sha256={entry.sha256[:12]}… src={entry.source_peer}"
            )
        # NONE may be in the live pool yet.
        assert pool_c.get_pool_stats()["ingest_events"] == 0, (
            "trusted-peer sync must not have ingested anything directly"
        )
        note(
            "verified: 0 direct ingests into C's pool — every candidate "
            "is parked in quarantine"
        )
        return result.quarantine_ids


def phase_validate(homes: dict, qids: List[str]) -> None:
    divider("PHASE 5: VALIDATE — run each quarantine entry through the rule set")
    with use_home(homes["C"]):
        q = get_default_quarantine()
        for qid in qids:
            results = q.validate(qid)
            render_validation_table(results, qid)


def phase_approve(homes: dict, registries: dict, qids: List[str]) -> None:
    divider("PHASE 6: APPROVE — operator releases trusted candidates into C's pool")
    with use_home(homes["C"]):
        pool_c = AgentDrive(registry=registries["C"], name=LABELS["C"])
        q = get_default_quarantine()
        for qid in qids:
            ok = q.approve(qid, pool_c, note="trusted prod edge")
            assert ok, f"approval failed for {qid}"
        render_genome_listing("C", registries["C"])


def phase_sync_lower_trust(homes: dict, registries: dict) -> List[str]:
    divider("PHASE 7: SECOND SYNC — lower-trust peer (edge-2)")
    with use_home(homes["C"]):
        pool_c = AgentDrive(registry=registries["C"], name=LABELS["C"])
        result = sync_peer("edge-2", target_pool=pool_c)
        info(
            f"PeerSyncResult: submitted={result.submitted} "
            f"errors={len(result.errors)} qids={[q[:8] for q in result.quarantine_ids]}"
        )
        return result.quarantine_ids


def phase_poisoned(
    homes: dict, registries: dict, prior_qids: List[str]
) -> None:
    divider("PHASE 8: POISONED CANDIDATE — malformed genome with embedded shebang")
    bad_dir = write_poisoned_genome(homes["B"])
    info(f"injected poisoned genome into edge-2 at {bad_dir}")

    with use_home(homes["C"]):
        pool_c = AgentDrive(registry=registries["C"], name=LABELS["C"])
        # Reset last_sync so the new (poisoned) dir surfaces.
        peer_reg = PeerRegistry()
        peer = peer_reg.get("edge-2")
        assert peer is not None
        peer.last_sync_iso = None
        peer_reg._atomic_write(peer_reg._entry_path("edge-2"), peer.to_dict())

        result = sync_peer("edge-2", target_pool=pool_c)
        info(
            f"re-sync submitted={result.submitted} "
            f"qids={[q[:8] for q in result.quarantine_ids]}"
        )

        # Identify the poisoned qid (one not seen before).
        q = get_default_quarantine()
        new_qids = [qid for qid in result.quarantine_ids if qid not in prior_qids]
        poisoned_qid: Optional[str] = None
        for qid in new_qids:
            entry = q.get(qid)
            if entry and "poisoned" in (entry.genome_id or ""):
                poisoned_qid = qid
                break
            if poisoned_qid is None:
                poisoned_qid = qid

        # Validate it explicitly and render the failure.
        assert poisoned_qid is not None, "expected at least one new qid"
        results = q.validate(poisoned_qid)
        render_validation_table(results, poisoned_qid)

        entry = q.get(poisoned_qid)
        assert entry is not None
        assert entry.status == QuarantineStatus.PENDING, (
            "poisoned entry must remain PENDING"
        )
        assert entry.reasons, "validation reasons must be populated on failure"
        note(
            f"poisoned candidate held in PENDING with reasons: "
            f"{entry.reasons[0]}"
        )

        # Try to approve it — must refuse.
        ok = q.approve(poisoned_qid, pool_c, note="should-be-blocked")
        assert ok is False, "approve must reject a candidate that fails validation"
        note("verified: approve() refused the poisoned candidate — never reached C's pool")


def phase_inheritance(homes: dict, registries: dict) -> None:
    divider("PHASE 9: INHERITANCE — sub-agent manifest with quarantine_external=True")

    # Build the inheritance manifest on C, pointing at a genome B owns.
    with use_home(homes["B"]):
        pool_b = AgentDrive(registry=registries["B"], name=LABELS["B"])

    with use_home(homes["C"]):
        pool_c = AgentDrive(registry=registries["C"], name=LABELS["C"])
        # NOTE on form: GenomeRegistry stores hierarchically at
        # <root>/<id>/<version>/, so the directory id resolvable via
        # registry.get_genome_path() is "regex-architect/1.0.0", NOT the
        # canonical "regex-architect@1.0.0". inheritance.record_manifest
        # hands the raw gid straight into get_genome_path with no @→/
        # normalization (see inheritance.py ~line 217), so the @-form
        # quietly fails with "source dir not resolvable for quarantine".
        # We feed it the dir form here so the demo exercises the happy
        # quarantine route. The rough edge is reported separately.
        manifest = InheritanceManifest(
            subagent_id="vektra-research-1",
            swarm_id="vektra-coord",
            genomes_pulled=[],
            genomes_created=["regex-architect/1.0.0"],
            outcomes_logged=[],
            duration_s=12.5,
        )
        result = record_manifest(
            manifest,
            target_pool=pool_c,
            source_pool=pool_b,
            quarantine_external=True,
        )
        info(
            f"InheritanceResult: absorbed={result.genomes_absorbed} "
            f"rejected={result.genomes_rejected}"
        )
        for gid, reason in result.reason_per_rejected.items():
            info(f"  {gid}: {reason}")
        # quarantine_external means the genome must NOT be in the absorbed list.
        assert result.genomes_absorbed == [], (
            "quarantine_external=True must route through quarantine, not direct ingest"
        )
        assert any("quarantined for review" in r for r in result.reason_per_rejected.values()), (
            "expected a 'quarantined for review' marker in rejection reasons"
        )
        note("verified: inheritance with quarantine_external=True routed through the gate")


def phase_final_state(homes: dict, registries: dict) -> None:
    divider("PHASE 10: FINAL STATE — pool, quarantine, peer registry, reconciliation")
    with use_home(homes["C"]):
        pool_c = AgentDrive(registry=registries["C"], name=LABELS["C"])
        render_genome_listing("C", registries["C"])

        q = get_default_quarantine()
        all_entries = q.list()
        by_status: dict = {}
        for e in all_entries:
            by_status.setdefault(e.status.value, 0)
            by_status[e.status.value] += 1
        rows = [(k, str(v)) for k, v in sorted(by_status.items())]
        panel(
            f"{LABELS['C']} :: quarantine by status",
            Section("counts", rows or [("(empty)", "0")], palette=PALETTE),
        )

        peer_reg = PeerRegistry()
        rows = []
        for entry in peer_reg.list():
            rows.append((
                entry.peer_id,
                f"trust={entry.trust_level:<8} "
                f"last_sync={entry.last_sync_iso or '-'}",
            ))
        panel(
            f"{LABELS['C']} :: peers (post-sync)",
            Section("peers", rows, palette=PALETTE),
        )

        runner = ReconciliationRunner(
            registry=registries["C"], pool=pool_c,
            state_path=homes["C"] / "reconciliation.state.json",
            interval_s=30.0,
        )
        report = runner.scan_once()
        panel(
            f"{LABELS['C']} :: reconciliation",
            Section(
                "scan_once",
                [
                    ("new_genomes", str(len(report.new_genomes))),
                    ("updated", str(len(report.updated_genomes))),
                    ("new_ingests", str(report.new_ingest_events)),
                    ("pending_q", str(report.pending_quarantine)),
                    ("took", f"{report.duration_ms}ms"),
                ],
                palette=PALETTE,
            ),
        )


# ─────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────


def main() -> int:
    CONSOLE.print()
    CONSOLE.print(Panel(
        "[bold cyan]Vektra Federation Deep-Test[/]\n\n"
        "Three AGENTDRIVE_HOMEs · peer trust gate · quarantine inversion · "
        "inheritance routing\n"
        "Hard contract under test: [bold]nothing crosses an instance "
        "boundary without quarantine.[/]",
        border_style="cyan", padding=(1, 2),
    ))

    subscribe_ribbons(instance_for_pool={LABELS["C"]: "C"})

    t0 = time.time()
    with tempfile.TemporaryDirectory(prefix="fed-test-") as td:
        workdir = Path(td)
        homes = phase_setup(workdir)
        registries = phase_seed(homes)
        phase_configure_peers(homes)
        qids_a = phase_sync_trusted(homes, registries)
        phase_validate(homes, qids_a)
        phase_approve(homes, registries, qids_a)
        qids_b = phase_sync_lower_trust(homes, registries)
        phase_poisoned(homes, registries, prior_qids=qids_a + qids_b)
        phase_inheritance(homes, registries)
        phase_final_state(homes, registries)

    elapsed = time.time() - t0
    divider("VERDICT")
    note(f"federation flow completed in {elapsed:.1f}s")
    note(
        "QUARANTINE GATE HELD: peer.trust_level='trusted' did NOT bypass "
        "validation — every cross-instance candidate routed through "
        "Quarantine.submit(); the poisoned genome stayed PENDING after "
        "approve() and never landed in C's pool; inheritance with "
        "quarantine_external=True respected the gate identically."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
