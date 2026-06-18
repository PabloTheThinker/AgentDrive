"""
Import dialogue transcripts into the Memory Bank.

Reads JSONL or plain-text session exports and stores full-text shards without
rewriting or summarizing the source messages.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Iterator

from agentdrive.memory.scope import resolve_topic
from agentdrive.memory.store import MemoryBankStore

logger = logging.getLogger(__name__)

SHARD_CHARS = 800
MIN_CHARS = 30


def _iter_jsonl_messages(path: Path) -> Iterator[dict[str, Any]]:
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(row, dict):
            continue
        role = str(row.get("role") or row.get("type") or "unknown")
        content = row.get("content") or row.get("text") or row.get("message") or ""
        if isinstance(content, list):
            parts: list[str] = []
            for block in content:
                if isinstance(block, dict) and block.get("text"):
                    parts.append(str(block["text"]))
                elif isinstance(block, str):
                    parts.append(block)
            content = "\n".join(parts)
        content = str(content).strip()
        if len(content) >= MIN_CHARS:
            yield {"role": role, "content": content, "origin_path": str(path)}


def _split_shards(text: str, *, size: int = SHARD_CHARS) -> list[str]:
    if len(text) <= size:
        return [text]
    shards: list[str] = []
    offset = 0
    while offset < len(text):
        shards.append(text[offset : offset + size])
        offset += size
    return shards


def import_dialogue_file(
    path: str | Path,
    *,
    swarm_id: str,
    vault: str = "",
    program_id: str = "dialogue-import",
) -> dict[str, Any]:
    file_path = Path(path).expanduser().resolve()
    if not file_path.is_file():
        raise FileNotFoundError(f"Dialogue file not found: {file_path}")

    store = MemoryBankStore(swarm_id)
    vault_name = vault or file_path.parent.name or "dialogues"
    imported = 0
    skipped = 0

    if file_path.suffix == ".jsonl":
        for index, message in enumerate(_iter_jsonl_messages(file_path)):
            role = message["role"]
            for shard_index, shard in enumerate(_split_shards(message["content"])):
                title = f"Dialogue {file_path.name} [{role}] #{index}"
                if store.has_similar(title, shard):
                    skipped += 1
                    continue
                store.store(
                    kind="episode",
                    title=title,
                    content=shard,
                    confidence=0.7,
                    source="dialogue_import",
                    program_id=program_id,
                    tags=["dialogue", "full_text", vault_name, role],
                    links=[{"type": "origin_path", "id": str(file_path)}],
                    vault=vault_name,
                    topic=resolve_topic("episode", [role, vault_name]),
                    origin_path=str(file_path),
                    shard_index=shard_index,
                    preserves_source=True,
                )
                imported += 1
    else:
        text = file_path.read_text(encoding="utf-8", errors="replace")
        for shard_index, shard in enumerate(_split_shards(text)):
            title = f"Dialogue {file_path.name} shard {shard_index}"
            if store.has_similar(title, shard):
                skipped += 1
                continue
            store.store(
                kind="episode",
                title=title,
                content=shard,
                confidence=0.65,
                source="dialogue_import",
                program_id=program_id,
                tags=["dialogue", "full_text", vault_name],
                vault=vault_name,
                topic="dialogues",
                origin_path=str(file_path),
                shard_index=shard_index,
                preserves_source=True,
            )
            imported += 1

    return {
        "path": str(file_path),
        "vault": vault_name,
        "imported": imported,
        "skipped": skipped,
        "swarm_id": swarm_id,
    }


def import_dialogue_directory(
    directory: str | Path,
    *,
    swarm_id: str,
    vault: str = "",
    pattern: str = "*.jsonl",
) -> dict[str, Any]:
    root = Path(directory).expanduser().resolve()
    if not root.is_dir():
        raise NotADirectoryError(f"Directory not found: {root}")

    total_imported = 0
    total_skipped = 0
    files: list[dict[str, Any]] = []
    for path in sorted(root.rglob(pattern)):
        if not path.is_file():
            continue
        try:
            result = import_dialogue_file(path, swarm_id=swarm_id, vault=vault)
            total_imported += result["imported"]
            total_skipped += result["skipped"]
            files.append(result)
        except Exception:
            logger.debug("Dialogue import failed for %s", path, exc_info=True)

    return {
        "directory": str(root),
        "files_processed": len(files),
        "imported": total_imported,
        "skipped": total_skipped,
        "files": files,
        "swarm_id": swarm_id,
    }
