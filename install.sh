#!/usr/bin/env bash
#
# AgentDrive Installer
#
# One-liner (recommended):
#   curl -fsSL https://vektraindustries.com/agentdrive/install.sh | bash
#
# With options:
#   curl -fsSL https://vektraindustries.com/agentdrive/install.sh | bash -s -- --dev
#
# This installs AgentDrive with full MCP support (agentdrive + agentdrive-mcp binaries).

set -euo pipefail

# Colors
if [[ -t 1 && -z "${NO_COLOR:-}" ]]; then
    CYAN='\033[0;36m'
    GREEN='\033[0;32m'
    YELLOW='\033[0;33m'
    RED='\033[0;31m'
    BOLD='\033[1m'
    NC='\033[0m'
else
    CYAN='' GREEN='' YELLOW='' RED='' BOLD='' NC=''
fi

log() { echo -e "${CYAN}→${NC} $*"; }
success() { echo -e "${GREEN}✓${NC} $*"; }
warn() { echo -e "${YELLOW}⚠${NC} $*"; }
error() { echo -e "${RED}✗${NC} $*"; }

print_banner() {
    echo ""
    echo -e "${BOLD}${CYAN}AgentDrive Installer${NC}"
    echo "The structural Experience Graph + MCP for autonomous agents"
    echo ""
}

# Detect if running interactively
if [ -t 0 ]; then
    INTERACTIVE=true
else
    INTERACTIVE=false
fi

# Parse args
BRANCH="main"
DEV_MODE=false
SKIP_MCP=false

while [[ $# -gt 0 ]]; do
    case $1 in
        --branch) BRANCH="$2"; shift 2 ;;
        --dev) DEV_MODE=true; shift ;;
        --skip-mcp) SKIP_MCP=true; shift ;;
        --help|-h)
            echo "Usage: install.sh [--branch NAME] [--dev] [--skip-mcp]"
            exit 0
            ;;
        *) shift ;;
    esac
done

print_banner

# Requirements
if ! command -v python3 >/dev/null 2>&1; then
    error "python3 is required"
    exit 1
fi

PYTHON_VERSION=$(python3 -c 'import sys; print(".".join(map(str, sys.version_info[:2])))')
log "Python $PYTHON_VERSION detected"

# Home
AGENTDRIVE_HOME="${AGENTDRIVE_HOME:-$HOME/.agentdrive}"
VENV_DIR="$AGENTDRIVE_HOME/venv"
BIN_DIR="$HOME/.local/bin"
mkdir -p "$AGENTDRIVE_HOME" "$BIN_DIR"

# Create venv
if [ -d "$VENV_DIR" ]; then
    log "Removing previous venv..."
    rm -rf "$VENV_DIR"
fi

if command -v uv >/dev/null 2>&1; then
    log "Creating venv with uv..."
    uv venv "$VENV_DIR" --python "$PYTHON_VERSION" >/dev/null 2>&1 || python3 -m venv "$VENV_DIR"
else
    log "Creating venv with python3 -m venv..."
    python3 -m venv "$VENV_DIR"
fi

# Install
REPO="https://github.com/PabloTheThinker/AgentDrive.git"
REF="$BRANCH"

log "Installing AgentDrive (branch: $REF)..."

if [ "$DEV_MODE" = true ]; then
    if [ -d ".git" ]; then
        "$VENV_DIR/bin/pip" install --upgrade pip -q
        "$VENV_DIR/bin/pip" install -e ".[mcp]" -q
        success "Installed in development (editable) mode with MCP support"
    else
        warn "--dev used but not in a git checkout. Falling back to remote install."
    fi
fi

if [ "${SKIP_INSTALL:-false}" != "true" ] && [ "$DEV_MODE" != true ]; then
    "$VENV_DIR/bin/pip" install --upgrade pip -q

    if [ "$SKIP_MCP" = true ]; then
        "$VENV_DIR/bin/pip" install "git+${REPO}@${REF}" -q
    else
        "$VENV_DIR/bin/pip" install "git+${REPO}@${REF}[mcp]" -q
        success "Installed with MCP support (agentdrive + agentdrive-mcp)"
    fi
fi

# Create shims
cat > "$BIN_DIR/agentdrive" << 'SHIM'
#!/usr/bin/env bash
unset PYTHONPATH
unset PYTHONHOME
exec "$HOME/.agentdrive/venv/bin/agentdrive" "$@"
SHIM
chmod +x "$BIN_DIR/agentdrive"

if [ -f "$VENV_DIR/bin/agentdrive-mcp" ]; then
    cat > "$BIN_DIR/agentdrive-mcp" << 'SHIM'
#!/usr/bin/env bash
unset PYTHONPATH
unset PYTHONHOME
exec "$HOME/.agentdrive/venv/bin/agentdrive-mcp" "$@"
SHIM
    chmod +x "$BIN_DIR/agentdrive-mcp"
    success "Created agentdrive-mcp → $BIN_DIR/agentdrive-mcp"
fi

success "Created agentdrive → $BIN_DIR/agentdrive"

# PATH hint
if [[ ":$PATH:" != *":$BIN_DIR:"* ]]; then
    warn "~/.local/bin is not in your PATH"
    echo "  Add this to your shell rc:"
    echo "    export PATH=\"\$HOME/.local/bin:\$PATH\""
fi

# Post-install
echo ""
success "AgentDrive installed successfully!"

if command -v agentdrive >/dev/null 2>&1; then
    if agentdrive mcp doctor >/dev/null 2>&1; then
        success "MCP bridge ready for AI clients"
    else
        warn "MCP not fully wired — run: agentdrive mcp install"
    fi
fi

echo ""
echo "Next steps:"

if command -v agentdrive >/dev/null 2>&1; then
    echo "  agentdrive doctor"
    echo "  agentdrive setup"
else
    echo "  ~/.local/bin/agentdrive doctor"
fi

echo ""
echo "Connect any AI model (Grok, Claude, Cursor, Continue, local models):"
echo "  agentdrive mcp install    # pip [mcp] + write client configs"
echo "  agentdrive mcp doctor     # verify 25+ tools ready"
echo "  agentdrive mcp config       # show resolved launcher + paste snippets"
echo ""
echo "One-liner to re-run this installer anytime:"
echo "  curl -fsSL https://vektraindustries.com/agentdrive/install.sh | bash"
echo ""

# Optional launch
if [ "$INTERACTIVE" = true ] && [ "${RUN_LAUNCH:-true}" = true ]; then
    if prompt_yes_no "Launch AgentDrive now?" "yes"; then
        exec "$BIN_DIR/agentdrive" || "$VENV_DIR/bin/agentdrive"
    fi
fi

