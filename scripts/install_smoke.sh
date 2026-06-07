#!/usr/bin/env bash
# Post-install smoke: fresh venv, wheel install, doctor + dream dry-run + hello example.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

python3 -m venv "$TMP/venv"
# shellcheck disable=SC1091
source "$TMP/venv/bin/activate"
python -m pip install --upgrade pip build wheel

if [[ -d "$ROOT/dist" ]] && compgen -G "$ROOT/dist/agentdrive-*.whl" > /dev/null; then
  WHEEL=( "$ROOT"/dist/agentdrive-*.whl )
  python -m pip install "${WHEEL[0]}[mcp]"
else
  python -m pip install -e "$ROOT[mcp,test]"
fi

agentdrive --version
agentdrive doctor
agentdrive dream run --dry-run
python "$ROOT/examples/01_hello_drive.py"

echo "INSTALL_SMOKE_PASS"