"""
MCP client configuration helpers — resolve launchers, emit configs, doctor checks.

Designed so any AI model can connect after ``pip install agentdrive[mcp]``,
``git clone`` + editable install, or the root ``install.sh`` — without guessing
binary paths or client-specific JSON/TOML formats.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

from agentdrive.constants import get_agentdrive_home

MCP_TRANSPORT_ARGS = ["--transport", "stdio"]
MCP_SERVER_NAME = "agentdrive"

ClientId = Literal[
    "grok",
    "claude",
    "cursor",
    "continue",
    "vscode",
    "windsurf",
    "generic",
]


@dataclass(frozen=True)
class McpLauncher:
    """How to start the AgentDrive MCP server for stdio clients."""

    method: Literal["binary", "module", "uvx"]
    command: str
    args: list[str]
    env: dict[str, str] = field(default_factory=dict)
    notes: str = ""

    def to_mcp_json(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "command": self.command,
            "args": list(self.args),
        }
        if self.env:
            payload["env"] = dict(self.env)
        return payload


def _clean_env() -> dict[str, str]:
    """Env vars that keep MCP subprocesses stable across parent shells."""
    env: dict[str, str] = {"PYTHONUNBUFFERED": "1"}
    home = get_agentdrive_home()
    env.setdefault("AGENTDRIVE_HOME", str(home))
    return env


def resolve_mcp_launcher(*, prefer_uvx: bool = False) -> McpLauncher:
    """Pick the most reliable launcher for the current installation."""
    clean = _clean_env()

    if prefer_uvx and shutil.which("uvx"):
        return McpLauncher(
            method="uvx",
            command="uvx",
            args=["--from", "agentdrive[mcp]", "agentdrive-mcp", *MCP_TRANSPORT_ARGS],
            env=clean,
            notes="Zero-install via uvx (no venv required)",
        )

    binary = shutil.which("agentdrive-mcp")
    if binary:
        return McpLauncher(
            method="binary",
            command=binary,
            args=list(MCP_TRANSPORT_ARGS),
            env=clean,
            notes=f"On PATH: {binary}",
        )

    venv_bin = get_agentdrive_home() / "venv" / "bin" / "agentdrive-mcp"
    if venv_bin.is_file():
        return McpLauncher(
            method="binary",
            command=str(venv_bin),
            args=list(MCP_TRANSPORT_ARGS),
            env=clean,
            notes=f"Installer venv: {venv_bin}",
        )

    local_bin = Path.home() / ".local" / "bin" / "agentdrive-mcp"
    if local_bin.is_file():
        return McpLauncher(
            method="binary",
            command=str(local_bin),
            args=list(MCP_TRANSPORT_ARGS),
            env=clean,
            notes=f"User shim: {local_bin}",
        )

    return McpLauncher(
        method="module",
        command=sys.executable,
        args=["-m", "agentdrive.adapters.mcp_server", *MCP_TRANSPORT_ARGS],
        env=clean,
        notes="Python module fallback (works for editable clone installs)",
    )


def get_mcp_server_block(*, prefer_uvx: bool = False) -> dict[str, Any]:
    """Standard ``mcpServers.agentdrive`` JSON block."""
    launcher = resolve_mcp_launcher(prefer_uvx=prefer_uvx)
    return {MCP_SERVER_NAME: launcher.to_mcp_json()}


def get_grok_toml_snippet(*, prefer_uvx: bool = False) -> str:
    launcher = resolve_mcp_launcher(prefer_uvx=prefer_uvx)
    args_toml = ", ".join(json.dumps(a) for a in launcher.args)
    return (
        f"[mcp_servers.{MCP_SERVER_NAME}]\n"
        f'command = "{launcher.command}"\n'
        f"args = [{args_toml}]\n"
        f"enabled = true\n"
    )


def get_grok_cli_command(*, prefer_uvx: bool = False) -> str:
    launcher = resolve_mcp_launcher(prefer_uvx=prefer_uvx)
    args = " ".join(launcher.args)
    return f'grok mcp add {MCP_SERVER_NAME} --command {launcher.command} --args "{args}"'


def client_config_paths() -> dict[ClientId, list[Path]]:
    """Known config file locations per client (first match wins on write)."""
    home = Path.home()
    paths: dict[ClientId, list[Path]] = {
        "grok": [home / ".grok" / "config.toml"],
        "claude": [
            home / ".config" / "claude" / "claude_desktop_config.json",
            home / "Library" / "Application Support" / "Claude" / "claude_desktop_config.json",
            home / ".claude" / "claude_desktop_config.json",
        ],
        "cursor": [
            home / ".cursor" / "mcp.json",
            home / ".config" / "cursor" / "mcp.json",
        ],
        "continue": [
            home / ".continue" / "config.json",
            home / ".continue" / "config.yaml",
        ],
        "vscode": [
            home / ".vscode" / "mcp.json",
        ],
        "windsurf": [
            home / ".codeium" / "windsurf" / "mcp_config.json",
            home / ".windsurf" / "mcp.json",
        ],
        "generic": [],
    }
    return paths


def _merge_json_mcp(path: Path, server_block: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    data: dict[str, Any] = {}
    if path.is_file():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            data = {}
    servers = data.setdefault("mcpServers", {})
    if not isinstance(servers, dict):
        servers = {}
        data["mcpServers"] = servers
    servers.update(server_block)
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def _merge_cursor_mcp(path: Path, server_block: dict[str, Any]) -> None:
    """Cursor uses ``{ mcpServers: ... }`` or ``{ mcp: { servers: ... } }``."""
    path.parent.mkdir(parents=True, exist_ok=True)
    data: dict[str, Any] = {}
    if path.is_file():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            data = {}
    if "mcpServers" in data or "mcp" not in data:
        servers = data.setdefault("mcpServers", {})
        if isinstance(servers, dict):
            servers.update(server_block)
    else:
        mcp = data.setdefault("mcp", {})
        if not isinstance(mcp, dict):
            mcp = {}
            data["mcp"] = mcp
        servers = mcp.setdefault("servers", {})
        if not isinstance(servers, dict):
            servers = {}
            mcp["servers"] = servers
        servers.update(server_block)
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def _merge_grok_toml(path: Path, snippet: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    marker = f"[mcp_servers.{MCP_SERVER_NAME}]"
    if path.is_file():
        text = path.read_text(encoding="utf-8")
        if marker in text:
            return
        if not text.endswith("\n"):
            text += "\n"
        text += "\n" + snippet
        path.write_text(text, encoding="utf-8")
    else:
        path.write_text(snippet, encoding="utf-8")


def write_client_config(
    client: ClientId,
    *,
    prefer_uvx: bool = False,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Merge AgentDrive MCP config into a client config file."""
    server_block = get_mcp_server_block(prefer_uvx=prefer_uvx)
    candidates = client_config_paths().get(client, [])
    target: Path | None = None
    for cand in candidates:
        if cand.parent.exists() or client in ("cursor", "grok", "claude"):
            target = cand
            break
    if target is None and candidates:
        target = candidates[0]

    result: dict[str, Any] = {
        "client": client,
        "written": False,
        "path": str(target) if target else None,
        "server_block": server_block,
    }
    if dry_run or target is None:
        return result

    if client == "grok":
        _merge_grok_toml(target, get_grok_toml_snippet(prefer_uvx=prefer_uvx))
    elif client == "cursor":
        _merge_cursor_mcp(target, server_block)
    elif client in ("claude", "continue", "vscode", "windsurf", "generic"):
        _merge_json_mcp(target, server_block)
    else:
        _merge_json_mcp(target, server_block)

    result["written"] = True
    return result


def try_grok_mcp_add(*, prefer_uvx: bool = False) -> dict[str, Any]:
    """Run ``grok mcp add`` when the Grok CLI is available."""
    grok = shutil.which("grok")
    if not grok:
        return {"ok": False, "reason": "grok CLI not on PATH"}
    launcher = resolve_mcp_launcher(prefer_uvx=prefer_uvx)
    cmd = [
        grok,
        "mcp",
        "add",
        MCP_SERVER_NAME,
        "--command",
        launcher.command,
        "--args",
        " ".join(launcher.args),
    ]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=30, check=False)
        return {
            "ok": proc.returncode == 0,
            "returncode": proc.returncode,
            "stdout": (proc.stdout or "").strip(),
            "stderr": (proc.stderr or "").strip(),
            "command": " ".join(cmd),
        }
    except Exception as exc:
        return {"ok": False, "reason": str(exc), "command": " ".join(cmd)}


def mcp_package_available() -> bool:
    try:
        import mcp.server.fastmcp  # noqa: F401

        return True
    except ImportError:
        return False


def count_mcp_tools() -> int:
    from agentdrive.adapters.mcp_server import create_mcp_server

    server = create_mcp_server()
    return len(server._tool_manager._tools)  # noqa: SLF001


def list_mcp_tool_names() -> list[str]:
    from agentdrive.adapters.mcp_server import create_mcp_server

    server = create_mcp_server()
    return sorted(server._tool_manager._tools.keys())  # noqa: SLF001


def run_mcp_doctor(*, prefer_uvx: bool = False) -> dict[str, Any]:
    """Structured health report for MCP connectivity."""
    launcher = resolve_mcp_launcher(prefer_uvx=prefer_uvx)
    report: dict[str, Any] = {
        "ok": True,
        "launcher": {
            "method": launcher.method,
            "command": launcher.command,
            "args": launcher.args,
            "notes": launcher.notes,
        },
        "checks": [],
    }

    def _check(name: str, ok: bool, detail: str) -> None:
        report["checks"].append({"name": name, "ok": ok, "detail": detail})
        if not ok:
            report["ok"] = False

    _check("mcp package", mcp_package_available(), "pip install agentdrive[mcp]")
    if launcher.method == "binary":
        _check(
            "binary exists",
            Path(launcher.command).is_file() or bool(shutil.which(launcher.command)),
            launcher.command,
        )
    else:
        _check("launcher", True, launcher.notes)

    try:
        tool_count = count_mcp_tools()
        _check("tool registration", tool_count >= 25, f"{tool_count} tools registered")
        report["tool_count"] = tool_count
    except Exception as exc:
        _check("tool registration", False, str(exc))
        report["tool_count"] = 0

    try:
        from agentdrive.operations import export_operations_json

        ops = json.loads(export_operations_json())
        with_mcp = sum(1 for op in ops if op.get("mcp_tool"))
        _check(
            "operations registry",
            with_mcp >= 20,
            f"{with_mcp}/{len(ops)} ops have mcp_tool mapping",
        )
    except Exception as exc:
        _check("operations registry", False, str(exc))

    grok = try_grok_mcp_add() if shutil.which("grok") else {"ok": False, "reason": "skipped"}
    report["grok_cli"] = grok
    return report


def _repo_root() -> Path | None:
    here = Path(__file__).resolve()
    for parent in here.parents:
        if (parent / "pyproject.toml").is_file() and (parent / "src" / "agentdrive").is_dir():
            return parent
    return None


def install_mcp_extra(*, python: str | None = None) -> dict[str, Any]:
    """pip install the mcp extra into the active environment."""
    py = python or sys.executable
    root = _repo_root()
    if root is not None:
        cmd = [py, "-m", "pip", "install", "-e", f"{root}[mcp]"]
    else:
        cmd = [py, "-m", "pip", "install", "agentdrive[mcp]"]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=180, check=False)
        return {
            "ok": proc.returncode == 0,
            "command": " ".join(cmd),
            "stdout": (proc.stdout or "")[-500:],
            "stderr": (proc.stderr or "")[-500:],
        }
    except Exception as exc:
        return {"ok": False, "error": str(exc), "command": " ".join(cmd)}


def export_client_bundle(*, prefer_uvx: bool = False) -> dict[str, Any]:
    """Machine-readable bundle for docs, tests, and ``agentdrive mcp config --json``."""
    launcher = resolve_mcp_launcher(prefer_uvx=prefer_uvx)
    return {
        "server_name": MCP_SERVER_NAME,
        "transport": "stdio",
        "launcher": launcher.to_mcp_json() | {"method": launcher.method, "notes": launcher.notes},
        "mcpServers": get_mcp_server_block(prefer_uvx=prefer_uvx),
        "grok_toml": get_grok_toml_snippet(prefer_uvx=prefer_uvx),
        "grok_cli": get_grok_cli_command(prefer_uvx=prefer_uvx),
        "clients": {
            client: [str(p) for p in paths]
            for client, paths in client_config_paths().items()
        },
        "onboarding_doc": "docs/FOR_AI_MODELS.md",
        "connection_doc": "docs/MCP.md",
    }