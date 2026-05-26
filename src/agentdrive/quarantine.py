"""Trust-gated quarantine for externally-sourced Agent DNA.

Every genome that arrives from a non-local source — a sub-agent's
inheritance manifest, a peer Agent Drive's reconciliation, a federated pull —
MUST land here first. Quarantine validates the candidate against a
configurable rule set before any release into the live pool.

The module sits in FRONT of `AgentDrive.ingest`. Approval is the only
release path; rejection and indefinite hold are explicit dead-ends.
There is no "skip quarantine" flag exposed from the public API.

On-disk layout (under $AGENTDRIVE_HOME/quarantine/):
    entries/<quarantine_id>.json   — entry metadata
    candidates/<quarantine_id>/    — the genome dir as received (copy)
    log.jsonl                      — append-only audit log of every
                                     transition (submit / validate /
                                     approve / reject / hold)

Module API:
    QuarantineStatus            — enum lifecycle states
    QuarantineEntry             — persisted record per candidate
    ValidationRule              — base class for a single check
    SchemaValid, SizeLimit,     — built-in rules registered by default
    NoExecutables, PromptSanity,
    SignatureValid
    Quarantine                  — coordinator: submit / list / get /
                                  validate / approve / reject / hold
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import shutil
import threading
import uuid
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import TYPE_CHECKING, Any

import yaml

from agentdrive.constants import get_agentdrive_home
from agentdrive.events import (
    QuarantineApproved,
    QuarantineRejected,
    QuarantineSubmitted,
    QuarantineValidated,
    emit,
)

if TYPE_CHECKING:
    from agentdrive.drive.drive import AgentDrive

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────
# Status + entry record
# ─────────────────────────────────────────────────────────────────────


class QuarantineStatus(StrEnum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    QUARANTINED = "quarantined"


def _utc_now_iso() -> str:
    return datetime.now(UTC).isoformat()


@dataclass
class QuarantineEntry:
    quarantine_id: str
    genome_id: str
    source_peer: str
    received_at: str
    status: QuarantineStatus
    reasons: list[str]
    genome_dir: Path
    sha256: str

    # ---- serialization helpers ----

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["status"] = self.status.value
        d["genome_dir"] = str(self.genome_dir)
        return d

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> QuarantineEntry:
        return cls(
            quarantine_id=str(data["quarantine_id"]),
            genome_id=str(data.get("genome_id", "")),
            source_peer=str(data.get("source_peer", "")),
            received_at=str(data.get("received_at", _utc_now_iso())),
            status=QuarantineStatus(data.get("status", "pending")),
            reasons=list(data.get("reasons") or []),
            genome_dir=Path(data.get("genome_dir", "")),
            sha256=str(data.get("sha256", "")),
        )


# ─────────────────────────────────────────────────────────────────────
# Validation rules
# ─────────────────────────────────────────────────────────────────────


class ValidationRule:
    """Base class for a single validation check.

    Subclasses set `name` and implement `check(genome_dir) -> (ok, reason)`.
    A passing rule returns (True, ""); a failing rule returns (False, "...").
    Rules MUST be defensive: any unexpected exception is treated as a
    failure (the wrapper in Quarantine catches and records it).
    """

    name: str = "rule"

    def check(self, genome_dir: Path) -> tuple[bool, str]:
        raise NotImplementedError


_REQUIRED_MANIFEST_FIELDS = ("id", "version", "content_hash", "created")


class SchemaValid(ValidationRule):
    """Manifest.yaml (or .json) parses and contains required fields."""

    name = "schema_valid"

    def check(self, genome_dir: Path) -> tuple[bool, str]:
        manifest_path: Path | None = None
        for cand in ("manifest.yaml", "manifest.json"):
            p = genome_dir / cand
            if p.is_file():
                manifest_path = p
                break
        if manifest_path is None:
            return False, "no manifest.yaml or manifest.json"

        try:
            raw_text = manifest_path.read_text(encoding="utf-8")
            if manifest_path.suffix == ".yaml":
                raw: Any = yaml.safe_load(raw_text) or {}
            else:
                raw = json.loads(raw_text)
        except Exception as exc:
            return False, f"manifest parse failed: {exc}"

        if isinstance(raw, dict) and "genome" in raw and isinstance(raw["genome"], dict):
            raw = raw["genome"]
        if not isinstance(raw, dict):
            return False, "manifest is not a mapping"

        missing = [f for f in _REQUIRED_MANIFEST_FIELDS if not raw.get(f)]
        if missing:
            return False, f"missing required field(s): {', '.join(missing)}"
        return True, ""


class SizeLimit(ValidationRule):
    """Total directory size must be <= max_bytes (default 5 MB)."""

    name = "size_limit"

    def __init__(self, max_bytes: int = 5 * 1024 * 1024) -> None:
        self.max_bytes = int(max_bytes)

    def check(self, genome_dir: Path) -> tuple[bool, str]:
        total = 0
        for root, _dirs, files in os.walk(genome_dir):
            for fname in files:
                try:
                    total += (Path(root) / fname).stat().st_size
                except OSError:
                    continue
                if total > self.max_bytes:
                    return False, (f"size exceeds limit: {total} > {self.max_bytes} bytes")
        return True, ""


_EXECUTABLE_SUFFIXES = (".so", ".dll", ".dylib")


class NoExecutables(ValidationRule):
    """Reject native shared objects or files starting with a shebang.

    The shebang check is intentionally crude: it catches the obvious
    "drop a script and rely on it being executed" case without trying
    to be a sandbox.
    """

    name = "no_executables"

    def check(self, genome_dir: Path) -> tuple[bool, str]:
        for root, _dirs, files in os.walk(genome_dir):
            for fname in files:
                fp = Path(root) / fname
                if fname.lower().endswith(_EXECUTABLE_SUFFIXES):
                    return False, f"executable artifact present: {fp.name}"
                try:
                    with open(fp, "rb") as fh:
                        head = fh.read(2)
                except OSError:
                    continue
                if head == b"#!":
                    return False, f"shebang detected in {fp.name}"
        return True, ""


_PROMPT_INJECTION_PATTERNS = (
    re.compile(r"ignore (?:all )?(?:previous|prior|above) instructions", re.I),
    re.compile(r"disregard (?:all )?(?:previous|prior|above) instructions", re.I),
    re.compile(r"you are now (?:a )?(?:dan|developer mode|jailbroken)", re.I),
    re.compile(r"system prompt[: ]+", re.I),
    re.compile(r"\bprompt injection\b", re.I),
    re.compile(r"</?\s*system\s*>", re.I),
)


class PromptSanity(ValidationRule):
    """Catch obvious prompt-injection strings in text-ish files.

    Not a security boundary — just a tripwire for the laziest attempts.
    """

    name = "prompt_sanity"
    _TEXT_SUFFIXES = (".yaml", ".yml", ".json", ".md", ".txt", ".jsonl")

    def check(self, genome_dir: Path) -> tuple[bool, str]:
        for root, _dirs, files in os.walk(genome_dir):
            for fname in files:
                if not fname.lower().endswith(self._TEXT_SUFFIXES):
                    continue
                fp = Path(root) / fname
                try:
                    text = fp.read_text(encoding="utf-8", errors="ignore")
                except OSError:
                    continue
                for pat in _PROMPT_INJECTION_PATTERNS:
                    if pat.search(text):
                        return False, (f"prompt-injection pattern in {fp.name}: {pat.pattern}")
        return True, ""


class SignatureValid(ValidationRule):
    """Verify a signature file's well-formedness if present.

    v1 STUB: real key-based verification lands when we have a trust
    store (see proposal #6 in POOL-EVOLUTION.md). For now we only
    confirm any `signature.json` parses and carries the minimum fields
    (`algorithm`, `signature`). Absence of a signature is *not* a
    failure — peers without keys are still legal in v1.
    """

    name = "signature_valid"
    _REQUIRED_SIG_FIELDS = ("algorithm", "signature")

    def check(self, genome_dir: Path) -> tuple[bool, str]:
        sig_path = genome_dir / "signature.json"
        if not sig_path.is_file():
            return True, ""  # absence is allowed in v1
        try:
            payload = json.loads(sig_path.read_text(encoding="utf-8"))
        except Exception as exc:
            return False, f"signature.json parse failed: {exc}"
        if not isinstance(payload, dict):
            return False, "signature.json is not an object"
        missing = [f for f in self._REQUIRED_SIG_FIELDS if not payload.get(f)]
        if missing:
            return False, f"signature missing field(s): {', '.join(missing)}"
        return True, ""


def _default_rules() -> list[ValidationRule]:
    return [
        SchemaValid(),
        SizeLimit(),
        NoExecutables(),
        PromptSanity(),
        SignatureValid(),
    ]


# ─────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────


def _sha256_of_dir(path: Path) -> str:
    """Stable content hash over file paths + bytes for dedup / integrity.

    Walks in sorted order so the same directory contents always hash to
    the same digest, regardless of fs ordering.
    """
    h = hashlib.sha256()
    base = Path(path)
    files: list[Path] = []
    for root, _dirs, fnames in os.walk(base):
        for fn in fnames:
            files.append(Path(root) / fn)
    for fp in sorted(files, key=lambda p: str(p.relative_to(base))):
        rel = str(fp.relative_to(base)).encode("utf-8")
        h.update(rel)
        h.update(b"\x00")
        try:
            with open(fp, "rb") as fh:
                for chunk in iter(lambda: fh.read(65536), b""):
                    h.update(chunk)
        except OSError:
            continue
        h.update(b"\x00")
    return h.hexdigest()


def _read_genome_id_from_manifest(genome_dir: Path) -> str:
    """Best-effort read of `id@version` from manifest. Returns "" on failure.

    Searches at the dir root first; falls back to one level of subdirs so
    versioned layouts (``<genome>/<version>/manifest.json``, as written by
    GenomeRegistry) still resolve.
    """
    search_dirs = [genome_dir]
    try:
        search_dirs.extend(p for p in genome_dir.iterdir() if p.is_dir())
    except Exception:
        pass

    for d in search_dirs:
        for cand in ("manifest.yaml", "manifest.json"):
            p = d / cand
            if not p.is_file():
                continue
            try:
                raw_text = p.read_text(encoding="utf-8")
                raw: Any = yaml.safe_load(raw_text) if p.suffix == ".yaml" else json.loads(raw_text)
            except Exception:
                return ""
            if isinstance(raw, dict) and "genome" in raw and isinstance(raw["genome"], dict):
                raw = raw["genome"]
            if isinstance(raw, dict):
                gid = str(raw.get("id") or "").strip()
                ver = str(raw.get("version") or "").strip()
                if gid and ver:
                    return f"{gid}@{ver}"
                if gid:
                    return gid
    return ""


# ─────────────────────────────────────────────────────────────────────
# Quarantine coordinator
# ─────────────────────────────────────────────────────────────────────


class Quarantine:
    """Trust-gated holding area for externally-sourced genomes."""

    def __init__(
        self,
        root: Path | str | None = None,
        rules: list[ValidationRule] | None = None,
    ) -> None:
        if root is None:
            root = get_agentdrive_home() / "quarantine"
        self.root = Path(root)
        self.entries_dir = self.root / "entries"
        self.candidates_dir = self.root / "candidates"
        self.log_path = self.root / "log.jsonl"
        self.entries_dir.mkdir(parents=True, exist_ok=True)
        self.candidates_dir.mkdir(parents=True, exist_ok=True)
        self.rules: list[ValidationRule] = list(rules) if rules else _default_rules()
        # Guards write-side operations (submit / approve / reject / hold).
        # The dedup-then-create path in submit() races without this — three
        # concurrent submits of the same content all see an empty list and
        # each create a fresh entry.
        self._lock = threading.Lock()

    # ---- audit log ----

    def _append_log(self, action: str, entry: QuarantineEntry, **extra: Any) -> None:
        record = {
            "timestamp": _utc_now_iso(),
            "action": action,
            "quarantine_id": entry.quarantine_id,
            "genome_id": entry.genome_id,
            "source_peer": entry.source_peer,
            "status": entry.status.value,
            "sha256": entry.sha256,
        }
        record.update(extra)
        try:
            with open(self.log_path, "a", encoding="utf-8") as fh:
                fh.write(json.dumps(record, default=str) + "\n")
        except Exception:
            logger.debug("failed to append quarantine audit log", exc_info=True)

    # ---- persistence ----

    def _entry_path(self, quarantine_id: str) -> Path:
        return self.entries_dir / f"{quarantine_id}.json"

    def _save_entry(self, entry: QuarantineEntry) -> None:
        self._entry_path(entry.quarantine_id).write_text(
            json.dumps(entry.to_dict(), indent=2, default=str), encoding="utf-8"
        )

    def _load_entry(self, quarantine_id: str) -> QuarantineEntry | None:
        p = self._entry_path(quarantine_id)
        if not p.is_file():
            return None
        try:
            return QuarantineEntry.from_dict(json.loads(p.read_text(encoding="utf-8")))
        except Exception:
            logger.debug("failed to load quarantine entry %s", p, exc_info=True)
            return None

    # ---- submit ----

    def submit(self, genome_dir: Path | str, source_peer: str) -> QuarantineEntry:
        """Place an externally-sourced genome dir into quarantine.

        Copies the dir under candidates/<quarantine_id>/, computes a
        sha256 for integrity + dedup, writes the entry, and emits
        QuarantineSubmitted. If a prior entry exists with the same
        content hash, returns that entry instead (dedup).
        """
        src = Path(genome_dir)
        if not src.is_dir():
            raise FileNotFoundError(f"quarantine.submit: not a directory: {src}")

        sha = _sha256_of_dir(src)

        # Lock the dedup-check-and-create section so concurrent submits of
        # the same content collapse to a single entry rather than racing.
        with self._lock:
            for prior in self.list():
                if prior.sha256 == sha:
                    return prior

            qid = uuid.uuid4().hex
            candidate_dir = self.candidates_dir / qid
            shutil.copytree(src, candidate_dir)

            entry = QuarantineEntry(
                quarantine_id=qid,
                genome_id=_read_genome_id_from_manifest(candidate_dir),
                source_peer=str(source_peer or "unknown"),
                received_at=_utc_now_iso(),
                status=QuarantineStatus.PENDING,
                reasons=[],
                genome_dir=candidate_dir,
                sha256=sha,
            )
            self._save_entry(entry)
            self._append_log("submit", entry)

        try:
            emit(
                QuarantineSubmitted(
                    quarantine_id=qid,
                    genome_id=entry.genome_id,
                    source_peer=entry.source_peer,
                )
            )
        except Exception:
            logger.debug("failed to emit QuarantineSubmitted", exc_info=True)

        return entry

    # ---- list / get ----

    def list(self, status: QuarantineStatus | None = None) -> list[QuarantineEntry]:
        out: list[QuarantineEntry] = []
        if not self.entries_dir.is_dir():
            return out
        for p in sorted(self.entries_dir.glob("*.json")):
            e = self._load_entry(p.stem)
            if e is None:
                continue
            if status is not None and e.status != status:
                continue
            out.append(e)
        return out

    def get(self, quarantine_id: str) -> QuarantineEntry | None:
        return self._load_entry(quarantine_id)

    # ---- validate ----

    def validate(self, quarantine_id: str) -> list[tuple[str, bool, str]]:
        """Run every registered rule against the candidate.

        Returns a list of (rule_name, ok, reason). Updates the entry's
        `reasons` to the human-readable failure messages and emits
        QuarantineValidated.
        """
        entry = self._load_entry(quarantine_id)
        if entry is None:
            raise KeyError(f"unknown quarantine_id: {quarantine_id}")

        results: list[tuple[str, bool, str]] = []
        failed: list[str] = []
        reasons: list[str] = []

        for rule in self.rules:
            try:
                ok, reason = rule.check(entry.genome_dir)
            except Exception as exc:
                ok, reason = False, f"rule raised: {exc}"
            results.append((rule.name, ok, reason))
            if not ok:
                failed.append(rule.name)
                reasons.append(f"{rule.name}: {reason}" if reason else rule.name)

        entry.reasons = reasons
        self._save_entry(entry)

        all_passed = not failed
        self._append_log("validate", entry, all_passed=all_passed, failed_rules=list(failed))

        try:
            emit(
                QuarantineValidated(
                    quarantine_id=quarantine_id,
                    all_passed=all_passed,
                    failed_rules=list(failed),
                )
            )
        except Exception:
            logger.debug("failed to emit QuarantineValidated", exc_info=True)

        return results

    # ---- approve / reject / hold ----

    def approve(
        self,
        quarantine_id: str,
        target_pool: AgentDrive,
        *,
        note: str = "",
    ) -> bool:
        """Validate, then ingest into `target_pool` only if everything passes.

        Marks the entry APPROVED on success. Returns True if released
        into the Drive, False otherwise (and the entry stays PENDING with
        reasons recorded so the operator can decide next step).
        """
        entry = self._load_entry(quarantine_id)
        if entry is None:
            raise KeyError(f"unknown quarantine_id: {quarantine_id}")

        # Status guard: only PENDING entries are eligible for approval. A
        # previously REJECTED entry whose content happens to revalidate clean
        # must NOT silently flip to APPROVED — the rejection was an operator
        # decision and stands until they explicitly resubmit.
        if entry.status != QuarantineStatus.PENDING:
            # Hash the quarantine_id before logging — it's the authorization
            # handle for approve(), so the raw value belongs only in the
            # audit log (``_append_log``), not operational stdout. The
            # ``hashlib.sha256`` boundary breaks CodeQL's secret-log taint.
            import hashlib

            id_digest = hashlib.sha256(quarantine_id.encode()).hexdigest()[:12]
            logger.warning(
                "approve blocked: entry sha256:%s status=%s",
                id_digest,
                entry.status.value,
            )
            self._append_log("approve_blocked", entry)
            return False

        results = self.validate(quarantine_id)
        if any(not ok for _name, ok, _r in results):
            return False

        # Load the genome from the candidate dir and hand off to the Drive.
        from agentdrive.genome.models import Genome  # local import to avoid cycle

        try:
            genome = Genome.load(entry.genome_dir)
        except Exception as exc:
            entry.reasons = list(entry.reasons) + [f"load_failed: {exc}"]
            self._save_entry(entry)
            self._append_log("approve_failed", entry, error=str(exc))
            return False

        try:
            target_pool.ingest(
                genome,
                source=f"quarantine:approved:{entry.source_peer}",
                actor=os.environ.get("USER", "quarantine"),
            )
        except Exception as exc:
            entry.reasons = list(entry.reasons) + [f"ingest_failed: {exc}"]
            self._save_entry(entry)
            self._append_log("approve_failed", entry, error=str(exc))
            return False

        # Refresh genome_id from the loaded genome (canonical id@version).
        entry.genome_id = genome.genome_id or entry.genome_id
        entry.status = QuarantineStatus.APPROVED
        if note:
            entry.reasons = list(entry.reasons) + [f"approved: {note}"]
        self._save_entry(entry)
        self._append_log("approve", entry, note=note)

        approver = os.environ.get("USER", "quarantine")
        try:
            emit(
                QuarantineApproved(
                    quarantine_id=quarantine_id,
                    genome_id=entry.genome_id,
                    approved_by=approver,
                )
            )
        except Exception:
            logger.debug("failed to emit QuarantineApproved", exc_info=True)

        return True

    def reject(self, quarantine_id: str, reason: str) -> bool:
        entry = self._load_entry(quarantine_id)
        if entry is None:
            raise KeyError(f"unknown quarantine_id: {quarantine_id}")
        entry.status = QuarantineStatus.REJECTED
        entry.reasons = list(entry.reasons) + [f"rejected: {reason}"]
        self._save_entry(entry)
        self._append_log("reject", entry, reason=reason)

        try:
            emit(
                QuarantineRejected(
                    quarantine_id=quarantine_id,
                    genome_id=entry.genome_id,
                    reason=reason,
                )
            )
        except Exception:
            logger.debug("failed to emit QuarantineRejected", exc_info=True)

        return True

    def hold(self, quarantine_id: str, reason: str) -> bool:
        """Move the entry to QUARANTINED — held indefinitely pending a call."""
        entry = self._load_entry(quarantine_id)
        if entry is None:
            raise KeyError(f"unknown quarantine_id: {quarantine_id}")
        entry.status = QuarantineStatus.QUARANTINED
        entry.reasons = list(entry.reasons) + [f"held: {reason}"]
        self._save_entry(entry)
        self._append_log("hold", entry, reason=reason)
        return True


# ─────────────────────────────────────────────────────────────────────
# Module-level default (lazy)
# ─────────────────────────────────────────────────────────────────────


_default_quarantine: Quarantine | None = None


def get_default_quarantine() -> Quarantine:
    """Return a process-wide default Quarantine rooted at $AGENTDRIVE_HOME/quarantine.

    Rebuilt if the AGENTDRIVE_HOME override changed (test isolation).
    """
    global _default_quarantine
    expected_root = get_agentdrive_home() / "quarantine"
    if _default_quarantine is None or _default_quarantine.root != expected_root:
        _default_quarantine = Quarantine(root=expected_root)
    return _default_quarantine


__all__ = [
    "QuarantineStatus",
    "QuarantineEntry",
    "ValidationRule",
    "SchemaValid",
    "SizeLimit",
    "NoExecutables",
    "PromptSanity",
    "SignatureValid",
    "Quarantine",
    "get_default_quarantine",
]
