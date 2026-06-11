#!/usr/bin/env bash
#
# Compatibility wrapper — delegates to the canonical root install.sh
#
# Prefer:
#   curl -fsSL https://vektraindustries.com/agentdrive/install | bash
#
# This path is kept for old links (HELP.md, GitHub raw URLs, bookmarks).
# When piped via curl | bash, BASH_SOURCE is unset — we fetch canonical install.sh.

set -eo pipefail

CANONICAL_URL="${AGENTDRIVE_INSTALL_SCRIPT:-https://raw.githubusercontent.com/PabloTheThinker/AgentDrive/main/install.sh}"

wrapper_path="${BASH_SOURCE[0]:-}"

# Piped install (curl ... | bash) — no BASH_SOURCE; delegate to canonical script URL
if [[ -z "$wrapper_path" || ! -f "$wrapper_path" ]]; then
  if [[ -t 1 && -z "${NO_COLOR:-}" ]]; then
    echo -e "\033[0;33m⚠\033[0m scripts/install.sh piped — fetching canonical installer"
    echo -e "  Prefer: curl -fsSL https://vektraindustries.com/agentdrive/install | bash"
    echo ""
  fi
  exec bash -c 'curl -fsSL "$1" | bash -s -- "${@:2}"' _ "$CANONICAL_URL" "$@"
fi

ROOT="$(cd "$(dirname "$wrapper_path")/.." && pwd)"
CANONICAL="$ROOT/install.sh"

if [[ ! -f "$CANONICAL" ]]; then
  echo "error: canonical installer not found at $CANONICAL" >&2
  exit 1
fi

if [[ -t 1 && -z "${NO_COLOR:-}" ]]; then
  echo -e "\033[0;33m⚠\033[0m scripts/install.sh is a compatibility wrapper."
  echo -e "  Canonical: curl -fsSL https://vektraindustries.com/agentdrive/install | bash"
  echo ""
fi

exec bash "$CANONICAL" "$@"