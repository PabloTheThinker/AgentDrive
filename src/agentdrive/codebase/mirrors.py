"""
Mirror-neuron layer — observation activates motor programs for mimicry.

Like mirror neurons in humans: seeing how code is written primes the same
writing circuits. Observations link to exemplar motor templates; cross-project
resonance strengthens patterns shared across repos (universal priors).
"""

from __future__ import annotations

import json
import logging
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from agentdrive.codebase.exemplars import extract_exemplars
from agentdrive.codebase.registry import framework_path, list_projects
from agentdrive.constants import get_agentdrive_home
from agentdrive.utils.safe_paths import safe_name

logger = logging.getLogger(__name__)


def _mirrors_path(project_id: str) -> Path:
    slug = safe_name(project_id)
    return get_agentdrive_home() / "codebase-patterns" / slug / "mirrors.json"


def _resonance_path() -> Path:
    root = get_agentdrive_home() / "codebase-patterns"
    root.mkdir(parents=True, exist_ok=True)
    return root / "mirror_resonance.json"


def _load_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _save_json(path: Path, data: dict[str, Any]) -> None:
    path.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")


def _pattern_key_from_observation(obs: dict[str, Any]) -> list[str]:
    """Tags that identify which motor programs this observation should fire."""
    keys: list[str] = []
    lang = obs.get("language", "unknown")
    keys.append(f"lang:{lang}")
    sig = obs.get("signals") or {}
    if sig.get("function_naming"):
        keys.append(f"func_naming:{sig['function_naming']}")
    if sig.get("class_naming"):
        keys.append(f"class_naming:{sig['class_naming']}")
    if sig.get("import_style") and sig["import_style"] != "unknown":
        keys.append(f"imports:{sig['import_style']}")
    for fw in obs.get("frameworks") or []:
        keys.append(f"fw:{fw}")
    for conv, val in (
        ("type_hints", sig.get("uses_type_hints")),
        ("async", sig.get("uses_async")),
        ("dataclass", sig.get("uses_dataclass")),
        ("logging", sig.get("uses_structured_logging")),
        ("hooks", sig.get("uses_react_hooks")),
    ):
        if val:
            keys.append(f"conv:{conv}")
    rel = obs.get("path", "")
    if "/" in rel:
        keys.append(f"dir:{rel.split('/')[0]}")
    return keys


def ingest_observation_mirror(
    project_id: str,
    *,
    path: str,
    content: str,
    observation: dict[str, Any],
) -> dict[str, Any]:
    """
    Mirror-neuron ingest: observation → link exemplar motor templates + fire tags.
    """
    language = observation.get("language", "unknown")
    exemplars = extract_exemplars(path=path, content=content, language=language)
    pattern_keys = _pattern_key_from_observation(observation)

    store = _load_json(_mirrors_path(project_id))
    store.setdefault("project_id", safe_name(project_id))
    store.setdefault("motor_programs", [])
    store.setdefault("observation_links", [])
    motors: list[dict[str, Any]] = list(store.get("motor_programs") or [])
    links: list[dict[str, Any]] = list(store.get("observation_links") or [])

    fired: list[str] = []
    now = datetime.now(UTC).isoformat()

    for ex in exemplars:
        motor_id = f"motor:{safe_name(project_id)}:{ex.get('kind')}:{ex.get('name')}"
        existing = next((m for m in motors if m.get("id") == motor_id), None)
        if existing:
            existing["fire_count"] = int(existing.get("fire_count") or 0) + 1
            existing["last_fired_at"] = now
            existing["source_paths"] = list(
                dict.fromkeys((existing.get("source_paths") or []) + [path])
            )[-8:]
        else:
            motors.append(
                {
                    "id": motor_id,
                    "kind": ex.get("kind"),
                    "name": ex.get("name"),
                    "pattern_keys": pattern_keys,
                    "motor_template": ex.get("motor_template", ""),
                    "source_paths": [path],
                    "fire_count": 1,
                    "first_seen_at": now,
                    "last_fired_at": now,
                }
            )
        fired.append(motor_id)

    links.append(
        {
            "path": path,
            "observed_at": observation.get("observed_at", now),
            "pattern_keys": pattern_keys,
            "motors_fired": fired,
            "exemplar_count": len(exemplars),
        }
    )
    links = links[-200:]
    motors = motors[-120:]

    store["motor_programs"] = motors
    store["observation_links"] = links
    store["updated_at"] = now
    _save_json(_mirrors_path(project_id), store)

    resonance = _update_global_resonance(project_id, pattern_keys, fired)
    return {
        "motors_fired": len(fired),
        "motor_ids": fired[:6],
        "pattern_keys": pattern_keys,
        "resonance_updates": resonance.get("updated", 0),
    }


def _update_global_resonance(
    project_id: str,
    pattern_keys: list[str],
    motor_ids: list[str],
) -> dict[str, Any]:
    """Cross-project mirror field — patterns seen in multiple repos resonate louder."""
    data = _load_json(_resonance_path())
    nodes: dict[str, Any] = dict(data.get("nodes") or {})
    edges: list[dict[str, Any]] = list(data.get("edges") or [])
    slug = safe_name(project_id)

    for key in pattern_keys:
        node = nodes.get(key) or {
            "pattern_key": key,
            "projects": [],
            "fire_count": 0,
            "motor_count": 0,
        }
        projects = list(node.get("projects") or [])
        if slug not in projects:
            projects.append(slug)
        node["projects"] = projects[-20:]
        node["fire_count"] = int(node.get("fire_count") or 0) + 1
        node["motor_count"] = int(node.get("motor_count") or 0) + len(motor_ids)
        node["last_fired_at"] = datetime.now(UTC).isoformat()
        # Resonance strength: more projects sharing = stronger universal prior
        node["resonance"] = round(
            min(1.0, 0.35 + 0.15 * len(projects) + 0.02 * node["fire_count"]),
            3,
        )
        nodes[key] = node

    for i, mid in enumerate(motor_ids[:4]):
        for key in pattern_keys[:3]:
            edges.append(
                {
                    "motor_id": mid,
                    "pattern_key": key,
                    "project_id": slug,
                    "weight": 1.0 / (1 + i * 0.1),
                }
            )
    edges = edges[-500:]

    data["nodes"] = nodes
    data["edges"] = edges
    data["updated_at"] = datetime.now(UTC).isoformat()
    _save_json(_resonance_path(), data)
    return {"updated": len(pattern_keys)}


def fire_mirrors_for_intent(
    project_id: str,
    *,
    intent: str,
    language: str | None = None,
    limit: int = 5,
) -> dict[str, Any]:
    """
    Given writing intent, fire mirror neurons — return motor templates to imitate.
    """
    store = _load_json(_mirrors_path(project_id))
    motors: list[dict[str, Any]] = list(store.get("motor_programs") or [])
    framework = _load_json(framework_path(project_id))
    patterns = framework.get("patterns") or []

    intent_tokens = set(re.findall(r"[a-z]{3,}", intent.lower()))
    scored: list[tuple[float, dict[str, Any]]] = []

    for motor in motors:
        score = 0.0
        name = str(motor.get("name", "")).lower()
        template = str(motor.get("motor_template", "")).lower()
        for tok in intent_tokens:
            if tok in name:
                score += 2.5
            if tok in template:
                score += 0.8
        score += 0.15 * int(motor.get("fire_count") or 0)
        if language:
            keys = motor.get("pattern_keys") or []
            if f"lang:{language}" in keys:
                score += 1.2
        if score > 0:
            scored.append((score, motor))

    scored.sort(key=lambda x: x[0], reverse=True)
    fired = [m for _, m in scored[:limit]]

    if not fired and motors:
        fired = sorted(motors, key=lambda m: int(m.get("fire_count") or 0), reverse=True)[:limit]

    resonance_hits = _resonance_for_project(project_id, patterns)
    mimicry_prompt = _build_mimicry_prompt(
        project_id=project_id,
        intent=intent,
        fired=fired,
        patterns=patterns,
        resonance=resonance_hits,
    )

    return {
        "project_id": project_id,
        "intent": intent,
        "motors_fired": len(fired),
        "motor_programs": [
            {
                "id": m.get("id"),
                "kind": m.get("kind"),
                "name": m.get("name"),
                "template": m.get("motor_template", ""),
                "source_paths": m.get("source_paths", [])[:3],
                "fire_count": m.get("fire_count", 0),
            }
            for m in fired
        ],
        "resonance": resonance_hits[:6],
        "mimicry_prompt": mimicry_prompt,
    }


def _resonance_for_project(
    project_id: str,
    patterns: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    data = _load_json(_resonance_path())
    nodes: dict[str, Any] = dict(data.get("nodes") or {})
    hits: list[dict[str, Any]] = []
    slug = safe_name(project_id)

    for pat in patterns:
        pid = pat.get("id", "")
        candidates = []
        if pid.startswith("language-"):
            candidates.append(f"lang:{pid.replace('language-', '')}")
        if pid.startswith("naming-functions-"):
            candidates.append(f"func_naming:{pid.replace('naming-functions-', '')}")
        if pid.startswith("imports-"):
            candidates.append(f"imports:{pid.replace('imports-', '')}")
        if pid.startswith("framework-"):
            candidates.append(f"fw:{pid.replace('framework-', '')}")
        for key in candidates:
            node = nodes.get(key)
            if not node:
                continue
            other_projects = [p for p in node.get("projects") or [] if p != slug]
            hits.append(
                {
                    "pattern_key": key,
                    "resonance": node.get("resonance", 0),
                    "shared_with_projects": other_projects[:5],
                    "fire_count": node.get("fire_count", 0),
                }
            )
    hits.sort(key=lambda h: float(h.get("resonance") or 0), reverse=True)
    return hits


def _build_mimicry_prompt(
    *,
    project_id: str,
    intent: str,
    fired: list[dict[str, Any]],
    patterns: list[dict[str, Any]],
    resonance: list[dict[str, Any]],
) -> str:
    lines = [
        f"# Mimicry brief — write like `{project_id}`",
        "",
        f"**Intent:** {intent}",
        "",
        "Mirror-neuron rule: imitate the motor programs below — same naming, imports,",
        "structure, and rhythm. Do not invent a foreign style.",
        "",
        "## Project patterns",
    ]
    for pat in patterns[:6]:
        lines.append(f"- {pat.get('rule', '')}")
    if resonance:
        lines.append("")
        lines.append("## Cross-project resonance (shared with other observed repos)")
        for hit in resonance[:4]:
            shared = ", ".join(hit.get("shared_with_projects") or []) or "none yet"
            lines.append(
                f"- `{hit.get('pattern_key')}` resonance {hit.get('resonance')} — also in: {shared}"
            )
    if fired:
        lines.append("")
        lines.append("## Motor programs to imitate")
        for motor in fired[:3]:
            lines.append(f"### {motor.get('kind')}: {motor.get('name')}")
            lines.append("```")
            lines.append(str(motor.get("motor_template", ""))[:600])
            lines.append("```")
    return "\n".join(lines)


def transform_toward_style(
    project_id: str,
    *,
    code: str,
    path: str = "snippet.py",
) -> dict[str, Any]:
    """Transform generic code toward observed project style (naming mimicry)."""
    from agentdrive.codebase.analyzer import analyze_content
    from agentdrive.codebase.framework import get_writing_guide, match_against_framework

    framework = get_writing_guide(project_id)
    patterns = framework.get("patterns") or []
    match = match_against_framework(project_id, code=code, path=path)
    snippet = analyze_content(path=path, content=code)

    func_style = "snake_case"
    class_style = "PascalCase"
    for pat in patterns:
        pid = pat.get("id", "")
        if pid.startswith("naming-functions-"):
            func_style = pid.replace("naming-functions-", "")
        if pid.startswith("naming-classes-"):
            class_style = pid.replace("naming-classes-", "")

    transformed = code
    suggestions: list[str] = []

    if func_style == "snake_case":
        for name in (snippet.identifiers or {}).get("functions", []):
            if re.search(r"[A-Z]", name) and "_" not in name:
                snake = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", name).lower()
                if snake != name:
                    transformed = re.sub(rf"\b{re.escape(name)}\b", snake, transformed)
                    suggestions.append(f"Rename function `{name}` → `{snake}`")
    elif func_style == "camelCase":
        for name in (snippet.identifiers or {}).get("functions", []):
            if "_" in name:
                parts = name.split("_")
                camel = parts[0] + "".join(p.capitalize() for p in parts[1:])
                transformed = re.sub(rf"\b{re.escape(name)}\b", camel, transformed)
                suggestions.append(f"Rename function `{name}` → `{camel}`")

    lang = framework.get("summary", {}).get("languages", {})
    primary = max(lang, key=lang.get) if lang else snippet.language
    if primary == "python" and "def " in transformed and "->" not in transformed:
        suggestions.append("Add return type hints to match project convention")
    if primary == "typescript" and "export " not in transformed and "function " in transformed:
        suggestions.append("Consider `export` on public functions (TypeScript project style)")

    fired = fire_mirrors_for_intent(project_id, intent="transform style", language=primary, limit=2)

    return {
        "project_id": project_id,
        "original_alignment": match.get("alignment_score"),
        "transformed_code": transformed,
        "suggestions": suggestions,
        "target_function_naming": func_style,
        "target_class_naming": class_style,
        "mimicry_prompt": fired.get("mimicry_prompt", "")[:1200],
        "conflicts_remaining": match.get("conflicts", []),
    }


def mirror_summary(project_id: str) -> dict[str, Any]:
    store = _load_json(_mirrors_path(project_id))
    motors = store.get("motor_programs") or []
    return {
        "motor_program_count": len(motors),
        "total_fires": sum(int(m.get("fire_count") or 0) for m in motors),
        "top_motors": [
            {"name": m.get("name"), "kind": m.get("kind"), "fires": m.get("fire_count")}
            for m in sorted(motors, key=lambda x: int(x.get("fire_count") or 0), reverse=True)[:5]
        ],
    }


def global_mirror_field(*, limit: int = 12) -> dict[str, Any]:
    """Universal priors — pattern keys that resonate across multiple observed projects."""
    data = _load_json(_resonance_path())
    nodes: list[dict[str, Any]] = list((data.get("nodes") or {}).values())
    nodes.sort(
        key=lambda n: (len(n.get("projects") or []), float(n.get("resonance") or 0)),
        reverse=True,
    )
    universal = []
    for node in nodes[:limit]:
        projects = node.get("projects") or []
        if len(projects) < 1:
            continue
        universal.append(
            {
                "pattern_key": node.get("pattern_key"),
                "resonance": node.get("resonance"),
                "projects": projects,
                "fire_count": node.get("fire_count"),
                "kind": "universal_prior" if len(projects) >= 2 else "project_local",
            }
        )
    return {
        "projects_registered": len(list_projects()),
        "universal_priors": [u for u in universal if u["kind"] == "universal_prior"],
        "top_resonances": universal,
        "updated_at": data.get("updated_at"),
    }