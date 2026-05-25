#!/usr/bin/env bash
# AgentDrive one-command developer bring-up.
#
# Boots a reproducible local environment so a contributor can poke at the
# engine without touching their real ~/.agentdrive/ data. See DEVELOPERS.md
# for the full description.
#
# Layout:
#   ~/.agentdrive-dev/          primary daemon home (port 8421)
#   ~/.agentdrive-dev-peer/     simulated remote peer home (port 8422)
#
# Press Ctrl-C to stop both daemons; state persists for inspection. Re-run
# this script to reset.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

PRIMARY_HOME="${AGENTDRIVE_DEV_HOME:-$HOME/.agentdrive-dev}"
PEER_HOME="${AGENTDRIVE_DEV_PEER_HOME:-$HOME/.agentdrive-dev-peer}"
PRIMARY_PORT="${AGENTDRIVE_DEV_PORT:-8421}"
PEER_PORT="${AGENTDRIVE_DEV_PEER_PORT:-8422}"

log() { printf '\033[1;36m[dev]\033[0m %s\n' "$*"; }

# Fresh reset.
log "Resetting $PRIMARY_HOME and $PEER_HOME ..."
rm -rf "$PRIMARY_HOME" "$PEER_HOME"
mkdir -p "$PRIMARY_HOME" "$PEER_HOME"

# Sanity: editable install present.
if ! python -c "import agentdrive" 2>/dev/null; then
    log "agentdrive package not importable — run 'make install' first."
    exit 1
fi

PIDS=()
cleanup() {
    log "Shutting down ..."
    for pid in "${PIDS[@]:-}"; do
        kill "$pid" 2>/dev/null || true
    done
    wait 2>/dev/null || true
}
trap cleanup EXIT INT TERM

# 1. Primary daemon.
log "Starting primary daemon on :$PRIMARY_PORT (home=$PRIMARY_HOME)"
AGENTDRIVE_HOME="$PRIMARY_HOME" \
    agentdrive web --host 127.0.0.1 --port "$PRIMARY_PORT" \
    >"$PRIMARY_HOME/daemon.log" 2>&1 &
PIDS+=($!)

# 2. Peer daemon.
log "Starting peer daemon on :$PEER_PORT (home=$PEER_HOME)"
AGENTDRIVE_HOME="$PEER_HOME" \
    python -m agentdrive.web --host 127.0.0.1 --port "$PEER_PORT" \
    >"$PEER_HOME/daemon.log" 2>&1 &
PIDS+=($!)

# Give the daemons a moment to bind.
sleep 2

# 3. Swarm example against the primary daemon's home.
log "Running examples/03_swarm.py against primary home ..."
AGENTDRIVE_HOME="$PRIMARY_HOME" python examples/03_swarm.py || \
    log "Swarm example failed — daemons still running for inspection."

cat <<EOF

  Primary daemon : http://127.0.0.1:$PRIMARY_PORT   (home: $PRIMARY_HOME)
  Peer daemon    : http://127.0.0.1:$PEER_PORT   (home: $PEER_HOME)

  To wire them as peers, mint a cap on each side and add the other to
  peers.yaml. See docs/POOL-EVOLUTION.md for the federation handshake.

  Tailing both audit logs. Ctrl-C to stop.

EOF

tail -F "$PRIMARY_HOME/audit.log" "$PEER_HOME/audit.log" 2>/dev/null || \
    log "Audit logs not yet written — daemons running, send a request to populate."

# Wait for daemons to exit (Ctrl-C triggers cleanup via trap).
wait
