#!/usr/bin/env bash
# AgentDrive golden path — runnable first-run walkthrough.
#
# Usage:
#   bash examples/00_golden_path.sh          # live (writes learnings + may seed)
#   bash examples/00_golden_path.sh --dry-run
#
# See docs/GOLDEN_PATH.md for the full guide.
set -euo pipefail

DRY_RUN=false
for arg in "$@"; do
  case "$arg" in
    --dry-run) DRY_RUN=true ;;
    -h|--help)
      echo "Usage: $0 [--dry-run]"
      echo "Runs: doctor → mcp doctor → seed (if needed) → think → learnings → query"
      exit 0
      ;;
  esac
done

echo "==> AgentDrive golden path"
echo ""

step() { echo ""; echo "── $1 ──"; }

step "1/6  doctor"
agentdrive doctor || true

step "2/6  mcp doctor"
if ! agentdrive mcp doctor >/dev/null 2>&1; then
  echo "MCP not ready — run: agentdrive mcp install"
  exit 1
fi
echo "MCP bridge ok"

step "3/6  seed (if empty)"
if ! agentdrive drive status 2>/dev/null | grep -qi "genome"; then
  if [ "$DRY_RUN" = true ]; then
    agentdrive ops run reconcile_seed --dry-run
  else
    agentdrive reconcile seed-experience-v3 || true
  fi
else
  echo "Drive already has genomes — skipping explicit seed"
fi

step "4/6  think"
if [ "$DRY_RUN" = true ]; then
  agentdrive think "Golden path verification" --dry-run
else
  agentdrive think "What does my AgentDrive contain after first install?" || \
    echo "(think may need a provider — run: agentdrive provider set <name>)"
fi

step "5/6  learnings"
if [ "$DRY_RUN" = true ]; then
  agentdrive learnings log --key golden-path --insight "dry-run" --dry-run 2>/dev/null || \
    agentdrive ops run learnings_log --dry-run key=golden-path insight=dry-run
else
  agentdrive learnings log \
    --key golden-path \
    --insight "Completed examples/00_golden_path.sh walkthrough" \
    --type operational
fi

step "6/6  drive query"
if [ "$DRY_RUN" = true ]; then
  agentdrive ops run pool_query --dry-run task="dedup identical agent outputs" limit=3
else
  agentdrive drive query "dedup identical agent outputs" --limit 3 || true
  echo ""
  echo "Tip: run python3 examples/01_hello_drive.py to ingest the dedup demo genome"
fi

echo ""
echo "Golden path complete. Next: agentdrive golden-path verify"
echo "Docs: docs/GOLDEN_PATH.md"