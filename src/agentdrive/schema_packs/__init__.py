"""
Schema Packs for AgentDrive.

Lightweight, evolvable typing for raw drive pages + genomes + captures + observations.
Complements the strong, versioned Genome typing system.

Exposes:
- DriveSchemaPack + PageType (core models with resolution)
- AGENTDRIVE_DRIVE_PACK (the canonical starter pack powering page types, source_boost, experience layer boosts, and graph signal integration)
- Manager + activate_pack / load_active_pack (runtime switch + flows)
- detect / suggest / review helpers
- YAML (de)serialization for self-ingestion of schema work

Page type resolution and evolution flows are used across synthesis (for schema-aware scoring), knowledge_graph (source_boost), drive hybrid retrieval, and experience layer.
"""

from .pack import (
    AGENTDRIVE_DRIVE_PACK,
    DEFAULT_PACK,
    DriveSchemaPack,
    PageType,
    SchemaPackManager,
    activate_pack,
    detect_schema,
    get_schema_pack_manager,
    load_active_pack,
    load_pack_from_yaml,
    review_page_inference,
    serialize_active_pack_to_yaml,
    suggest_new_pack_version,
    suggest_page_types,
)

__all__ = [
    "DriveSchemaPack",
    "PageType",
    "AGENTDRIVE_DRIVE_PACK",
    "DEFAULT_PACK",
    "SchemaPackManager",
    "get_schema_pack_manager",
    "load_active_pack",
    "activate_pack",
    "detect_schema",
    "suggest_page_types",
    "review_page_inference",
    "load_pack_from_yaml",
    "serialize_active_pack_to_yaml",
    "suggest_new_pack_version",
]
