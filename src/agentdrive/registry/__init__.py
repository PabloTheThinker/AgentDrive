"""
Savant Genome Registry.

Production-ready local-first registry for versioned, searchable, forkable Agent Genomes (DNA).

- Stores genomes hierarchically under <root>/<genome_id>/<version>/ for clean versioning
- Backward-compatible with legacy flat layout
- Rich search/filter by applicability domains, problem signatures, capabilities, scores, free-text
- Version management: get_versions, get_latest
- Native fork() that produces descendant + records full provenance lineage
- Delegates full load/save (with normalization, content hashing, structured files) to Genome model
- Used by: TUI, scanners, evolution engine, orchestrator, programmatic users

See savant.genome.models.Genome for the DNA primitive itself.
"""

from pathlib import Path
from typing import Any, Dict, List, Optional

from agentdrive.genome.models import Genome, GenomeAuthor


class GenomeRegistry:
    """Production-ready local Genome registry for the Savant evolutionary ecosystem.

    Supports hierarchical + legacy flat storage, full search/filter by applicability,
    versioning, forking with provenance, and delegates rich Genome load/save/hashing.
    Existing methods (list_genome_details, search_genomes, bootstrap, stats) preserved.
    """

    def __init__(
        self,
        root: Path | None = None,
        *,
        swarm_id: str | None = None,
        subagent_id: str | None = None,
    ):
        self.swarm_id = swarm_id
        self.subagent_id = subagent_id
        if root is None:
            from agentdrive.constants import get_agentdrive_home, get_swarm_drive_path

            if swarm_id is not None or subagent_id is not None:
                pool_p = get_swarm_drive_path(swarm_id or "default", subagent_id)
                root = Path(pool_p) / "genomes"
            else:
                root = get_agentdrive_home() / "genomes"
        # Resolve before mkdir so any symlink escape collapses to a single
        # canonical path the rest of the registry can reason about.
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def list_genomes(self) -> list[str]:
        """Return qualified names for all genomes (supports hier <id>/<ver> + legacy flat)."""
        found: list[str] = []
        for p in self.root.iterdir():
            if not p.is_dir():
                continue
            if self._has_manifest(p):
                found.append(p.name)
            else:
                # possible hier id dir
                for v in p.iterdir():
                    if v.is_dir() and self._has_manifest(v):
                        found.append(f"{p.name}/{v.name}")
        return sorted(set(found))

    def list_genome_ids(self) -> list[str]:
        """Alias for list_genomes for CLI friendliness."""
        return self.list_genomes()

    def _has_manifest(self, p: Path) -> bool:
        """Internal: does this dir contain a genome manifest?"""
        return (p / "manifest.yaml").exists() or (p / "manifest.json").exists()

    def list_ids(self) -> list[str]:
        """Return unique base genome ids (new hardened alias)."""
        ids = set()
        for name in self.list_genomes():
            gid, _ = self._parse_spec(name)
            ids.add(gid)
        return sorted(ids)

    def load(self, genome_id: str) -> Genome | None:
        """Load a genome by its directory name (e.g. 'security-incident-postmortem-v1')."""
        path = self.root / genome_id
        if not path.exists() or not path.is_dir():
            return None
        return Genome.load(path)

    def save(self, genome: Genome) -> Path:
        """Hardened save: use clean hierarchical <root>/<id>/<version>/ layout.
        Legacy flat names still loadable via enhanced load/list.
        """
        genome.finalize()
        gid = genome.manifest.id
        ver = genome.manifest.version
        target = self.root / gid / ver
        target.mkdir(parents=True, exist_ok=True)
        genome.save(target)
        return target

    def register_from_dir(self, source_dir: Path | str, override_id: str | None = None) -> Genome:
        """Load a genome manually placed in a directory and register it. Returns the Genome (fixed to return object not path)."""
        src = Path(source_dir)
        g = Genome.load(src)
        if override_id:
            g.manifest.id = override_id
        g.finalize()
        self.save(g)  # hierarchical or flat depending on impl
        return g

    def get_genome_path(self, genome_id: str) -> Path | None:
        path = self.root / genome_id
        return path if path.exists() else None

    def list_genome_details(self) -> list[dict[str, Any]]:
        """Return rich metadata dicts for UI tables, browsers, search. Safe on partial data."""
        details: list[dict[str, Any]] = []
        for name in self.list_genomes():
            path = self.root / name
            try:
                g = Genome.load(path)
                m = g.manifest
                details.append(
                    {
                        "dir_name": name,
                        "genome_id": g.genome_id,
                        "id": m.id,
                        "version": m.version,
                        "domains": m.applicability.get("domains", [])
                        if isinstance(m.applicability, dict)
                        else [],
                        "problem_signatures": m.applicability.get("problem_signatures", [])
                        if isinstance(m.applicability, dict)
                        else [],
                        "score": float(m.evaluation_score.get("reference_tasks", 0.0))
                        if isinstance(m.evaluation_score, dict)
                        else 0.0,
                        "authors": [(a.name or a.id or "unknown") for a in (m.authors or [])],
                        "created": m.created.isoformat()
                        if hasattr(m.created, "isoformat")
                        else str(m.created),
                        "last_improved": (
                            m.last_improved.isoformat()
                            if m.last_improved and hasattr(m.last_improved, "isoformat")
                            else None
                        ),
                        "has_framework": bool(g.framework),
                        "num_steps": len(g.framework.get("steps", [])) if g.framework else 0,
                    }
                )
            except Exception:
                details.append(
                    {
                        "dir_name": name,
                        "genome_id": name,
                        "id": name,
                        "version": "?",
                        "domains": [],
                        "problem_signatures": [],
                        "score": 0.0,
                        "authors": ["?"],
                        "created": "",
                        "last_improved": None,
                        "has_framework": False,
                        "num_steps": 0,
                    }
                )
        return sorted(details, key=lambda d: d.get("genome_id", d["dir_name"]))

    def get_genome(self, key: str) -> Genome | None:
        """Robust loader: tries dir, genome_id, bare id, and searches details."""
        if not key:
            return None
        # direct
        for cand in (key, key.replace("@", "-"), key.split("@", 1)[0] if "@" in key else key):
            p = self.root / cand
            if p.is_dir():
                try:
                    return Genome.load(p)
                except Exception:
                    pass
        # search
        for d in self.list_genome_details():
            if key in (d["dir_name"], d["genome_id"], d["id"]):
                p = self.root / d["dir_name"]
                if p.is_dir():
                    try:
                        return Genome.load(p)
                    except Exception:
                        return None
        return None

    def search_genomes(self, query: str) -> list[str]:
        """Case-insensitive search returning dir_names matching id/domains/signatures."""
        q = (query or "").lower().strip()
        if not q:
            return self.list_genomes()
        hits = []
        for d in self.list_genome_details():
            haystack = " ".join(
                filter(
                    None,
                    [
                        d.get("id", ""),
                        d.get("genome_id", ""),
                        d.get("dir_name", ""),
                        " ".join(d.get("domains", [])),
                        " ".join(d.get("problem_signatures", [])),
                    ],
                )
            ).lower()
            if q in haystack:
                hits.append(d["dir_name"])
        return hits

    def ensure_bootstrap_example(self, example_dir: Path | None = None) -> str | None:
        """Auto-register the seed example genome if registry is empty. Returns registered genome_id or None."""
        if self.list_genomes():
            return None
        if example_dir is None:
            # Search a portable set of locations — current working directory
            # and the project root walked back from this file. No absolute
            # personal-machine paths.
            candidates = [
                Path.cwd() / "genomes" / "examples" / "security-incident-postmortem-v1",
                Path(__file__).resolve().parents[4]
                / "genomes"
                / "examples"
                / "security-incident-postmortem-v1",  # src/agentdrive/registry/__init__.py -> project root
            ]
            for c in candidates:
                if c and (c / "manifest.json").exists() and (c / "framework.yaml").exists():
                    example_dir = c
                    break
        if example_dir and (example_dir / "manifest.json").exists():
            try:
                g = self.register_from_dir(example_dir)
                return g.genome_id
            except Exception:
                # fallback: try direct load+save
                try:
                    gg = Genome.load(example_dir)
                    return self.save(gg).name
                except Exception:
                    return None
        return None

    def get_registry_stats(self) -> dict[str, Any]:
        """Summary for status dashboard and health checks."""
        details = self.list_genome_details()
        return {
            "root": str(self.root),
            "count": len(details),
            "genome_ids": [d["genome_id"] for d in details],
            "domains_covered": sorted({d for det in details for d in det.get("domains", [])}),
            "avg_score": round(
                sum(det.get("score", 0) for det in details) / max(1, len(details)), 3
            )
            if details
            else 0.0,
            "total_steps": sum(det.get("num_steps", 0) for det in details),
        }

    # --- Hardened additions: versioning, applicability filtering, full search, forking ---

    def get_versions(self, genome_id: str) -> list[str]:
        """Return sorted list of versions available for base id (works with current flat layout too)."""
        vers: list[str] = []
        gid_prefix = genome_id
        for name in self.list_genomes():
            parsed_gid, v = self._parse_spec(name)
            if parsed_gid == gid_prefix and v:
                if v not in vers:
                    vers.append(v)
            elif name == gid_prefix:
                vers.append(name)

        def _semver_key(v: str) -> tuple:
            try:
                parts = [int(x) for x in v.split("-")[0].split("+")[0].split(".") if x.isdigit()]
                return tuple(parts) or (0,)
            except Exception:
                return (0,)

        return sorted(set(vers), key=_semver_key)

    def load(self, genome_id: str) -> Genome | None:  # type: ignore[override]
        """Enhanced load: accepts 'id', 'id@ver', 'id/ver', 'id-ver', or direct Path.
        Falls back to latest version if bare id given. Preserves original behavior.
        """
        # delegate to robust internal if possible, else original
        try:
            p = Path(genome_id)
            if p.exists() and p.is_dir():
                return Genome.load(p)
        except Exception:
            pass

        gid, ver = (
            self._parse_spec(genome_id) if hasattr(self, "_parse_spec") else (genome_id, None)
        )
        if not hasattr(self, "_parse_spec"):
            # fallback parse
            for sep in ("@", "/", "-"):
                if sep in str(genome_id):
                    gid, ver = str(genome_id).split(sep, 1)
                    break
            else:
                gid, ver = str(genome_id), None

        if ver is None:
            # pick latest
            vers = self.get_versions(gid)
            if vers:
                ver = vers[-1]
        # try several candidate dir names
        candidates = []
        if ver:
            candidates.extend([f"{gid}/{ver}", f"{gid}@{ver}", f"{gid}-{ver}", f"{gid}{ver}"])
        candidates.append(gid)
        candidates.append(genome_id)
        for cand in candidates:
            p = self.root / cand
            if (
                p.exists()
                and p.is_dir()
                and ((p / "manifest.json").exists() or (p / "manifest.yaml").exists())
            ):
                try:
                    return Genome.load(p)
                except Exception:
                    continue
        # original fallback
        path = self.root / str(genome_id)
        if path.exists() and path.is_dir():
            try:
                return Genome.load(path)
            except Exception:
                return None
        return None

    def _parse_spec(self, spec: str) -> tuple[str, str | None]:
        """Robust parser that handles ids containing - (e.g. security-incident-postmortem-1.0.0)."""
        s = str(spec).strip()
        if "@" in s:
            return s.split("@", 1)
        if "/" in s:
            return s.split("/", 1)
        # for - : split only on the last - that precedes a version-like token (starts with digit)
        if "-" in s:
            # try last -
            left, right = s.rsplit("-", 1)
            if right and (
                right[0].isdigit() or right[0].isalpha() and any(c.isdigit() for c in right)
            ):
                return left, right
            # fallback whole
        return s, None

    def search(
        self,
        query: str | None = None,
        domains: list[str] | None = None,
        capabilities: list[str] | None = None,
        min_score: float | None = None,
        limit: int = 50,
    ) -> list[Genome]:
        """Full search with filtering by applicability etc. (complements the simpler search_genomes).
        Returns actual Genome objects ready for use by evolution/orchestrator.
        """
        results: list[Genome] = []
        for name in self.list_genomes():
            g = None
            try:
                g = self.load(name)  # uses enhanced load
            except Exception:
                continue
            if not g:
                continue
            ok = True
            if query:
                q = query.lower()
                hay = " ".join(
                    [
                        g.manifest.id,
                        g.manifest.version,
                        str(g.manifest.applicability or {}),
                        " ".join(a.name or "" for a in g.manifest.authors),
                    ]
                ).lower()
                if q not in hay:
                    ok = False
            if ok and domains:
                doms = [str(x).lower() for x in (g.manifest.applicability or {}).get("domains", [])]
                if not any(d.lower() in doms for d in domains):
                    ok = False
            if ok and capabilities:
                caps = (g.manifest.dependencies or {}).get("agent_capabilities", [])
                if not any(c in caps for c in capabilities):
                    ok = False
            if ok and min_score is not None:
                sc = list((g.manifest.evaluation_score or {}).values())
                if not sc or max(sc) < float(min_score):
                    ok = False
            if ok:
                results.append(g)
                if len(results) >= limit:
                    break
        return results

    def filter_by_applicability(self, domains: list[str], **search_kwargs) -> list[Genome]:
        """Filter genomes whose applicability matches any of the given domains."""
        return self.search(domains=domains, **search_kwargs)

    def fork(
        self,
        source_spec: str,
        new_version: str,
        authors: list[dict[str, Any] | GenomeAuthor] | None = None,
        notes: str = "Forked for evolutionary improvement",
    ) -> Genome:
        """High-level forking API: load source, produce improved descendant via Genome.fork,
        persist it, return the child. Records lineage automatically.
        """
        src = self.load(source_spec)
        if src is None:
            raise ValueError(
                f"Fork source '{source_spec}' not found. Registry has: {self.list_genomes()[:10]}"
            )
        child = src.fork(new_version=new_version, authors=authors, notes=notes)
        self.save(child)
        return child

    def register_example_if_needed(self) -> str | None:
        """Idempotent helper (alias to ensure_bootstrap_example for new code)."""
        return self.ensure_bootstrap_example()


__all__ = ["GenomeRegistry"]
