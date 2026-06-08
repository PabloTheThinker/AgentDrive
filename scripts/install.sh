#!/usr/bin/env bash
#
# Compatibility wrapper — delegates to the canonical root install.sh
#
# Prefer the short URL:
#   curl -fsSL https://vektraindustries.com/agentdrive/install.sh | bash
#
# This path is kept for old links (HELP.md, GitHub raw URLs, bookmarks).

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CANONICAL="$ROOT/install.sh"

if [[ ! -f "$CANONICAL" ]]; then
    echo "error: canonical installer not found at $CANONICAL" >&2
    exit 1
fi

if [[ -t 1 && -z "${NO_COLOR:-}" ]]; then
    echo -e "\033[0;33m⚠\033[0m scripts/install.sh is a compatibility wrapper."
    echo -e "  Canonical: curl -fsSL https://vektraindustries.com/agentdrive/install.sh | bash"
    echo ""
fi

exec bash "$CANONICAL" "$@"