"""Path-traversal guards.

CodeQL ``py/path-injection`` recognises ``os.path.realpath`` +
``os.path.commonpath`` as a sanitizer pair. We deliberately use that exact
shape instead of ``Path.resolve`` + ``Path.relative_to`` so the alert is
suppressed at the source rather than at every sink.

Use :func:`safe_join` whenever an untrusted name is about to become a
filesystem path. It raises :class:`PathTraversalError` on anything that
resolves outside ``root`` — relative ``..``, absolute paths, and symlinks
that escape the root all caught.
"""

from __future__ import annotations

import os
from pathlib import Path


class PathTraversalError(ValueError):
    """Raised when an untrusted path component tries to escape its root."""


def safe_join(root: Path | str, *parts: str) -> Path:
    """Join ``parts`` onto ``root`` and refuse anything outside the root.

    Uses ``os.path.realpath`` + ``os.path.commonpath`` (CodeQL's documented
    sanitizer for ``py/path-injection``) so static analyzers recognise the
    barrier. Symlink escapes are caught alongside literal ``..``.
    """
    if not parts:
        raise PathTraversalError("safe_join requires at least one part")

    # Cheap pre-filters — give a precise error before we touch the FS.
    for part in parts:
        if part in ("", ".", ".."):
            raise PathTraversalError(f"Invalid path segment: {part!r}")
        if os.path.isabs(part):
            raise PathTraversalError(f"Absolute path not allowed: {part!r}")

    real_root = os.path.realpath(str(root))
    real_candidate = os.path.realpath(os.path.join(real_root, *parts))

    # commonpath raises ValueError on cross-drive paths (Windows) or empty
    # input; either case is a traversal attempt.
    try:
        common = os.path.commonpath([real_root, real_candidate])
    except ValueError as exc:
        raise PathTraversalError(
            f"Path {real_candidate} could not be compared to root {real_root}"
        ) from exc
    if common != real_root:
        raise PathTraversalError(f"Path {real_candidate} escapes root {real_root}")
    return Path(real_candidate)


def safe_name(name: str) -> str:
    """Reject names containing path separators or ``..``.

    Use when you need a single segment (not a multi-part path) and just want
    the string back unchanged after validation.
    """
    if not isinstance(name, str) or not name:
        raise PathTraversalError("safe_name requires a non-empty string")
    if "/" in name or "\\" in name or name in (".", ".."):
        raise PathTraversalError(f"Invalid name segment: {name!r}")
    if os.path.isabs(name):
        raise PathTraversalError(f"Absolute path not allowed: {name!r}")
    return name
