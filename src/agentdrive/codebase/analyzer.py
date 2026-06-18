"""Heuristic file analysis — extract writing-style signals without AST deps."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

_PY_CLASS = re.compile(r"^class\s+([A-Za-z_][A-Za-z0-9_]*)", re.MULTILINE)
_PY_FUNC = re.compile(r"^def\s+([A-Za-z_][A-Za-z0-9_]*)", re.MULTILINE)
_PY_ASYNC = re.compile(r"^async\s+def\s+", re.MULTILINE)
_PY_TYPE_HINT = re.compile(r"->\s*[^:]+:|:\s*[A-Za-z_\[]")
_PY_DATACLASS = re.compile(r"@dataclass")
_PY_LOGGER = re.compile(r"logger\s*=\s*logging\.getLogger")
_PY_REL_IMPORT = re.compile(r"^from\s+\.", re.MULTILINE)
_PY_ABS_IMPORT = re.compile(r"^from\s+[a-zA-Z]", re.MULTILINE)

_TS_FUNC = re.compile(r"(?:export\s+)?(?:async\s+)?function\s+([A-Za-z_$][\w$]*)")
_TS_ARROW = re.compile(r"(?:export\s+)?const\s+([A-Za-z_$][\w$]*)\s*=\s*(?:async\s*)?\(")
_TS_INTERFACE = re.compile(r"(?:export\s+)?interface\s+([A-Za-z_$][\w$]*)")
_TS_TYPE = re.compile(r"(?:export\s+)?type\s+([A-Za-z_$][\w$]*)")
_TS_HOOK = re.compile(r"use[A-Z][A-Za-z]+")

_CAMEL = re.compile(r"^[a-z]+(?:[A-Z][a-z0-9]*)+$")
_SNAKE = re.compile(r"^[a-z][a-z0-9]*(?:_[a-z0-9]+)*$")
_PASCAL = re.compile(r"^[A-Z][a-zA-Z0-9]*$")


@dataclass
class FileSignals:
    path: str
    language: str
    lines: int
    signals: dict[str, Any] = field(default_factory=dict)
    identifiers: dict[str, list[str]] = field(default_factory=dict)
    frameworks: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "language": self.language,
            "lines": self.lines,
            "signals": self.signals,
            "identifiers": self.identifiers,
            "frameworks": self.frameworks,
        }


def detect_language(path: str) -> str:
    ext = Path(path).suffix.lower()
    return {
        ".py": "python",
        ".ts": "typescript",
        ".tsx": "typescript",
        ".js": "javascript",
        ".jsx": "javascript",
        ".go": "go",
        ".rs": "rust",
        ".md": "markdown",
        ".json": "json",
        ".yaml": "yaml",
        ".yml": "yaml",
    }.get(ext, "unknown")


def _naming_style(names: list[str]) -> str:
    if not names:
        return "unknown"
    snake = sum(1 for n in names if _SNAKE.match(n))
    camel = sum(1 for n in names if _CAMEL.match(n))
    pascal = sum(1 for n in names if _PASCAL.match(n))
    total = len(names)
    if snake / total >= 0.6:
        return "snake_case"
    if camel / total >= 0.5:
        return "camelCase"
    if pascal / total >= 0.5:
        return "PascalCase"
    return "mixed"


def _detect_frameworks(content: str, path: str) -> list[str]:
    hits: list[str] = []
    checks = [
        ("fastapi", r"FastAPI|from fastapi"),
        ("pytest", r"import pytest|@pytest"),
        ("nextjs", r"from ['\"]next/|next\.config"),
        ("react", r"from ['\"]react['\"]|useState|useEffect"),
        ("clerk", r"@clerk/|clerkMiddleware"),
        ("convex", r"from ['\"]convex|convex/"),
        ("pydantic", r"from pydantic|BaseModel"),
        ("mcp", r"FastMCP|mcp\.server"),
        ("tailwind", r"tailwindcss|@tailwind"),
    ]
    blob = content[:8000]
    for name, pattern in checks:
        if re.search(pattern, blob):
            hits.append(name)
    if "/test" in path or path.startswith("test_") or "_test." in path:
        if "pytest" not in hits:
            hits.append("tests")
    return hits


def analyze_content(*, path: str, content: str) -> FileSignals:
    language = detect_language(path)
    lines = content.count("\n") + (1 if content else 0)
    signals: dict[str, Any] = {
        "has_module_docstring": False,
        "uses_type_hints": False,
        "uses_async": False,
        "uses_dataclass": False,
        "uses_structured_logging": False,
        "import_style": "unknown",
        "comment_density": 0.0,
        "test_file": False,
    }
    identifiers: dict[str, list[str]] = {
        "functions": [],
        "classes": [],
        "types": [],
    }
    frameworks = _detect_frameworks(content, path)

    if language == "python":
        stripped = content.lstrip()
        signals["has_module_docstring"] = stripped.startswith(('"""', "'''"))
        signals["uses_type_hints"] = bool(_PY_TYPE_HINT.search(content))
        signals["uses_async"] = bool(_PY_ASYNC.search(content))
        signals["uses_dataclass"] = bool(_PY_DATACLASS.search(content))
        signals["uses_structured_logging"] = bool(_PY_LOGGER.search(content))
        rel = len(_PY_REL_IMPORT.findall(content))
        ab = len(_PY_ABS_IMPORT.findall(content))
        if rel > ab:
            signals["import_style"] = "relative"
        elif ab > 0:
            signals["import_style"] = "absolute"
        identifiers["functions"] = _PY_FUNC.findall(content)[:40]
        identifiers["classes"] = _PY_CLASS.findall(content)[:30]
        signals["function_naming"] = _naming_style(identifiers["functions"])
        signals["class_naming"] = _naming_style(identifiers["classes"])

    elif language in ("typescript", "javascript"):
        identifiers["functions"] = (
            _TS_FUNC.findall(content)[:40] + _TS_ARROW.findall(content)[:20]
        )
        identifiers["types"] = _TS_INTERFACE.findall(content)[:20] + _TS_TYPE.findall(content)[:20]
        signals["function_naming"] = _naming_style(identifiers["functions"])
        signals["uses_react_hooks"] = bool(_TS_HOOK.search(content))
        if content.strip().startswith("/**") or content.lstrip().startswith("//"):
            signals["has_module_docstring"] = True
        signals["uses_async"] = "async " in content
        if "import type" in content:
            signals["import_style"] = "type_imports"
        elif "from '@/" in content or 'from "@/' in content:
            signals["import_style"] = "path_alias"

    comment_lines = sum(
        1
        for line in content.splitlines()
        if line.strip().startswith(("#", "//", "/*", "*"))
    )
    signals["comment_density"] = round(comment_lines / max(1, lines), 3)
    signals["test_file"] = (
        "/test" in path.replace("\\", "/")
        or path.startswith("test_")
        or path.endswith("_test.py")
        or ".test." in path
        or ".spec." in path
    )

    return FileSignals(
        path=path,
        language=language,
        lines=lines,
        signals=signals,
        identifiers=identifiers,
        frameworks=frameworks,
    )