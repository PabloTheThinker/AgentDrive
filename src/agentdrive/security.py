"""
Production security posture helpers for AgentDrive.

Intended for self-hosted / production deployments.
Provides lightweight, actionable checks around permissions, secrets handling,
and overall operational hygiene.

This is deliberately minimal and framework-agnostic — no cloud calls,
no external dependencies beyond the stdlib + existing AgentDrive primitives.

Example usage (also surfaced by `agentdrive doctor` and scripts):

    from agentdrive.security import get_security_posture, print_security_posture

    posture = get_security_posture()
    if posture.overall != "good":
        print("Issues:", posture.issues)
        print("Recommendations:", posture.recommendations)
    print_security_posture()
    # Richer signals now include trust circle size, active grants,
    # reconciliation last-scan, key file perms, and default name hygiene.
    # Expanded: immune/quarantine hygiene, key rotation signals (trust material mtime),
    # reconciliation health depth (scan delta + failure count from state),
    # grants revocation hygiene, and schema_pack evolution proposals touching
    # security-relevant promotion rules — all framed around sovereignty of the
    # user's drive, role-swarm trust boundaries via grants + immune, and
    # experience layer integrity via quarantine signals.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from agentdrive.config import get_agentdrive_home, get_instance_name, load_config
from agentdrive.constants import get_correlation_id, new_correlation_id, using_correlation_id
from agentdrive.events import HealingSignalEvent, emit


@dataclass
class SecurityPosture:
    """Lightweight security posture summary for a running AgentDrive instance.

    Richer but still cheap to compute. Production signals for role-specialized
    swarm stabilization (all optional/defaulted to preserve backward compat):

    - trust_members + has_trust_circle: federation / multi-device hygiene
    - active_grants: lineage sharing / grant usage signal
    - reconciliation_last_scan: background healing loop visibility (if run)
    - instance_name_is_default: warns on "AgentDrive" (should be personalized)

    Expanded signals (Security Posture & Immune Hardening):
    - quarantined_items + recent_quarantine_releases: immune/quarantine directory
      hygiene (count of items held for review, recent releases into pool)
    - key_rotation_signal + trust_self_mtime_age_days: key rotation signals
      (trust/self.json or pending.pem mtime age for rotation hygiene)
    - reconciliation_last_scan_delta_hours + reconciliation_failure_count:
      reconciliation health depth (last successful scan delta + failure count
      persisted in state)
    - revoked_grants: grants revocation hygiene (role-swarm trust boundaries)
    - schema_evolution_security_proposals + schema_evolution_security_details:
      schema_pack evolution proposals that touch security-relevant promotion
      rules (experience layer integrity)

    All framed strictly for sovereignty of the user's drive and explicit
    role-swarm trust boundaries via grants + immune.
    """

    instance_name: str
    home_path: Path
    sensitive_files_ok: bool
    issues: list[str]
    recommendations: list[str]
    overall: str  # "good", "needs_attention", "unknown"
    # Additional lightweight production signals (defaults keep backward compat)
    trust_members: int = 0
    active_grants: int = 0
    reconciliation_last_scan: str | None = None
    has_trust_circle: bool = False
    instance_name_is_default: bool = True

    # Immune / quarantine directory hygiene (experience layer integrity via quarantine signals)
    quarantined_items: int = 0
    recent_quarantine_releases: int = 0

    # Key rotation signals (role-swarm trust boundaries via grants + immune)
    key_rotation_signal: str | None = None
    trust_self_mtime_age_days: float | None = None

    # Reconciliation health depth (last successful scan delta + failure count from state)
    reconciliation_last_scan_delta_hours: float | None = None
    reconciliation_failure_count: int = 0

    # Grants revocation hygiene (role-swarm trust boundaries)
    revoked_grants: int = 0

    # Schema pack evolution proposals touching security-relevant promotion rules
    schema_evolution_security_proposals: int = 0
    schema_evolution_security_details: list[str] = field(default_factory=list)


SENSITIVE_FILES = [
    ".env",
    "auth.db",
    "caps.db",
    "dna/_ancestry.db",
    "grants.db",
    # Key material (trust roots contain private PEMs; pending used during bootstrap)
    "trust/self.json",
    "trust/pending.pem",
]


def _check_file_permissions(path: Path) -> tuple[bool, str]:
    """Return (is_tight, current_mode). Tight means 600 or 700."""
    if not path.exists():
        return True, "absent"
    try:
        mode = oct(path.stat().st_mode)[-3:]
        is_tight = mode in ("600", "700")
        return is_tight, mode
    except Exception as e:
        return False, f"error: {e}"


def get_security_posture() -> SecurityPosture:
    """
    Return a production-oriented security posture for the current AgentDrive instance.

    Checks (expanded for production hardening and role-specialized swarms):
    - Permissions on known sensitive files (DBs holding keys, .env, trust material).
    - Basic trust store hygiene (circle initialized? member count).
    - Basic grants hygiene (active non-revoked grant count via lightweight sqlite).
    - Key file existence + tight permission checks (trust/*.pem/json + .env).
    - Instance name hygiene (warning if still the default "AgentDrive").
    - Simple reconciliation health signal (last_scan from state file, if available).
    - Config + home presence.
    - Immune/quarantine directory hygiene (count of quarantined items + recent releases).
    - Key rotation signals (trust/self.json or pending mtime age).
    - Reconciliation health depth (last successful scan delta + failure count from state).
    - Grants revocation hygiene (count of revoked entries).
    - Schema pack evolution proposals touching security-relevant promotion rules
      (quarantine/immune/trust/experience layer).

    This is intentionally lightweight (stdlib + public primitives only).
    For deeper audits, combine with external tools (filesystem scanners, etc).
    """
    home = get_agentdrive_home()
    issues: list[str] = []
    recommendations: list[str] = []

    # Resolve via config (respects persisted name + env fallback) for accurate hygiene
    instance_name = get_instance_name()
    instance_name_is_default = instance_name == "AgentDrive"

    # Richer signals (populated in try blocks below)
    trust_members = 0
    has_trust_circle = False
    active_grants = 0
    recon_last_scan: str | None = None

    # New expanded signals for immune/quarantine, key rotation, recon depth,
    # grants revocation, and schema_pack security proposals. Populated below.
    # All checks defend sovereignty of the user's drive and role-swarm
    # trust boundaries via grants + immune.
    quarantined_items = 0
    recent_quarantine_releases = 0
    key_rotation_signal: str | None = None
    trust_self_mtime_age_days: float | None = None
    recon_delta_hours: float | None = None
    recon_failure_count = 0
    revoked_grants = 0
    schema_sec_proposals = 0
    schema_sec_details: list[str] = []

    # Basic home sanity
    if not home.exists() or not home.is_dir():
        issues.append("AgentDrive home directory missing or not a directory")
        recommendations.append("Run `agentdrive doctor` or the onboarding flow")
        return SecurityPosture(
            instance_name=instance_name,
            home_path=home,
            sensitive_files_ok=False,
            issues=issues,
            recommendations=recommendations,
            overall="unknown",
            # new fields use dataclass defaults
        )

    # Check sensitive files (now includes explicit key material paths)
    sensitive_ok = True
    for name in SENSITIVE_FILES:
        p = home / name
        ok, mode = _check_file_permissions(p)
        if not ok:
            sensitive_ok = False
            issues.append(f"{name} has loose permissions ({mode})")
            recommendations.append(f"chmod 600 {p}")

    # Instance naming hygiene (soft but important production identity signal)
    if instance_name_is_default:
        recommendations.append(
            "Set AGENTDRIVE_INSTANCE_NAME (or config.yaml agentdrive.instance_name) "
            "so this runtime has a clear identity"
        )

    # Config presence
    cfg = load_config()
    if not cfg:
        issues.append("No user config found (using only defaults)")
        recommendations.append("Run `agentdrive setup` or create config.yaml")

    # Basic trust store hygiene (production federation signal)
    try:
        from agentdrive.trust.store import TrustStore

        ts = TrustStore()
        member_count = len(ts.members)
        has_circle = ts.self_identity is not None
        trust_members = member_count
        has_trust_circle = has_circle
        if not has_circle:
            recommendations.append(
                "No local trust circle initialized — consider `peers trust` / "
                "federation setup for multi-device use"
            )
        else:
            recommendations.append(
                f"Trust circle active ({trust_members} member(s) including self)"
            )
    except Exception:
        pass

    # Basic grants hygiene (lineage sharing signal) — stdlib sqlite, no private APIs
    # Expanded for revocation hygiene (role-swarm trust boundaries via grants + immune)
    try:
        grants_db = home / "grants.db"
        if grants_db.exists():
            import sqlite3

            with sqlite3.connect(grants_db) as conn:
                conn.row_factory = sqlite3.Row
                row = conn.execute("SELECT COUNT(*) as c FROM grants WHERE revoked = 0").fetchone()
                gcount = int(row["c"]) if row else 0
                row_rev = conn.execute(
                    "SELECT COUNT(*) as c FROM grants WHERE revoked = 1"
                ).fetchone()
                rcount = int(row_rev["c"]) if row_rev else 0
            active_grants = gcount
            revoked_grants = rcount
            recommendations.append(f"{active_grants} active (non-revoked) lineage grants")
            if revoked_grants > 0:
                recommendations.append(
                    f"{revoked_grants} revoked grants (revocation hygiene active)"
                )
        else:
            recommendations.append("grants.db absent — no lineage share grants issued yet")
    except Exception:
        pass

    # Explicit key file existence + permission checks (trust roots + env hold real secrets)
    key_files = [home / "trust" / "self.json", home / ".env"]
    for kf in key_files:
        if kf.exists():
            ok, mode = _check_file_permissions(kf)
            if not ok:
                issues.append(f"Key file {kf.name} has loose permissions ({mode})")
                recommendations.append(f"chmod 600 {kf}")

    # Key rotation signals: mtime age of trust material (self.json primary, pending for bootstrap)
    # Supports detection of stale keys in role-swarm trust boundaries.
    try:
        from datetime import UTC, datetime

        trust_dir = home / "trust"
        self_json = trust_dir / "self.json"
        if self_json.exists():
            mtime = datetime.fromtimestamp(self_json.stat().st_mtime, tz=UTC)
            age_days = (datetime.now(UTC) - mtime).total_seconds() / 86400.0
            trust_self_mtime_age_days = round(age_days, 1)
            key_rotation_signal = f"self.json mtime age: {trust_self_mtime_age_days:.1f}d"
            recommendations.append(f"Key rotation signal: {key_rotation_signal}")
            if age_days > 90:
                recommendations.append(
                    "Consider key rotation (self.json >90d old) for role-swarm trust hygiene"
                )
        pending = trust_dir / "pending.pem"
        if pending.exists() and not self_json.exists():
            mtime = datetime.fromtimestamp(pending.stat().st_mtime, tz=UTC)
            age_days = (datetime.now(UTC) - mtime).total_seconds() / 86400.0
            key_rotation_signal = f"pending.pem (bootstrap) age: {round(age_days, 1)}d"
    except Exception:
        pass

    # Immune / quarantine directory hygiene (count of quarantined items, recent releases)
    # Directly protects experience layer integrity via quarantine signals and
    # sovereignty of the user's drive: every external genome is gated here.
    try:
        from agentdrive.quarantine import QuarantineStatus, get_default_quarantine

        q = get_default_quarantine()
        all_entries = q.list()
        quarantined_items = sum(
            1
            for e in all_entries
            if e.status in (QuarantineStatus.PENDING, QuarantineStatus.QUARANTINED)
        )
        # Recent releases: count APPROVED entries whose log or received time indicates recent activity.
        # Lightweight: scan log.jsonl for recent "approve" actions (last ~10 lines, 7d window).
        recent_releases = 0
        log_path = q.log_path
        if log_path.exists():
            try:
                from datetime import UTC, datetime, timedelta

                cutoff = datetime.now(UTC) - timedelta(days=7)
                lines = log_path.read_text(encoding="utf-8").strip().splitlines()[-30:]
                for line in lines:
                    if not line.strip():
                        continue
                    try:
                        rec = __import__("json").loads(line)
                        if rec.get("action") == "approve":
                            ts = rec.get("timestamp")
                            if ts:
                                dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
                                if dt >= cutoff:
                                    recent_releases += 1
                    except Exception:
                        continue
                recent_quarantine_releases = recent_releases
            except Exception:
                pass
        if quarantined_items > 0:
            recommendations.append(
                f"Quarantine hygiene: {quarantined_items} items pending/held review"
            )
        if recent_quarantine_releases > 0:
            recommendations.append(f"{recent_quarantine_releases} recent quarantine releases (7d)")
    except Exception:
        pass

    # Simple reconciliation health signal if the module/state is available
    # Expanded to health depth: last successful scan delta + failure count from state.
    try:
        from agentdrive.reconciliation import STATE_FILENAME

        state_path = home / STATE_FILENAME
        if state_path.exists() and state_path.is_file():
            import json
            from datetime import UTC, datetime

            data = json.loads(state_path.read_text(encoding="utf-8"))
            last = data.get("last_scan_iso")
            recon_last_scan = last
            recon_failure_count = int(data.get("consecutive_failures", 0) or 0)
            epoch = "1970-01-01T00:00:00+00:00"
            if last and last != epoch:
                recommendations.append(f"Reconciliation last scan: {last}")
                try:
                    last_dt = datetime.fromisoformat(last.replace("Z", "+00:00"))
                    if last_dt.tzinfo is None:
                        last_dt = last_dt.replace(tzinfo=UTC)
                    delta_h = (datetime.now(UTC) - last_dt).total_seconds() / 3600.0
                    recon_delta_hours = round(delta_h, 1)
                    recommendations.append(
                        f"Reconciliation health depth: {recon_delta_hours:.1f}h since last scan, {recon_failure_count} failures in state"
                    )
                    if delta_h > 48:
                        recommendations.append(
                            "Reconciliation stale (>48h) — run `agentdrive reconcile run` or check background loop"
                        )
                except Exception:
                    pass
            else:
                recommendations.append("Reconciliation state present (no completed scan)")
        else:
            recommendations.append(
                "No reconciliation.json — run `agentdrive reconcile run` to enable "
                "background healing signal"
            )
    except Exception:
        pass

    # Schema pack evolution proposals touching security-relevant promotion rules.
    # Lightweight bounded scan for proposals that could affect promotion gates
    # (quarantine/immune/trust/experience layer integrity).
    try:
        from datetime import UTC, datetime, timedelta

        sec_keywords = (
            "quarantine",
            "immune",
            "trust",
            "grant",
            "revoked",
            "promotion",
            "experience layer",
            "role-swarm",
        )
        candidates: list[str] = []
        scan_roots = [
            home / "schema_packs",
            home / "genomes",
            home / "quarantine" / "entries",
        ]
        cutoff = datetime.now(UTC) - timedelta(days=30)
        for root in scan_roots:
            if not root.exists():
                continue
            for p in list(root.rglob("*.yaml"))[:20] + list(root.rglob("*.json"))[:20]:
                if not p.is_file():
                    continue
                try:
                    if p.stat().st_mtime < cutoff.timestamp():
                        continue
                    text = p.read_text(encoding="utf-8", errors="ignore").lower()
                    if "schema-pack-evolution" in text or "evolution proposal" in text:
                        if any(kw in text for kw in sec_keywords):
                            detail = f"{p.parent.name}/{p.name}"
                            if detail not in candidates:
                                candidates.append(detail)
                except Exception:
                    continue
        schema_sec_proposals = len(candidates)
        schema_sec_details = candidates[:5]
        if schema_sec_proposals > 0:
            recommendations.append(
                f"{schema_sec_proposals} schema evolution proposal(s) touching security-relevant promotion rules"
            )
    except Exception:
        pass

    overall = "good" if not issues else "needs_attention"

    # Minor wiring for synthesis damage signals + security posture (HealingFactor integration):
    # When posture signals needs_attention, emit first-class HealingSignalEvent so
    # the Regenerative HealingFactor Operator can autonomously diagnose + propose
    # experience layer regeneration under durable healing phase (schema-pack governed).
    if overall == "needs_attention":
        try:
            cid = get_correlation_id() or new_correlation_id()
            with using_correlation_id(cid):
                emit(
                    HealingSignalEvent(
                        signal_type="security_posture_needs_attention",
                        correlation_id=cid,
                        context={
                            "issues": issues[:5],
                            "recommendations": recommendations[:3],
                            "source_component": "security_posture",
                            "swarm_context": "healing-regeneration",
                        },
                        source_component="security",
                        recommended_priority="high",
                    )
                )
        except Exception:
            # Best-effort; never breaks posture query (non-fatal root preserved).
            pass

    return SecurityPosture(
        instance_name=instance_name,
        home_path=home,
        sensitive_files_ok=sensitive_ok,
        issues=issues,
        recommendations=recommendations,
        overall=overall,
        trust_members=trust_members,
        active_grants=active_grants,
        reconciliation_last_scan=recon_last_scan,
        has_trust_circle=has_trust_circle,
        instance_name_is_default=instance_name_is_default,
        quarantined_items=quarantined_items,
        recent_quarantine_releases=recent_quarantine_releases,
        key_rotation_signal=key_rotation_signal,
        trust_self_mtime_age_days=trust_self_mtime_age_days,
        reconciliation_last_scan_delta_hours=recon_delta_hours,
        reconciliation_failure_count=recon_failure_count,
        revoked_grants=revoked_grants,
        schema_evolution_security_proposals=schema_sec_proposals,
        schema_evolution_security_details=schema_sec_details,
    )


def print_security_posture() -> None:
    """Convenience printer for CLI / doctor use."""
    from rich.console import Console
    from rich.table import Table

    posture = get_security_posture()
    console = Console()

    table = Table(title=f"{posture.instance_name} — Security Posture")
    table.add_column("Check", style="bold")
    table.add_column("Status")
    table.add_column("Notes")

    table.add_row(
        "Instance",
        posture.instance_name,
        "user-chosen"
        if not posture.instance_name_is_default
        else "default (set via config or env)",
    )
    table.add_row(
        "Home", str(posture.home_path), "exists" if posture.home_path.exists() else "missing"
    )
    table.add_row(
        "Sensitive files",
        "tight" if posture.sensitive_files_ok else "issues",
        ", ".join(posture.issues) or "all good",
    )
    table.add_row(
        "Trust circle",
        "active" if posture.has_trust_circle else "none",
        f"{posture.trust_members} member(s)"
        if posture.has_trust_circle
        else "no multi-device federation",
    )
    table.add_row(
        "Lineage grants",
        str(posture.active_grants),
        "active non-revoked" if posture.active_grants else "none issued",
    )
    table.add_row(
        "Grants revocation",
        str(posture.revoked_grants),
        "revoked (hygiene via grants + immune)"
        if posture.revoked_grants
        else "no revocations recorded",
    )
    if posture.reconciliation_last_scan:
        table.add_row(
            "Reconciliation",
            "scanned",
            posture.reconciliation_last_scan,
        )
    # Expanded hygiene rows for role-swarm stabilization
    table.add_row(
        "Quarantine hygiene",
        str(posture.quarantined_items),
        f"{posture.recent_quarantine_releases} recent releases (7d); experience layer integrity gate"
        if posture.quarantined_items or posture.recent_quarantine_releases
        else "no pending/held items",
    )
    if posture.key_rotation_signal:
        table.add_row(
            "Key rotation",
            "observed",
            f"{posture.key_rotation_signal} (trust material age for role-swarm boundaries)",
        )
    if posture.reconciliation_last_scan_delta_hours is not None:
        table.add_row(
            "Recon health depth",
            f"{posture.reconciliation_last_scan_delta_hours:.1f}h",
            f"{posture.reconciliation_failure_count} failures (from state)",
        )
    if posture.schema_evolution_security_proposals > 0:
        table.add_row(
            "Schema evolution (security)",
            str(posture.schema_evolution_security_proposals),
            "; ".join(posture.schema_evolution_security_details)
            or "proposals touch promotion rules",
        )
    table.add_row(
        "Overall",
        posture.overall,
        " | ".join(posture.recommendations) or "looks solid",
    )

    console.print(table)


__all__ = ["SecurityPosture", "get_security_posture", "print_security_posture"]
