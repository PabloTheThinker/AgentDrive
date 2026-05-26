"""
Core data models for Agent Drive Genomes (Agent DNA).

This is the foundational representation of transferable, versioned, evolvable
agent capabilities.
"""

from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class GenomeAuthor(BaseModel):
    """Author or contributor to a Genome (human or agent)."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True, str_strip_whitespace=True)

    type: Literal["human", "agent"]
    name: str | None = None
    id: str | None = None  # agent id or user handle
    run: str | None = None  # reference to the specific run that contributed


class ImprovementEvent(BaseModel):
    """Record of a specific improvement applied to this genome."""

    model_config = ConfigDict(extra="ignore", validate_assignment=True)

    timestamp: datetime
    description: str
    proposed_by: str | None = None
    score_delta: float | None = None
    notes: str | None = None


class GenomeProvenance(BaseModel):
    """Structured provenance and improvement history for the genome."""

    model_config = ConfigDict(extra="ignore", validate_assignment=True)

    lineage: list[dict[str, Any]] = Field(default_factory=list)
    improvements: list[ImprovementEvent] = Field(default_factory=list)

    def add_lineage_entry(self, parent: str, relation: str = "fork", notes: str = "") -> None:
        """Helper to append fork/merge lineage."""
        self.lineage.append(
            {
                "parent": parent,
                "relation": relation,
                "timestamp": datetime.utcnow().isoformat(),
                "notes": notes,
            }
        )


class GenomeManifest(BaseModel):
    """The identity and metadata header of a Genome. Production validated."""

    model_config = ConfigDict(extra="ignore", validate_assignment=True, str_strip_whitespace=True)

    id: str = Field(
        ..., min_length=1, description="Stable identifier, e.g. security-incident-postmortem"
    )
    version: str = Field(..., description="Semantic version (e.g. 2.3.1 or 1.0.0-rc1)")
    content_hash: str = Field(
        ..., description="sha256:<hex> of canonical content for exact reproducibility"
    )

    created: datetime
    last_improved: datetime | None = None

    authors: list[GenomeAuthor] = Field(default_factory=list)

    applicability: dict[str, Any] = Field(
        default_factory=dict,
        description="Domains, problem_signatures, keywords this genome is strong at",
    )

    dependencies: dict[str, list[str]] = Field(
        default_factory=lambda: {"genomes": [], "agent_capabilities": []}
    )

    evaluation_score: dict[str, float] = Field(
        default_factory=dict,
        description="Scores on reference_tasks, human_preference, cost_efficiency, etc.",
    )

    schema_version: str = Field(
        default="1.0", description="Manifest schema version for forward compat"
    )

    # v2 / AgentDrive Milestone 1: supersedes-DAG. When this Genome replaces
    # earlier work, list those Genomes' content hashes here. The DAG is walkable
    # in both directions and gives us free lineage without a separate ledger.
    supersedes: list[str] = Field(
        default_factory=list,
        description="Content hashes (sha256:<hex>) of Genomes this one supersedes — the v2 lineage edge",
    )

    # v2 / AgentDrive Milestone 4: merge strategy + CRDT state. The default
    # ``last-write`` preserves v1 behavior — non-matching same-id writes will
    # emit a conflict copy instead of clobbering. ``crdt-counter`` and
    # ``crdt-set`` are add-only (G-Counter / G-Set); see drive/crdt.py.
    merge_strategy: Literal["last-write", "crdt-counter", "crdt-set"] = Field(
        default="last-write",
        description="How sibling writes of the same Genome id are reconciled",
    )
    crdt_state: dict[str, Any] | None = Field(
        default=None,
        description="Actor-keyed CRDT state (counter: int per actor; set: list[str] under 'members')",
    )

    @field_validator("id")
    @classmethod
    def validate_id(cls, v: str) -> str:
        if not re.match(r"^[a-z0-9](?:[a-z0-9._-]*[a-z0-9])?$", v.lower()):
            raise ValueError(
                f"Genome id '{v}' must be lowercase alphanum (optionally with [._-]), min length 1"
            )
        return v

    @field_validator("version")
    @classmethod
    def validate_version(cls, v: str) -> str:
        # Accept semver-ish with pre-release/build
        if not re.match(r"^\d+\.\d+\.\d+(?:[-+][a-zA-Z0-9_.]+)?$", v):
            if not any(c.isdigit() for c in v):
                raise ValueError(f"Version '{v}' should contain numbers (semver recommended)")
        return v

    @field_validator("content_hash")
    @classmethod
    def validate_content_hash(cls, v: str) -> str:
        if v == "sha256:pending":
            return v
        if not (v.startswith("sha256:") and len(v) >= 15):
            raise ValueError("content_hash must be of form 'sha256:<64-hex>' or 'sha256:pending'")
        return v


class Genome(BaseModel):
    """
    A complete Agent Drive Genome — the reliable, evolvable 'DNA' primitive for agent capabilities.

    Supports:
    - Programmatic creation via Genome.create(...)
    - In-memory forking via .fork(...)
    - Improvement tracking via .record_improvement(...)
    - Content hashing for reproducibility
    - Rich structured persistence (spec-aligned dirs + legacy flat)
    - Full loading of framework, reasoning patterns (incl. jsonl), provenance/lineage, etc.
    """

    model_config = ConfigDict(
        extra="ignore",
        validate_assignment=True,
        str_strip_whitespace=True,
    )

    manifest: GenomeManifest
    framework: dict[str, Any] | None = None  # The structured typed playbook (inner content)
    reasoning_patterns: dict[str, Any] = Field(default_factory=dict)
    tool_compositions: dict[str, Any] = Field(default_factory=dict)
    evaluations: dict[str, Any] = Field(default_factory=dict)
    provenance: GenomeProvenance = Field(default_factory=GenomeProvenance)

    # Future: reference_artifacts handled by path, not embedded in model for size

    @property
    def genome_id(self) -> str:
        return f"{self.manifest.id}@{self.manifest.version}"

    def __repr__(self) -> str:
        return (
            f"Genome(id={self.manifest.id!r}, version={self.manifest.version!r}, "
            f"hash={self.manifest.content_hash[:32]}...)"
        )

    def __str__(self) -> str:
        return self.__repr__()

    def compute_content_hash(self) -> str:
        """Deterministic content hash over the capability payload (framework + patterns + tools + evals).

        Delegates to ``agentdrive.drive.content_store.genome_hash`` so there is
        exactly ONE place that decides what bytes get hashed. If you change the
        canonicalization rule, change it there.
        """
        # Local import: content_store imports Genome via canonical_genome_payload's
        # duck-typed access (not a direct import), so this stays acyclic.
        from agentdrive.drive.content_store import genome_hash

        return genome_hash(self)

    def finalize(self, update_timestamp: bool = True) -> None:
        """Compute/repair content hash and ensure last_improved is set. Safe to call after any change."""
        if (
            not self.manifest.content_hash
            or self.manifest.content_hash == "sha256:pending"
            or "example" in self.manifest.content_hash.lower()
        ):
            self.manifest.content_hash = self.compute_content_hash()
        if update_timestamp and self.manifest.last_improved is None:
            self.manifest.last_improved = datetime.utcnow()

    @model_validator(mode="after")
    def _ensure_integrity(self) -> Genome:
        self.finalize(update_timestamp=False)
        return self

    # --- Clean creation and evolution APIs ---

    @classmethod
    def create(
        cls,
        id: str,
        version: str,
        framework: dict[str, Any] | None = None,
        authors: list[dict[str, Any] | GenomeAuthor] | None = None,
        applicability: dict[str, Any] | None = None,
        dependencies: dict[str, list[str]] | None = None,
        evaluation_score: dict[str, float] | None = None,
        reasoning_patterns: dict[str, Any] | None = None,
        tool_compositions: dict[str, Any] | None = None,
        evaluations: dict[str, Any] | None = None,
        provenance: dict[str, Any] | None = None,
    ) -> Genome:
        """Primary factory for creating new genomes programmatically (the recommended constructor).

        Example:
            g = Genome.create(
                id="my-capability",
                version="1.0.0",
                framework={"steps": [...]},
                authors=[{"type": "human", "name": "Alice"}],
                applicability={"domains": ["security"]},
            )
            g.finalize()  # or it auto finalizes
        """
        auth_objects: list[GenomeAuthor] = []
        if authors:
            for a in authors:
                if isinstance(a, dict):
                    auth_objects.append(GenomeAuthor.model_validate(a))
                elif isinstance(a, GenomeAuthor):
                    auth_objects.append(a)
        manifest = GenomeManifest(
            id=id,
            version=version,
            content_hash="sha256:pending",
            created=datetime.utcnow(),
            authors=auth_objects,
            applicability=applicability or {},
            dependencies=dependencies or {"genomes": [], "agent_capabilities": []},
            evaluation_score=evaluation_score or {},
        )
        prov = GenomeProvenance.model_validate(provenance or {})
        g = cls(
            manifest=manifest,
            framework=framework,
            reasoning_patterns=reasoning_patterns or {},
            tool_compositions=tool_compositions or {},
            evaluations=evaluations or {},
            provenance=prov,
        )
        g.finalize()
        return g

    def fork(
        self,
        new_version: str,
        authors: list[dict[str, Any] | GenomeAuthor] | None = None,
        notes: str = "Forked for improvement / evolution",
    ) -> Genome:
        """Create an in-memory descendant (fork) of this genome.

        Does not save. Use registry.fork() for registry-integrated forking with auto-save.
        The fork records lineage automatically.
        """
        # Use Pydantic roundtrip for deep safe copy of data
        data = self.model_dump()
        auth_objects: list[GenomeAuthor] = []
        if authors:
            for a in authors:
                auth_objects.append(GenomeAuthor.model_validate(a) if isinstance(a, dict) else a)
        else:
            auth_objects = [a.model_copy() for a in self.manifest.authors]

        # rebuild manifest with updates (avoids direct mutation of frozen-ish)
        mdata = {
            k: v
            for k, v in data["manifest"].items()
            if k not in ("version", "created", "last_improved", "content_hash", "authors")
        }
        new_manifest = GenomeManifest(
            **mdata,
            version=new_version,
            content_hash="sha256:pending",
            created=datetime.utcnow(),
            last_improved=datetime.utcnow(),
            authors=auth_objects,
        )
        data["manifest"] = new_manifest.model_dump(mode="json")

        # record lineage in provenance
        prov_data = data.setdefault("provenance", {})
        lineage = prov_data.setdefault("lineage", [])
        lineage.append(
            {
                "parent": self.genome_id,
                "relation": "fork",
                "timestamp": datetime.utcnow().isoformat(),
                "notes": notes,
            }
        )
        prov_data["lineage"] = lineage
        data["provenance"] = prov_data

        forked = Genome.model_validate(data)
        forked.finalize()
        return forked

    def record_improvement(
        self,
        description: str,
        proposed_by: str | None = None,
        score_delta: float | None = None,
        notes: str | None = None,
    ) -> ImprovementEvent:
        """Append an improvement event to provenance and update last_improved.
        Returns the event. Does not change version (call site or registry decides on version bump).
        """
        event = ImprovementEvent(
            timestamp=datetime.utcnow(),
            description=description,
            proposed_by=proposed_by,
            score_delta=score_delta,
            notes=notes,
        )
        self.provenance.improvements.append(event)
        self.manifest.last_improved = datetime.utcnow()
        return event

    # --- Persistence (hardened, full-structure aware) ---

    def save(self, path: Path | str) -> Path:
        """Persist this genome using the canonical directory layout from GENOME-SPEC.md.

        - manifest.yaml + manifest.json (flat)
        - framework.yaml (with 'framework:' wrapper for compat)
        - reasoning/, tools/, evaluations/, provenance/ subdirs with json (and lineage.json)
        - Also writes legacy flat files for maximum compatibility.
        Always call finalize() before save if you mutated content.
        """
        path = Path(path)
        path.mkdir(parents=True, exist_ok=True)

        # Manifests (yaml primary for spec, json always)
        mdata = self.manifest.model_dump(mode="json")
        (path / "manifest.yaml").write_text(
            yaml.safe_dump(mdata, sort_keys=False, default_flow_style=False)
        )
        (path / "manifest.json").write_text(self.manifest.model_dump_json(indent=2))

        # Framework (wrapped to match existing example format)
        if self.framework is not None:
            fw_wrapped = {"framework": self.framework}
            (path / "framework.yaml").write_text(
                yaml.safe_dump(fw_wrapped, sort_keys=False, default_flow_style=False)
            )
            (path / "framework.json").write_text(json.dumps(fw_wrapped, indent=2, default=str))

        # Rich structured content (new canonical) + legacy flat files
        structured = {
            "reasoning_patterns": ("reasoning", "reasoning_patterns.json"),
            "tool_compositions": ("tools", "tool_compositions.json"),
            "evaluations": ("evaluations", "reference-evals.json"),
            "provenance": ("provenance", "provenance.json"),
        }
        for attr_name, (subdir, fname) in structured.items():
            data = getattr(self, attr_name)
            if attr_name == "provenance":
                data = data.model_dump(mode="json") if isinstance(data, GenomeProvenance) else data
            if data:
                target_dir = path / subdir if subdir else path
                target_dir.mkdir(parents=True, exist_ok=True)
                (target_dir / fname).write_text(json.dumps(data, indent=2, default=str))

                # Extra lineage file per spec
                if attr_name == "provenance" and isinstance(data, dict) and data.get("lineage"):
                    (target_dir / "lineage.json").write_text(
                        json.dumps({"lineage": data["lineage"]}, indent=2, default=str)
                    )

        # Legacy flat copies (so old code keeps working)
        for key, data in [
            ("reasoning_patterns", self.reasoning_patterns),
            ("tool_compositions", self.tool_compositions),
            ("evaluations", self.evaluations),
        ]:
            if data:
                (path / f"{key}.json").write_text(json.dumps(data, indent=2, default=str))

        return path

    @classmethod
    def load(cls, path: Path | str) -> Genome:
        """Load a complete genome from disk.

        Supports:
        - New structured layout (manifest.yaml, reasoning/*.json, provenance/lineage.json, etc.)
        - Legacy flat files (manifest.json + *.json next to framework.yaml)
        - YAML or JSON manifests, with or without top-level 'genome:' wrapper
        - framework.yaml/json with or without 'framework:' wrapper
        - patterns.jsonl under reasoning/ (merged into reasoning_patterns['patterns'])
        Robust with good error messages.
        """
        path = Path(path)
        if not path.is_dir():
            raise FileNotFoundError(f"Genome path is not a directory: {path}")

        # --- Manifest (flexible discovery + normalization) ---
        manifest: GenomeManifest | None = None
        for mfile in ("manifest.yaml", "manifest.json"):
            mp = path / mfile
            if mp.exists():
                try:
                    if mfile.endswith(".yaml"):
                        raw = yaml.safe_load(mp.read_text(encoding="utf-8")) or {}
                    else:
                        raw = json.loads(mp.read_text(encoding="utf-8"))
                    if (
                        isinstance(raw, dict)
                        and "genome" in raw
                        and isinstance(raw["genome"], dict)
                    ):
                        raw = raw["genome"]
                    manifest = GenomeManifest.model_validate(raw)
                    break
                except Exception as exc:
                    raise ValueError(f"Failed to parse {mfile} in {path}: {exc}") from exc
        if manifest is None:
            raise FileNotFoundError(
                f"No manifest found in genome dir {path}. Expected manifest.yaml or manifest.json"
            )

        # --- Framework (normalize wrapper) ---
        framework: dict[str, Any] | None = None
        for ffile in ("framework.yaml", "framework.json"):
            fp = path / ffile
            if fp.exists():
                try:
                    if ffile.endswith(".yaml"):
                        raw_fw = yaml.safe_load(fp.read_text(encoding="utf-8")) or {}
                    else:
                        raw_fw = json.loads(fp.read_text(encoding="utf-8"))
                    if isinstance(raw_fw, dict) and "framework" in raw_fw:
                        framework = raw_fw["framework"]
                    else:
                        framework = raw_fw
                    break
                except Exception as exc:
                    raise ValueError(f"Failed to parse {ffile} in {path}: {exc}") from exc

        # --- Other data: structured first, then legacy flat, with special jsonl support ---
        def _load_json_candidates(*candidates: Path) -> dict[str, Any]:
            for cand in candidates:
                if cand.exists():
                    try:
                        return json.loads(cand.read_text(encoding="utf-8"))
                    except Exception:
                        return {}
            return {}

        reasoning_patterns = _load_json_candidates(
            path / "reasoning" / "reasoning_patterns.json",
            path / "reasoning_patterns.json",
        )
        # patterns.jsonl support (as list under 'patterns')
        patterns_jl = path / "reasoning" / "patterns.jsonl"
        if patterns_jl.exists():
            try:
                lines = []
                for line in patterns_jl.read_text(encoding="utf-8").splitlines():
                    line = line.strip()
                    if line:
                        lines.append(json.loads(line))
                if lines:
                    reasoning_patterns.setdefault("patterns", lines)
            except Exception:
                pass

        tool_compositions = _load_json_candidates(
            path / "tools" / "tool_compositions.json",
            path / "tool_compositions.json",
        )

        evaluations = _load_json_candidates(
            path / "evaluations" / "reference-evals.json",
            path / "evaluations.json",
            path / "reference-evals.json",
        )

        prov_raw = _load_json_candidates(
            path / "provenance" / "provenance.json",
            path / "provenance.json",
        )
        # lineage.json per spec
        lineage_file = path / "provenance" / "lineage.json"
        if lineage_file.exists():
            try:
                lin_raw = json.loads(lineage_file.read_text(encoding="utf-8"))
                if isinstance(lin_raw, dict) and "lineage" in lin_raw:
                    prov_raw.setdefault("lineage", lin_raw["lineage"])
            except Exception:
                pass

        provenance = GenomeProvenance.model_validate(prov_raw or {})

        g = cls(
            manifest=manifest,
            framework=framework,
            reasoning_patterns=reasoning_patterns,
            tool_compositions=tool_compositions,
            evaluations=evaluations,
            provenance=provenance,
        )
        return g


# Convenience alias
AgentGenome = Genome
