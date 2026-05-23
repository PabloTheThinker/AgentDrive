#!/usr/bin/env bash
#
# Savant Installer — Apple-grade, Hermes-style production installer
#
# Usage (recommended):
#   curl -fsSL https://vektraindustries.com/savant/install | bash
#   curl -fsSL https://vektraindustries.com/savant/install.sh | bash
#
# Canonical source (like Hermes):
#   https://raw.githubusercontent.com/PabloTheThinker/savant/main/scripts/install.sh
#
# This script installs the Savant Framework (The Living DNA Pool for AI Agent Swarms).
# It is safe to re-run at any time.
#
# Inspired by the Hermes Agent installer (https://hermes-agent.nousresearch.com)
# but appropriately scoped for a modern Python package + TUI experience.

set -euo pipefail

# ============================================================================
# Environment hardening (Hermes pattern)
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
# Colors & Logging (Hermes-style, Apple-grade polish)
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
    echo "│                  Savant Installer                       │"
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
    elif [ -r /dev/tty ] && [ -w /dev/tty ]; then
        printf "%s %s " "$question" "$prompt_suffix" > /dev/tty
        IFS= read -r answer < /dev/tty || answer=""
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
# Gum Integration (OpenClaw + Hermes level delight)
# ============================================================================
# We optionally bootstrap "gum" (Charmbracelet) for beautiful spinners and
# confirms during long operations. Falls back gracefully like OpenClaw does.

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

    # Mandatory checksum verification (OpenClaw-style)
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
bootstrap_gum

# ============================================================================
# Argument Parsing (Hermes-grade)
# ============================================================================

BRANCH="main"
USE_UV=true
RUN_LAUNCH=true
DEV_MODE=false
CUSTOM_PYTHON=""

show_help() {
    echo "Savant Installer"
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
    echo "  --skip-launch       Do not offer to launch Savant after install"
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

SAVANT_REPO="https://github.com/PabloTheThinker/savant.git"  # Correct casing is important for GitHub raw / git+ URLs
MIN_PYTHON="3.11"
SAVANT_HOME="${SAVANT_HOME:-$HOME/.savant}"

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

log_info "Starting Savant installation..."

# 1. Python check
log_info "Checking for Python ${MIN_PYTHON}+..."

if ! command -v python3 >/dev/null 2>&1; then
    log_error "python3 was not found in your PATH."
    log_info "Please install Python ${MIN_PYTHON} or newer and re-run this installer."
    exit 1
fi

PYTHON_VERSION=$(python3 -c 'import sys; print(".".join(map(str, sys.version_info[:2])))' 2>/dev/null || echo "0.0")

python3 -c "
import sys
min_ver = tuple(map(int, '${MIN_PYTHON}'.split('.')))
if sys.version_info[:2] < min_ver:
    print('Python ${MIN_PYTHON}+ is required (detected Python ${PYTHON_VERSION}).')
    sys.exit(1)
" 2>/dev/null || {
    log_error "Python ${MIN_PYTHON}+ is required. You currently have Python ${PYTHON_VERSION}."
    exit 1
}

log_success "Python ${PYTHON_VERSION} detected"

# 2. pip check
if ! python3 -m pip --version >/dev/null 2>&1; then
    log_error "pip is not available for this Python installation."
    log_info "Try: python3 -m ensurepip --upgrade"
    exit 1
fi

# 3. Install Savant (support uv + branch + dev mode)
REF="main"
if [ "$BRANCH" != "main" ]; then
    REF="$BRANCH"
fi

INSTALL_SPEC="git+${SAVANT_REPO}@${REF}"

if [ "$DEV_MODE" = true ]; then
    log_info "Development install mode"
    if [ -d ".git" ]; then
        INSTALL_SPEC="-e ."
    else
        log_warn "--dev was passed but you're not inside a Savant checkout. Falling back to remote install."
    fi
fi

log_info "Installing Savant from ${REF}..."

install_with_pip() {
    local spec="$1"
    local tmp_log
    tmp_log=$(mktemp)

    if python3 -m pip install --user --upgrade "$spec" >"$tmp_log" 2>&1; then
        rm -f "$tmp_log"
        return 0
    else
        log_error "pip install failed with the following output:"
        echo ""
        cat "$tmp_log" | sed 's/^/    /'
        echo ""
        rm -f "$tmp_log"
        return 1
    fi
}

install_with_uv() {
    local spec="$1"
    if uv pip install --user --upgrade "$spec" 2>/dev/null || uv pip install "$spec" 2>/dev/null; then
        return 0
    fi
    return 1
}

run_install_step() {
    local title="$1"
    shift

    if [[ -n "$GUM" ]]; then
        "$GUM" spin --spinner dot --title "$title" -- bash -c "$*"
    else
        log_info "$title"
        bash -c "$*"
    fi
}

success=false

if [ "$USE_UV" = true ] && command -v uv &> /dev/null; then
    if run_install_step "Installing with uv (this can take a minute)..." "install_with_uv '$INSTALL_SPEC'"; then
        log_success "Savant installed with uv"
        success=true
    else
        log_warn "uv path failed, trying pip with real error output..."
    fi
fi

if [ "$success" = false ]; then
    if run_install_step "Installing Savant with pip (this can take a minute)..." "install_with_pip '$INSTALL_SPEC'"; then
        log_success "Savant installed successfully"
        success=true
    fi
fi

if [ "$success" = false ]; then
    log_error "Installation failed."
    log_info "Common causes:"
    log_info "  • git is not installed"
    log_info "  • No internet / corporate proxy blocking git+https"
    log_info "  • Python version or permissions issue"
    echo ""
    log_info "Manual command to try:"
    log_info "  python3 -m pip install --user git+${SAVANT_REPO}@${REF}"
    echo ""
    log_info "If you have git installed, you can also do:"
    log_info "  git clone --branch ${REF} ${SAVANT_REPO} && cd savant && python -m pip install -e ."
    exit 1
fi

# 4. Locate the savant binary
SAVANT_BIN=""
for candidate in \
    "$HOME/.local/bin/savant" \
    "$HOME/Library/Python/${PYTHON_VERSION}/bin/savant" \
    "$(python3 -m site --user-base 2>/dev/null)/bin/savant"; do
    if [[ -n "$candidate" && -x "$candidate" ]]; then
        SAVANT_BIN="$candidate"
        break
    fi
done

if [[ -z "$SAVANT_BIN" ]]; then
    if command -v savant >/dev/null 2>&1; then
        SAVANT_BIN="$(command -v savant)"
    fi
fi

# 5. PATH setup (Hermes-grade shell awareness)
USER_BIN_DIR="$(dirname "${SAVANT_BIN:-$HOME/.local/bin/savant}")"

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
                echo "# Savant — ensure Savant CLI is on PATH" >> "$rc"
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

# 6. Ensure Savant home directory exists
mkdir -p "$SAVANT_HOME"/{genomes,logs,cache,pool,swarms,reasoning}

# 7. Final success messaging
log_success "Savant is now installed."

echo
echo -e "${BOLD}Next steps:${NC}"
echo "  Run the professional TUI:    ${CYAN}savant${NC}"
echo "  Run the setup wizard:        ${CYAN}savant setup${NC}"
echo "  View your DNA pools:         ${CYAN}savant pool status${NC}"
echo
echo "Documentation: https://github.com/pablothethinker/savant"
echo

# 8. Offer to launch immediately (Hermes-style delight)
launch_now=false
if [[ -n "$GUM" ]]; then
    if "$GUM" confirm "Launch Savant TUI now?" --default=true --affirmative="Yes, launch it" --negative="Later"; then
        launch_now=true
    fi
else
    if prompt_yes_no "Launch Savant now?" "yes"; then
        launch_now=true
    fi
fi

if [ "$launch_now" = true ]; then
    if [[ -n "$SAVANT_BIN" && -x "$SAVANT_BIN" ]]; then
        exec "$SAVANT_BIN"
    elif command -v savant >/dev/null 2>&1; then
        exec savant
    else
        log_info "Please restart your terminal and run: savant"
    fi
else
    echo
    log_info "You can start Savant anytime by running: ${BOLD}savant${NC}"
fi

exit 0
