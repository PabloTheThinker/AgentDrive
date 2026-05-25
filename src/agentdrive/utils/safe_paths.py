"""Path-traversal guards.

CodeQL "Uncontrolled data used in path expression" findings all share one
shape: an external string (HTTP body, manifest field, env var, peer-supplied
genome id) is joined onto a trusted root and then opened. The fix is to
validate the joined path resolves *inside* the root before any I/O happens.

Use :func:`safe_join` whenever an untrusted name is about to become a
filesystem path. It raises :class:`PathTraversalError` on anything outside
``root`` after resolution — relative ``..``, absolute paths, symlinks that
escape, all caught.
"""

from __future__ import annotations

from pathlib import Path


class PathTraversalError(ValueError):
    """Raised when an untrusted path component tries to escape its root."""


def safe_join(root: Path | str, *parts: str) -> Path:
    """Join ``parts`` onto ``root`` and refuse anything outside the root.

    Resolves both sides with ``Path.resolve()`` so symlink escapes are
    caught alongside literal ``../``. Returns the resolved path on success.
    """
    if not parts:
        raise PathTraversalError("safe_join requires at least one part")
    root_path = Path(root).resolve()
    candidate = root_path
    for part in parts:
        if part in ("", ".", ".."):
            raise PathTraversalError(f"Invalid path segment: {part!r}")
        as_path = Path(part)
        if as_path.is_absolute():
            raise PathTraversalError(f"Absolute path not allowed: {part!r}")
        candidate = candidate / part
    resolved = candidate.resolve()
    try:
        resolved.relative_to(root_path)
    except ValueError as exc:
        raise PathTraversalError(f"Path {resolved} escapes root {root_path}") from exc
    return resolved


def safe_name(name: str) -> str:
    """Reject names containing path separators or ``..``.

    Use when you need a single segment (not a multi-part path) and just want
    the string back unchanged after validation.
    """
    if not isinstance(name, str) or not name:
        raise PathTraversalError("safe_name requires a non-empty string")
    if "/" in name or "\\" in name or name in (".", ".."):
        raise PathTraversalError(f"Invalid name segment: {name!r}")
    if Path(name).is_absolute():
        raise PathTraversalError(f"Absolute path not allowed: {name!r}")
    return name
