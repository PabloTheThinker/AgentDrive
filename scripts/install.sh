#!/usr/bin/env bash
#
# AgentDrive Installer — production-grade installer
#
# Usage (recommended):
#   curl -fsSL https://vektraindustries.com/agentdrive/install | bash
#   curl -fsSL https://vektraindustries.com/agentdrive/install.sh | bash
#
# Canonical source:
#   https://raw.githubusercontent.com/PabloTheThinker/AgentDrive/main/scripts/install.sh
#
# This script installs the AgentDrive (local-first agent-memory drive — content-addressed Genomes, CRDT siblings, P-384 trust circle).
# It is safe to re-run at any time.
#
# Scoped for a modern Python package + TUI experience.

set -euo pipefail

# ============================================================================
# Environment hardening
# ============================================================================

# Guard against environment leakage when launched from another Python-driven tool
if [ -n "${PYTHONPATH:-}" ]; then
    echo "⚠ Ignoring inherited PYTHONPATH during install"
    unset PYTHONPATH
fi
if [ -n "${PYTHONHOME:-}" ]; then
    echo "⚠ Ignoring inherited PYTHONHOME during install"
    unset PYTHONHOME
fi

# ============================================================================
# Colors & Logging
# ============================================================================

if [[ -t 1 && -z "${NO_COLOR:-}" ]]; then
    RED='\033[0;31m'
    GREEN='\033[0;32m'
    YELLOW='\033[0;33m'
    BLUE='\033[0;34m'
    MAGENTA='\033[0;35m'
    CYAN='\033[0;36m'
    BOLD='\033[1m'
    NC='\033[0m' # No Color
else
    RED=''
    GREEN=''
    YELLOW=''
    BLUE=''
    MAGENTA=''
    CYAN=''
    BOLD=''
    NC=''
fi

log_info()    { echo -e "${CYAN}→${NC} $*"; }
log_success() { echo -e "${GREEN}✓${NC} $*"; }
log_warn()    { echo -e "${YELLOW}⚠${NC} $*"; }
log_error()   { echo -e "${RED}✗${NC} $*"; }

print_banner() {
    echo ""
    echo -e "${MAGENTA}${BOLD}"
    echo "┌─────────────────────────────────────────────────────────┐"
    echo "│                  AgentDrive Installer                       │"
    echo "├─────────────────────────────────────────────────────────┤"
    echo "│  The Living, Learning Ecosystem for AI Agent Swarms     │"
    echo "│  User-sovereign DNA pools • Professional TUI & CLI      │"
    echo "└─────────────────────────────────────────────────────────┘"
    echo -e "${NC}"
}

# Detect non-interactive mode (curl | bash)
if [ -t 0 ]; then
    IS_INTERACTIVE=true
else
    IS_INTERACTIVE=false
fi

# Robust yes/no prompt that works even when piped (uses /dev/tty when possible)
prompt_yes_no() {
    local question="$1"
    local default="${2:-yes}"
    local prompt_suffix
    local answer=""

    case "$default" in
        [yY]|[yY][eE][sS]|[tT][rR][uU][eE]|1) prompt_suffix="[Y/n]" ;;
        *) prompt_suffix="[y/N]" ;;
    esac

    if [ "$IS_INTERACTIVE" = true ]; then
        read -r -p "$question $prompt_suffix " answer || answer=""
    elif { : </dev/tty; } 2>/dev/null && { : >/dev/tty; } 2>/dev/null; then
        printf "%s %s " "$question" "$prompt_suffix" >/dev/tty 2>/dev/null || true
        IFS= read -r answer </dev/tty 2>/dev/null || answer=""
    else
        answer=""
    fi

    answer="${answer#"${answer%%[![:space:]]*}"}"
    answer="${answer%"${answer##*[![:space:]]*}"}"

    if [ -z "$answer" ]; then
        case "$default" in
            [yY]|[yY][eE][sS]|[tT][rR][uU][eE]|1) return 0 ;;
            *) return 1 ;;
        esac
    fi

    case "$answer" in
        [yY]|[yY][eE][sS]) return 0 ;;
        *) return 1 ;;
    esac
}

# ============================================================================
# ============================================================================
# Gum Integration (optional spinner support)
# ============================================================================
# We optionally bootstrap "gum" (Charmbracelet) for beautiful spinners and
# confirms during long operations. Falls back gracefully if unavailable.

GUM_VERSION="0.17.0"
GUM=""
GUM_STATUS="skipped"
GUM_REASON=""

gum_is_tty() {
    if [[ -n "${NO_COLOR:-}" ]]; then return 1; fi
    if [[ "${TERM:-dumb}" == "dumb" ]]; then return 1; fi
    if [[ -t 1 || -t 2 ]]; then return 0; fi
    if { : </dev/tty; } 2>/dev/null; then return 0; fi
    return 1
}

gum_detect_os() {
    case "$(uname -s 2>/dev/null || true)" in
        Darwin) echo "Darwin" ;;
        Linux) echo "Linux" ;;
        *) echo "unsupported" ;;
    esac
}

gum_detect_arch() {
    case "$(uname -m 2>/dev/null || true)" in
        x86_64|amd64) echo "x86_64" ;;
        arm64|aarch64) echo "arm64" ;;
        *) echo "unknown" ;;
    esac
}

bootstrap_gum() {
    if ! gum_is_tty; then
        GUM_REASON="no suitable TTY"
        return 1
    fi

    if command -v gum >/dev/null 2>&1; then
        GUM="gum"
        GUM_STATUS="found"
        return 0
    fi

    local os arch asset url checksum_url gum_dir
    os="$(gum_detect_os)"
    arch="$(gum_detect_arch)"

    if [[ "$os" == "unsupported" || "$arch" == "unknown" ]]; then
        GUM_REASON="unsupported platform"
        return 1
    fi

    asset="gum_${GUM_VERSION}_${os}_${arch}.tar.gz"
    url="https://github.com/charmbracelet/gum/releases/download/v${GUM_VERSION}/${asset}"
    checksum_url="https://github.com/charmbracelet/gum/releases/download/v${GUM_VERSION}/checksums.txt"

    gum_dir="$(mktemp -d)"
    TMPFILES+=("$gum_dir")

    # Strict HTTPS + retries
    if ! curl -fsSL --proto '=https' --tlsv1.2 --retry 3 --retry-delay 1 \
         -o "$gum_dir/$asset" "$url" 2>/dev/null; then
        GUM_REASON="secure download failed"
        return 1
    fi

    # Download checksums
    if ! curl -fsSL --proto '=https' --tlsv1.2 --retry 2 \
         -o "$gum_dir/checksums.txt" "$checksum_url" 2>/dev/null; then
        GUM_REASON="failed to fetch checksums"
        return 1
    fi

    # Mandatory checksum verification
    if command -v sha256sum >/dev/null 2>&1; then
        if ! (cd "$gum_dir" && sha256sum --ignore-missing -c checksums.txt >/dev/null 2>&1); then
            GUM_REASON="checksum verification failed"
            return 1
        fi
    elif command -v shasum >/dev/null 2>&1; then
        if ! (cd "$gum_dir" && shasum -a 256 --ignore-missing -c checksums.txt >/dev/null 2>&1); then
            GUM_REASON="checksum verification failed"
            return 1
        fi
    else
        GUM_REASON="no sha256sum/shasum available for verification"
        return 1
    fi

    tar -xzf "$gum_dir/$asset" -C "$gum_dir" --strip-components=1 2>/dev/null || {
        GUM_REASON="extract failed"
        return 1
    }

    if [[ -x "$gum_dir/gum" ]]; then
        GUM="$gum_dir/gum"
        GUM_STATUS="bootstrapped"
        chmod +x "$GUM"
        return 0
    fi

    GUM_REASON="binary not found after extract"
    return 1
}

# Call early so we can use gum for spinners later
bootstrap_gum || true

# ============================================================================
# Argument Parsing
# ============================================================================

BRANCH="main"
USE_UV=true
RUN_LAUNCH=true
DEV_MODE=false
CUSTOM_PYTHON=""

show_help() {
    echo "AgentDrive Installer"
    echo ""
    echo "Usage: install.sh [OPTIONS]"
    echo ""
    echo "Options:"
    echo "  --help              Show this help message"
    echo "  --no-color          Disable colored output"
    echo "  --branch NAME       Install from a specific branch (default: main)"
    echo "  --no-uv             Do not use uv even if available (use pip)"
    echo "  --python VERSION    Use a specific Python version (e.g. 3.12)"
    echo "  --dev               Install in editable mode (for contributors)"
    echo "  --skip-launch       Do not offer to launch AgentDrive after install"
    echo ""
    echo "Examples:"
    echo "  curl -fsSL ... | bash -s -- --branch develop"
    echo "  curl -fsSL ... | bash -s -- --dev"
    echo ""
    exit 0
}

# Parse arguments (support both direct execution and curl | bash -s --)
while [[ $# -gt 0 ]]; do
    case $1 in
        --help|-h)
            show_help
            ;;
        --no-color)
            RED='' GREEN='' YELLOW='' BLUE='' MAGENTA='' CYAN='' BOLD='' NC=''
            shift
            ;;
        --branch)
            BRANCH="$2"
            shift 2
            ;;
        --no-uv)
            USE_UV=false
            shift
            ;;
        --python)
            CUSTOM_PYTHON="$2"
            shift 2
            ;;
        --dev)
            DEV_MODE=true
            shift
            ;;
        --skip-launch)
            RUN_LAUNCH=false
            shift
            ;;
        *)
            log_warn "Unknown option: $1 (ignoring)"
            shift
            ;;
    esac
done

# ============================================================================
# Configuration
# ============================================================================

SAVANT_REPO="https://github.com/PabloTheThinker/AgentDrive.git"  # Correct casing is important for GitHub raw / git+ URLs
MIN_PYTHON="3.11"
AGENTDRIVE_HOME="${AGENTDRIVE_HOME:-$HOME/.agentdrive}"

if [ -n "$CUSTOM_PYTHON" ]; then
    MIN_PYTHON="$CUSTOM_PYTHON"
fi

if [ "$DEV_MODE" = true ]; then
    log_info "Development mode enabled"
fi

# ============================================================================
# Main Installation Flow
# ============================================================================

print_banner

# ============================================================================
# Pre-flight Doctor
# ============================================================================
# Run very early so users get clear, actionable feedback before anything else.

run_preflight_checks() {
    local failed=false
    PYTHON_VERSION=""

    log_info "Running pre-flight checks..."

    # Python 3
    if command -v python3 >/dev/null 2>&1; then
        PYTHON_VERSION=$(python3 -c 'import sys; print(".".join(map(str, sys.version_info[:2])))' 2>/dev/null || echo "unknown")
        if python3 -c "
import sys
min_ver = tuple(map(int, '${MIN_PYTHON}'.split('.')))
if sys.version_info[:2] >= min_ver:
    sys.exit(0)
else:
    sys.exit(1)
" 2>/dev/null; then
            log_success "python3 ${PYTHON_VERSION} (≥ ${MIN_PYTHON} required)"
        else
            log_error "python3 ${PYTHON_VERSION} (need ≥ ${MIN_PYTHON})"
            failed=true
        fi
    else
        log_error "python3 (not found)"
        failed=true
    fi

    # pip
    if python3 -m pip --version >/dev/null 2>&1; then
        log_success "pip"
    else
        log_error "pip (not available for this python3)"
        failed=true
    fi

    # git (required for source installs)
    if command -v git >/dev/null 2>&1; then
        log_success "git"
    else
        log_error "git (required for installing from GitHub)"
        log_info "Install git first:"
        log_info "  Ubuntu/Debian: sudo apt update && sudo apt install git"
        log_info "  macOS:         brew install git"
        log_info "  Fedora:        sudo dnf install git"
        log_info "  Arch:          sudo pacman -S git"
        log_info "  Termux:        pkg install git"
        failed=true
    fi

    # Downloader (at least one of curl or wget)
    if command -v curl >/dev/null 2>&1; then
        log_success "curl"
    elif command -v wget >/dev/null 2>&1; then
        log_success "wget"
    else
        log_warn "curl or wget (recommended for downloads)"
    fi

    # Warn if no `python` command (only python3) — very common on minimal Ubuntu
    if ! command -v python >/dev/null 2>&1 && command -v python3 >/dev/null 2>&1; then
        log_warn "'python' command not found (only python3 exists). This is normal on many systems."
        log_info "The installer uses 'python3' everywhere, so this is fine."
    fi

    if [ "$failed" = true ]; then
        echo ""
        log_error "Pre-flight checks failed. Please fix the issues above and re-run."
        exit 1
    fi

    log_success "Pre-flight checks passed"
}

# Make PYTHON_VERSION available to the rest of the script
PYTHON_VERSION=""
run_preflight_checks
# Re-run the version capture in case the function set it locally
if command -v python3 >/dev/null 2>&1; then
    PYTHON_VERSION=$(python3 -c 'import sys; print(".".join(map(str, sys.version_info[:2])))' 2>/dev/null || echo "unknown")
fi

log_info "Starting AgentDrive installation..."

# 3. Install AgentDrive (venv + bash shim — avoids PEP 668)
REF="main"
if [ "$BRANCH" != "main" ]; then
    REF="$BRANCH"
fi

log_info "Installing AgentDrive (branch: ${REF})..."

# Paths
VENV_DIR="$AGENTDRIVE_HOME/venv"
SHIM_DIR="$HOME/.local/bin"
SHIM_PATH="$SHIM_DIR/agentdrive"

# Create agentdrive home
mkdir -p "$AGENTDRIVE_HOME"

if [ "$DEV_MODE" = true ]; then
    log_info "Development mode: installing from local checkout"
    if [ ! -d ".git" ]; then
        log_warn "--dev was passed but not inside an AgentDrive checkout. Falling back to remote install."
    else
        # Create venv, install editable from local source
        if [ -d "$VENV_DIR" ]; then rm -rf "$VENV_DIR"; fi
        if command -v uv >/dev/null 2>&1; then
            uv venv "$VENV_DIR" --python "$PYTHON_VERSION" 2>/dev/null || python3 -m venv "$VENV_DIR"
        else
            python3 -m venv "$VENV_DIR"
        fi
        "$VENV_DIR/bin/pip" install --upgrade pip
        "$VENV_DIR/bin/pip" install -e .
        mkdir -p "$SHIM_DIR"
        cat > "$SHIM_PATH" <<SHIMEOF
#!/usr/bin/env bash
unset PYTHONPATH
unset PYTHONHOME
exec "$VENV_DIR/bin/agentdrive" "\$@"
SHIMEOF
        chmod +x "$SHIM_PATH"
        log_success "AgentDrive installed in dev mode → $SHIM_PATH"
        SAVANT_BIN="$VENV_DIR/bin/agentdrive"
        # Skip normal install below
        SKIP_INSTALL=true
    fi
fi

# Step 1: Create a fresh virtual environment (isolated from system Python, no PEP 668)
if [ "${SKIP_INSTALL:-false}" = false ]; then
if [ -d "$VENV_DIR" ]; then
    log_info "Removing previous virtual environment..."
    rm -rf "$VENV_DIR"
fi

if command -v uv >/dev/null 2>&1; then
    log_info "Creating virtual environment with uv..."
    uv venv "$VENV_DIR" --python "$PYTHON_VERSION" 2>/dev/null || python3 -m venv "$VENV_DIR"

    log_info "Installing AgentDrive with uv..."
    if VIRTUAL_ENV="$VENV_DIR" uv pip install --force-reinstall "git+${SAVANT_REPO}@${REF}"; then
        log_success "AgentDrive installed with uv"
    else
        log_error "Installation failed."
        exit 1
    fi
else
    log_info "Creating virtual environment with python3 -m venv..."
    python3 -m venv "$VENV_DIR"

    log_info "Installing AgentDrive with pip..."
    if "$VENV_DIR/bin/pip" install --upgrade --force-reinstall "git+${SAVANT_REPO}@${REF}"; then
        log_success "AgentDrive installed into virtual environment"
    else
        log_error "Installation failed."
        exit 1
    fi
fi

# Step 3: Create a bash shim that execs the venv binary
mkdir -p "$SHIM_DIR"
cat > "$SHIM_PATH" <<SHIMEOF
#!/usr/bin/env bash
unset PYTHONPATH
unset PYTHONHOME
exec "$VENV_DIR/bin/agentdrive" "\$@"
SHIMEOF
chmod +x "$SHIM_PATH"
log_success "Created agentdrive launcher → $SHIM_PATH"
SAVANT_BIN="$VENV_DIR/bin/agentdrive"
fi

# 5. PATH setup — ensure ~/.local/bin is on PATH
USER_BIN_DIR="$HOME/.local/bin"
if [[ ":$PATH:" != *":$USER_BIN_DIR:"* ]]; then
    log_info "Adding $USER_BIN_DIR to your PATH..."

    SHELL_NAME="$(basename "${SHELL:-/bin/bash}")"
    RC_FILES=()

    case "$SHELL_NAME" in
        zsh)
            RC_FILES+=("$HOME/.zshrc" "$HOME/.zprofile")
            ;;
        bash)
            RC_FILES+=("$HOME/.bashrc" "$HOME/.bash_profile" "$HOME/.profile")
            ;;
        fish)
            RC_FILES+=("$HOME/.config/fish/config.fish")
            ;;
        *)
            RC_FILES+=("$HOME/.bashrc" "$HOME/.profile")
            ;;
    esac

    for rc in "${RC_FILES[@]}"; do
        if [[ -f "$rc" ]]; then
            if ! grep -q "$USER_BIN_DIR" "$rc" 2>/dev/null; then
                echo "" >> "$rc"
                echo "# AgentDrive — ensure agentdrive CLI is on PATH" >> "$rc"
                if [[ "$SHELL_NAME" == "fish" ]]; then
                    echo "fish_add_path $USER_BIN_DIR" >> "$rc"
                else
                    echo "export PATH=\"$USER_BIN_DIR:\$PATH\"" >> "$rc"
                fi
                log_success "Updated $rc"
            fi
        fi
    done

    export PATH="$USER_BIN_DIR:$PATH"
fi

# 6. Ensure AgentDrive home directory exists
mkdir -p "$AGENTDRIVE_HOME"/{genomes,logs,cache,pool,swarms,reasoning}

# 7. Final success messaging
log_success "AgentDrive is now installed."

echo
echo -e "${BOLD}Next steps:${NC}"
echo "  agentdrive          Launch the AgentDrive TUI"
echo "  agentdrive setup        Run the setup wizard"
echo "  agentdrive drive status View your Drives"
echo "  agentdrive update       Update to the latest version"
echo
echo -e "${BOLD}Documentation:${NC} https://github.com/PabloTheThinker/AgentDrive"
echo

# 8. Offer to launch immediately (skip if --skip-launch was passed)
if [ "$RUN_LAUNCH" = false ]; then
    echo
    log_info "Skipping launch (--skip-launch). Run ${BOLD}agentdrive${NC} to start."
    exit 0
fi

launch_now=false
if [[ -n "$GUM" ]]; then
    if "$GUM" confirm "Launch AgentDrive TUI now?" --default=true --affirmative="Yes, launch it" --negative="Later"; then
        launch_now=true
    fi
else
    if prompt_yes_no "Launch AgentDrive now?" "yes"; then
        launch_now=true
    fi
fi

if [ "$launch_now" = true ]; then
    if [[ -n "$SAVANT_BIN" && -x "$SAVANT_BIN" ]]; then
        exec "$SAVANT_BIN"
    elif command -v agentdrive >/dev/null 2>&1; then
        exec agentdrive
    else
        log_info "Please restart your terminal and run: agentdrive"
    fi
else
    echo
    log_info "You can start AgentDrive anytime by running: ${BOLD}agentdrive${NC}"
fi

exit 0
