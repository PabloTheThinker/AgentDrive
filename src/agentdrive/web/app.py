"""
Legacy localhost web UI has been removed.

The old Jinja2-templated web page (served at http://127.0.0.1:8421 by default)
has been wiped as part of starting over with a new and better interface.

Core backend functionality (Drive, Grid, Evolution, chat client, etc.) remains
intact. The previous web/ presentation layer (templates + routes + static assets)
has been removed; only this minimal stub ``create_app`` survives so importers and
health probes keep working. A new UI will be built from scratch in a future
iteration.
"""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI

from agentdrive import AGENTDRIVE_VERSION


def create_app(auth_db: Path | None = None) -> FastAPI:
    """Minimal stub app after the legacy web UI removal.

    Exposes only ``/`` (an explanatory message) and ``/health`` so existing
    health checks and ``create_app`` importers continue to function until the
    new UI lands.
    """
    app = FastAPI(
        title="AgentDrive (Legacy Web UI Removed)",
        version=AGENTDRIVE_VERSION,
    )

    @app.get("/")
    async def root() -> dict[str, object]:
        return {
            "message": "Legacy web UI has been removed.",
            "status": "new UI in development",
            "core_functionality": "fully available via Python API, TUI, and CLI",
            "golden_path": {
                "doc": "docs/GOLDEN_PATH.md",
                "cli_steps": "agentdrive golden-path steps",
                "cli_run": "agentdrive golden-path run",
                "cli_verify": "agentdrive golden-path verify",
                "install": "curl -fsSL https://vektraindustries.com/agentdrive/install.sh | bash",
                "mcp": "agentdrive mcp install && agentdrive mcp doctor",
            },
        }

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok", "ui": "removed"}

    return app
