"""
Configuration management for Savant Framework.

- ~/.agentdrive/config.yaml for user settings
- ~/.agentdrive/.env for secrets (API keys etc.)
- Strong defaults
- Caching, warnings on parse failure
- Context-aware AGENTDRIVE_HOME
- Simple API: load_config(), save_config(), get_config_value()

Also initializes logging and provides get_logger().
"""

import logging
import sys
import threading
from pathlib import Path
from typing import Any

import yaml

from agentdrive.constants import (
    SAVANT_VERSION,
    get_agentdrive_home,
    get_savant_config_path,
)
from agentdrive.exceptions import (
    SavantConfigError,
)

logger = logging.getLogger(__name__)

# =============================================================================
# Defaults (minimal but extensible)
# =============================================================================

DEFAULT_CONFIG: dict[str, Any] = {
    "version": 1,
    "agentdrive": {
        "home": str(get_agentdrive_home()),
        "log_level": "INFO",
        "default_worker": "external",
    },
    "registry": {
        "auto_register_examples": True,
    },
    "scanners": {
        "enabled": ["framework", "reasoning", "tool_composition"],
        "default": "framework",
    },
    "orchestrator": {
        "default_worker_adapter": "external",
        "max_workers": 4,
    },
    "tui": {
        "skin": "default",
        "show_banner": True,
    },
    "integration": {
        "external": {
            "enabled": True,
            "auto_detect_home": True,
            "home": None,
        },
    },
    "pool": {
        "global": {
            "isolation_level": "subagent",
            "auto_ingest_on_success": True,
            "min_quality_for_ingest": 0.75,
            "sharing_policy": "selective",
            "retention_days": 0,
            "allow_upward_proposals": True,
        },
        "swarms": {},
        # per-subagent overrides can be added under "subagents": {"swarm:sub": {...}}
    },
}


# =============================================================================
# Internal state (thread-safe)
# =============================================================================

_CONFIG_LOCK = threading.RLock()
_LOAD_CONFIG_CACHE: dict[str, tuple[int, int, dict[str, Any]]] = {}
_RAW_CONFIG_CACHE: dict[str, tuple[int, int, dict[str, Any]]] = {}
_CONFIG_PARSE_WARNED: set = set()


def _get_config_path() -> Path:
    return get_savant_config_path()


def _ensure_home() -> Path:
    home = get_agentdrive_home()
    home.mkdir(parents=True, exist_ok=True)
    (home / "genomes").mkdir(exist_ok=True)
    (home / "logs").mkdir(exist_ok=True)
    (home / "cache").mkdir(exist_ok=True)
    (home / "pool").mkdir(exist_ok=True)
    (home / "swarms").mkdir(exist_ok=True)
    return home


def ensure_savant_home() -> Path:
    """Public wrapper to ensure the Savant home directory tree exists."""
    return _ensure_home()


def _warn_config_parse_failure(config_path: Path, exc: Exception) -> None:
    """Warn once per (path, mtime, size) about bad config.yaml."""
    try:
        st = config_path.stat()
        key = (str(config_path), st.st_mtime_ns, st.st_size)
    except OSError:
        key = (str(config_path), 0, 0)
    if key in _CONFIG_PARSE_WARNED:
        return
    _CONFIG_PARSE_WARNED.add(key)

    msg = (
        f"Failed to parse {config_path}: {exc}. "
        f"Falling back to DEFAULT_CONFIG. Fix your config.yaml."
    )
    logger.warning(msg)
    try:
        sys.stderr.write(f"⚠️  savant config: {msg}\n")
        sys.stderr.flush()
    except Exception:
        pass


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    """Recursively merge override into base (override wins)."""
    result = base.copy()
    for k, v in override.items():
        if k in result and isinstance(result[k], dict) and isinstance(v, dict):
            result[k] = _deep_merge(result[k], v)
        else:
            result[k] = v
    return result


def _normalize_config(cfg: dict[str, Any]) -> dict[str, Any]:
    """Apply any normalization / migration."""
    cfg = cfg.copy()
    cfg.setdefault("version", 1)
    # Ensure required top level
    for section in (
        "agentdrive",
        "registry",
        "scanners",
        "orchestrator",
        "tui",
        "integration",
        "drive",
    ):
        cfg.setdefault(section, {})
    return cfg


def load_config(force_reload: bool = False) -> dict[str, Any]:
    """
    Load the merged configuration (defaults + user overrides).

    Uses mtime-based caching for performance.
    Thread-safe.
    """
    with _CONFIG_LOCK:
        path = _get_config_path()
        _ensure_home()

        if not force_reload and path.exists():
            try:
                st = path.stat()
                key = (str(path), st.st_mtime_ns, st.st_size)
                if key in _LOAD_CONFIG_CACHE:
                    return _LOAD_CONFIG_CACHE[key][2].copy()
            except OSError:
                pass

        user_cfg: dict[str, Any] = {}
        if path.exists():
            try:
                with open(path, encoding="utf-8") as f:
                    loaded = yaml.safe_load(f) or {}
                if not isinstance(loaded, dict):
                    loaded = {}
                user_cfg = loaded
            except Exception as exc:
                _warn_config_parse_failure(path, exc)
                user_cfg = {}

        merged = _deep_merge(DEFAULT_CONFIG, user_cfg)
        merged = _normalize_config(merged)

        # Cache it
        try:
            st = path.stat() if path.exists() else None
            if st:
                key = (str(path), st.st_mtime_ns, st.st_size)
                _LOAD_CONFIG_CACHE[key] = (st.st_mtime_ns, st.st_size, merged.copy())
        except OSError:
            pass

        return merged.copy()


def read_raw_config() -> dict[str, Any]:
    """Return only the on-disk user config (no defaults merged)."""
    with _CONFIG_LOCK:
        path = _get_config_path()
        if not path.exists():
            return {}
        try:
            st = path.stat()
            key = (str(path), st.st_mtime_ns, st.st_size)
            if key in _RAW_CONFIG_CACHE:
                return _RAW_CONFIG_CACHE[key][2].copy()
            with open(path, encoding="utf-8") as f:
                raw = yaml.safe_load(f) or {}
            _RAW_CONFIG_CACHE[key] = (
                st.st_mtime_ns,
                st.st_size,
                raw.copy() if isinstance(raw, dict) else {},
            )
            return raw.copy() if isinstance(raw, dict) else {}
        except Exception as exc:
            _warn_config_parse_failure(path, exc)
            return {}


def save_config(config: dict[str, Any]) -> Path:
    """Atomically save user config (only the parts the user cares about; we store full for simplicity)."""
    with _CONFIG_LOCK:
        path = _get_config_path()
        _ensure_home()
        # Write atomically
        tmp = path.with_suffix(".yaml.tmp")
        try:
            with open(tmp, "w", encoding="utf-8") as f:
                yaml.safe_dump(config, f, sort_keys=False, indent=2)
            tmp.replace(path)
            # Invalidate caches
            _LOAD_CONFIG_CACHE.clear()
            _RAW_CONFIG_CACHE.clear()
            logger.info(f"Saved Savant config to {path}")
            return path
        except Exception as e:
            if tmp.exists():
                tmp.unlink(missing_ok=True)
            raise SavantConfigError(f"Failed to save config: {e}") from e


def get_config_value(key: str, default: Any = None) -> Any:
    """Dot-path access e.g. get_config_value('orchestrator.max_workers')"""
    cfg = load_config()
    parts = key.split(".")
    val = cfg
    for p in parts:
        if isinstance(val, dict) and p in val:
            val = val[p]
        else:
            return default
    return val


def set_config_value(key: str, value: Any) -> None:
    """Set a value in the user config and persist (shallow for now)."""
    raw = read_raw_config()
    # naive deep set
    parts = key.split(".")
    d = raw
    for p in parts[:-1]:
        d = d.setdefault(p, {})
    d[parts[-1]] = value
    save_config(raw)


# =============================================================================
# Logging setup (production-grade, configurable)
# =============================================================================

_LOGGING_CONFIGURED = False


def setup_logging(level: str | None = None, log_file: Path | None = None) -> None:
    """Configure root + savant logger. Call early in CLI entry."""
    global _LOGGING_CONFIGURED
    if _LOGGING_CONFIGURED:
        return

    cfg = load_config()
    lvl = level or cfg.get("agentdrive", {}).get("log_level", "INFO")
    numeric = getattr(logging, lvl.upper(), logging.INFO)

    log_dir = get_agentdrive_home() / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    if log_file is None:
        log_file = log_dir / "agentdrive.log"

    fmt = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    datefmt = "%Y-%m-%d %H:%M:%S"

    handlers: list[logging.Handler] = [logging.StreamHandler(sys.stderr)]
    try:
        fh = logging.FileHandler(log_file, encoding="utf-8")
        fh.setFormatter(logging.Formatter(fmt, datefmt))
        handlers.append(fh)
    except Exception:
        pass  # fallback to stderr only

    root = logging.getLogger()
    root.setLevel(numeric)
    for h in handlers:
        h.setFormatter(logging.Formatter(fmt, datefmt))
        root.addHandler(h)

    # Quieten noisy libs
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)

    logger.info(f"AgentDrive v{SAVANT_VERSION} logging initialized (level={lvl}, file={log_file})")
    _LOGGING_CONFIGURED = True


def get_logger(name: str | None = None) -> logging.Logger:
    """Convenience: get a namespaced logger (auto-inits logging if needed)."""
    if not _LOGGING_CONFIGURED:
        setup_logging()
    return logging.getLogger(name or "agentdrive")


# Auto-ensure home on import of config (lightweight)
_ensure_home()
