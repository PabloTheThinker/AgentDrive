"""Extract motor-program exemplars from observed source (what to imitate)."""

from __future__ import annotations

import re
from typing import Any

_PY_FUNC_BLOCK = re.compile(
    r"^((?:async\s+)?def\s+[A-Za-z_][A-Za-z0-9_]*\([^)]*\)(?:\s*->[^:]+)?:)(.*?)(?=^(?:async\s+)?def\s+|^class\s+|\Z)",
    re.MULTILINE | re.DOTALL,
)
_PY_CLASS_BLOCK = re.compile(
    r"^(class\s+[A-Za-z_][A-Za-z0-9_]*[^:]*:)(.*?)(?=^class\s+|^(?:async\s+)?def\s+|\Z)",
    re.MULTILINE | re.DOTALL,
)
_TS_EXPORT = re.compile(
    r"^((?:export\s+)?(?:async\s+)?function\s+[A-Za-z_$][\w$]*\([^)]*\)[^{]*\{)(.*?)(?=^(?:export\s+)?(?:async\s+)?function\s+|\Z)",
    re.MULTILINE | re.DOTALL,
)
_IMPORT_LINE = re.compile(r"^(?:from|import)\s+.+$", re.MULTILINE)


def _trim_body(body: str, *, max_chars: int = 480) -> str:
    lines = [ln for ln in body.splitlines() if ln.strip()]
    text = "\n".join(lines[:12])
    if len(text) > max_chars:
        text = text[: max_chars - 3].rstrip() + "..."
    return text


def extract_exemplars(*, path: str, content: str, language: str) -> list[dict[str, Any]]:
    """Pull concrete code fragments the mirror layer can replay (motor programs)."""
    exemplars: list[dict[str, Any]] = []
    imports = _IMPORT_LINE.findall(content)[:6]

    if language == "python":
        for match in _PY_FUNC_BLOCK.finditer(content):
            header = match.group(1).strip()
            body = _trim_body(match.group(2))
            name_m = re.search(r"def\s+([A-Za-z_][A-Za-z0-9_]*)", header)
            if not name_m:
                continue
            exemplars.append(
                {
                    "kind": "function",
                    "name": name_m.group(1),
                    "signature": header,
                    "body": body,
                    "motor_template": f"{header}\n{body}",
                    "path": path,
                }
            )
            if len(exemplars) >= 6:
                break
        for match in _PY_CLASS_BLOCK.finditer(content):
            header = match.group(1).strip()
            body = _trim_body(match.group(2), max_chars=360)
            name_m = re.search(r"class\s+([A-Za-z_][A-Za-z0-9_]*)", header)
            if not name_m:
                continue
            exemplars.append(
                {
                    "kind": "class",
                    "name": name_m.group(1),
                    "signature": header,
                    "body": body,
                    "motor_template": f"{header}\n{body}",
                    "path": path,
                }
            )
            if len(exemplars) >= 8:
                break

    elif language in ("typescript", "javascript"):
        for match in _TS_EXPORT.finditer(content):
            header = match.group(1).strip()
            body = _trim_body(match.group(2))
            name_m = re.search(r"function\s+([A-Za-z_$][\w$]*)", header)
            if not name_m:
                continue
            exemplars.append(
                {
                    "kind": "function",
                    "name": name_m.group(1),
                    "signature": header,
                    "body": body,
                    "motor_template": f"{header}\n{body}",
                    "path": path,
                }
            )
            if len(exemplars) >= 6:
                break

    if imports:
        exemplars.insert(
            0,
            {
                "kind": "imports",
                "name": "import_block",
                "signature": "",
                "body": "\n".join(imports),
                "motor_template": "\n".join(imports),
                "path": path,
            },
        )

    return exemplars[:10]