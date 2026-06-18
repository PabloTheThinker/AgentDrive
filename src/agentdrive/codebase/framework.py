"""Crystallize observations into a project-specific pattern recognition framework."""

from __future__ import annotations

import json
import logging
from collections import Counter, defaultdict
from datetime import UTC, datetime
from typing import Any

from agentdrive.codebase.registry import framework_path, get_project, observations_path

logger = logging.getLogger(__name__)

_CRYSTALLIZE_EVERY = 3


def _load_observations(project_id: str) -> list[dict[str, Any]]:
    path = observations_path(project_id)
    if not path.is_file():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
            if isinstance(row, dict):
                rows.append(row)
        except json.JSONDecodeError:
            continue
    return rows


def _aggregate(observations: list[dict[str, Any]]) -> dict[str, Any]:
    if not observations:
        return {"patterns": [], "summary": {}, "file_count": 0}

    languages = Counter()
    frameworks = Counter()
    func_naming = Counter()
    class_naming = Counter()
    import_styles = Counter()
    bool_signals: dict[str, list[bool]] = defaultdict(list)
    dirs = Counter()

    for obs in observations:
        languages[obs.get("language", "unknown")] += 1
        for fw in obs.get("frameworks") or []:
            frameworks[fw] += 1
        sig = obs.get("signals") or {}
        if sig.get("function_naming"):
            func_naming[sig["function_naming"]] += 1
        if sig.get("class_naming"):
            class_naming[sig["class_naming"]] += 1
        if sig.get("import_style") and sig["import_style"] != "unknown":
            import_styles[sig["import_style"]] += 1
        for key in (
            "has_module_docstring",
            "uses_type_hints",
            "uses_async",
            "uses_dataclass",
            "uses_structured_logging",
            "uses_react_hooks",
            "test_file",
        ):
            if key in sig:
                bool_signals[key].append(bool(sig[key]))
        rel = obs.get("path", "")
        if "/" in rel:
            dirs[rel.split("/")[0]] += 1

    file_count = len(observations)
    patterns: list[dict[str, Any]] = []

    def _add_pattern(
        pid: str,
        category: str,
        rule: str,
        confidence: float,
        evidence: int,
        *,
        examples: list[str] | None = None,
    ) -> None:
        if confidence < 0.55:
            return
        patterns.append(
            {
                "id": pid,
                "category": category,
                "rule": rule,
                "confidence": round(confidence, 3),
                "evidence_files": evidence,
                "examples": examples or [],
            }
        )

    if languages:
        top_lang, count = languages.most_common(1)[0]
        _add_pattern(
            f"language-{top_lang}",
            "language",
            f"Primary language is {top_lang}",
            count / file_count,
            count,
        )

    if func_naming:
        style, count = func_naming.most_common(1)[0]
        _add_pattern(
            f"naming-functions-{style}",
            "naming",
            f"Functions use {style}",
            count / max(1, sum(func_naming.values())),
            count,
        )

    if class_naming:
        style, count = class_naming.most_common(1)[0]
        _add_pattern(
            f"naming-classes-{style}",
            "naming",
            f"Classes use {style}",
            count / max(1, sum(class_naming.values())),
            count,
        )

    if import_styles:
        style, count = import_styles.most_common(1)[0]
        _add_pattern(
            f"imports-{style}",
            "imports",
            f"Import style favors {style}",
            count / max(1, sum(import_styles.values())),
            count,
        )

    for key, values in bool_signals.items():
        if not values:
            continue
        rate = sum(values) / len(values)
        if rate >= 0.5:
            labels = {
                "has_module_docstring": "Files commonly open with module-level docstrings",
                "uses_type_hints": "Type hints are used consistently",
                "uses_async": "Async functions are part of the codebase style",
                "uses_dataclass": "Dataclasses are a structural pattern",
                "uses_structured_logging": "Structured logging (logger = getLogger) is standard",
                "uses_react_hooks": "React hooks are the component pattern",
                "test_file": "Test files are part of the observed surface",
            }
            _add_pattern(
                f"convention-{key}",
                "convention",
                labels.get(key, key),
                rate,
                sum(values),
            )

    for fw, count in frameworks.most_common(5):
        _add_pattern(
            f"framework-{fw}",
            "framework",
            f"Uses {fw}",
            count / file_count,
            count,
        )

    if dirs:
        top_dirs = [d for d, _ in dirs.most_common(4)]
        _add_pattern(
            "layout-top-dirs",
            "layout",
            f"Top-level organization includes: {', '.join(top_dirs)}",
            0.7,
            file_count,
            examples=top_dirs,
        )

    summary = {
        "languages": dict(languages),
        "frameworks": dict(frameworks),
        "function_naming": dict(func_naming),
        "class_naming": dict(class_naming),
        "import_styles": dict(import_styles),
        "avg_comment_density": round(
            sum((o.get("signals") or {}).get("comment_density", 0) for o in observations)
            / file_count,
            3,
        ),
    }
    return {"patterns": patterns, "summary": summary, "file_count": file_count}


def crystallize_framework(project_id: str, *, force: bool = False) -> dict[str, Any]:
    observations = _load_observations(project_id)
    project = get_project(project_id)
    if not observations:
        return {"project_id": project_id, "patterns": [], "file_count": 0, "crystallized": False}

    if not force and len(observations) % _CRYSTALLIZE_EVERY != 0:
        return {
            "project_id": project_id,
            "crystallized": False,
            "note": f"Waiting for observation batch (every {_CRYSTALLIZE_EVERY} files)",
            "file_count": len(observations),
        }

    aggregated = _aggregate(observations)
    mirror_summary = _mirror_summary(project_id)
    framework = {
        "project_id": project_id,
        "display_name": project.display_name if project else project_id,
        "root": project.root if project else "",
        "crystallized_at": datetime.now(UTC).isoformat(),
        "file_count": aggregated["file_count"],
        "patterns": aggregated["patterns"],
        "summary": aggregated["summary"],
        "writing_guide": _build_writing_guide(aggregated),
        "mirror_neurons": mirror_summary,
    }
    framework_path(project_id).write_text(
        json.dumps(framework, indent=2, default=str),
        encoding="utf-8",
    )
    return framework


def _mirror_summary(project_id: str) -> dict[str, Any]:
    try:
        from agentdrive.codebase.mirrors import mirror_summary

        return mirror_summary(project_id)
    except Exception:
        return {}


def _build_writing_guide(aggregated: dict[str, Any]) -> str:
    lines = ["# Writing guide (auto-learned)", ""]
    summary = aggregated.get("summary") or {}
    if summary.get("languages"):
        langs = ", ".join(summary["languages"].keys())
        lines.append(f"- **Languages:** {langs}")
    if summary.get("function_naming"):
        top = max(summary["function_naming"], key=summary["function_naming"].get)
        lines.append(f"- **Functions:** {top}")
    if summary.get("frameworks"):
        fws = ", ".join(summary["frameworks"].keys())
        lines.append(f"- **Frameworks:** {fws}")
    lines.append("")
    lines.append("## Patterns")
    for pat in aggregated.get("patterns") or []:
        lines.append(
            f"- [{pat['category']}] {pat['rule']} "
            f"(confidence {pat['confidence']}, n={pat['evidence_files']})"
        )
    return "\n".join(lines)


def get_writing_guide(project_id: str) -> dict[str, Any]:
    path = framework_path(project_id)
    if path.is_file():
        return json.loads(path.read_text(encoding="utf-8"))
    return crystallize_framework(project_id, force=True)


def match_against_framework(
    project_id: str,
    *,
    code: str,
    path: str = "snippet.py",
) -> dict[str, Any]:
    from agentdrive.codebase.analyzer import analyze_content

    framework = get_writing_guide(project_id)
    patterns = framework.get("patterns") or []
    if not patterns:
        return {
            "project_id": project_id,
            "aligned": [],
            "conflicts": [],
            "note": "No framework yet — observe files first",
        }

    snippet = analyze_content(path=path, content=code)
    aligned: list[dict[str, Any]] = []
    conflicts: list[dict[str, Any]] = []

    for pat in patterns:
        pid = pat.get("id", "")
        rule = pat.get("rule", "")
        conf = float(pat.get("confidence") or 0)

        if pid.startswith("naming-functions-"):
            expected = pid.replace("naming-functions-", "")
            actual = (snippet.signals or {}).get("function_naming", "unknown")
            if actual == expected or actual == "unknown":
                aligned.append({"pattern": pid, "rule": rule, "confidence": conf})
            else:
                conflicts.append(
                    {
                        "pattern": pid,
                        "rule": rule,
                        "expected": expected,
                        "actual": actual,
                    }
                )
        elif pid.startswith("language-"):
            expected = pid.replace("language-", "")
            if snippet.language == expected:
                aligned.append({"pattern": pid, "rule": rule, "confidence": conf})
        elif pid.startswith("framework-"):
            expected = pid.replace("framework-", "")
            if expected in snippet.frameworks:
                aligned.append({"pattern": pid, "rule": rule, "confidence": conf})
        elif pid.startswith("convention-uses_type_hints"):
            if snippet.signals.get("uses_type_hints"):
                aligned.append({"pattern": pid, "rule": rule, "confidence": conf})
            elif "def " in code:
                conflicts.append(
                    {"pattern": pid, "rule": rule, "expected": "type hints", "actual": "none"}
                )

    score = len(aligned) / max(1, len(patterns))
    return {
        "project_id": project_id,
        "alignment_score": round(score, 3),
        "aligned": aligned,
        "conflicts": conflicts,
        "snippet_signals": snippet.to_dict(),
    }
