#!/usr/bin/env bash
#
# Agent Drive Release Helper
# Professional, safe release workflow
#
# Usage:
#   ./scripts/release.sh
#   ./scripts/release.sh patch
#   ./scripts/release.sh minor --push
#
# This script will:
#   1. Verify clean working tree + on main
#   2. Bump version (major/minor/patch)
#   3. Generate/update CHANGELOG.md using git-cliff
#   4. Show diff and ask for confirmation
#   5. Commit + create annotated tag
#   6. (Optional) push tag

set -euo pipefail

# Colors
if [[ -t 1 ]]; then
    BOLD='\033[1m'
    GREEN='\033[0;32m'
    CYAN='\033[0;36m'
    YELLOW='\033[0;33m'
    RED='\033[0;31m'
    NC='\033[0m'
else
    BOLD='' GREEN='' CYAN='' YELLOW='' RED='' NC=''
fi

log()   { echo -e "${CYAN}→${NC} $*"; }
success() { echo -e "${GREEN}✓${NC} $*"; }
warn()  { echo -e "${YELLOW}!${NC} $*"; }
error() { echo -e "${RED}✗${NC} $*"; }

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

# --- Safety checks -----------------------------------------------------------

if ! git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
    error "Not inside a git repository"
    exit 1
fi

CURRENT_BRANCH="$(git rev-parse --abbrev-ref HEAD)"
if [[ "$CURRENT_BRANCH" != "main" && "$CURRENT_BRANCH" != "master" ]]; then
    warn "You are on branch '$CURRENT_BRANCH' (expected main/master)"
    read -r -p "Continue anyway? [y/N] " ans
    if [[ ! "$ans" =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

if [[ -n "$(git status --porcelain)" ]]; then
    error "Working tree is not clean. Please commit or stash changes first."
    git status --short
    exit 1
fi

# --- Get bump type -----------------------------------------------------------

BUMP_TYPE="${1:-}"
PUSH_TAG=false

if [[ "$2" == "--push" || "$BUMP_TYPE" == "--push" ]]; then
    PUSH_TAG=true
    if [[ "$BUMP_TYPE" == "--push" ]]; then BUMP_TYPE=""; fi
fi

if [[ -z "$BUMP_TYPE" ]]; then
    echo ""
    echo "Choose release type:"
    echo "  1) patch   (0.1.0 → 0.1.1)   [bug fixes, small improvements]"
    echo "  2) minor   (0.1.0 → 0.2.0)   [new features, non-breaking]"
    echo "  3) major   (0.1.0 → 1.0.0)   [breaking changes]"
    echo ""
    read -r -p "Select [1/2/3] or type patch/minor/major: " choice

    case "$choice" in
        1|patch) BUMP_TYPE="patch" ;;
        2|minor) BUMP_TYPE="minor" ;;
        3|major) BUMP_TYPE="major" ;;
        *) echo "Invalid choice"; exit 1 ;;
    esac
fi

# --- Run bump + changelog ----------------------------------------------------

log "Bumping $BUMP_TYPE version..."
NEW_VERSION=$(python3 scripts/bump_version.py "$BUMP_TYPE" --print-only)

if [[ -z "$NEW_VERSION" ]]; then
    error "Failed to determine new version"
    exit 1
fi

log "New version will be: v${NEW_VERSION}"

log "Generating changelog for v${NEW_VERSION}..."
bash scripts/generate_changelog.sh "v${NEW_VERSION}"

echo ""
echo "=== Proposed changes ==="
git diff --stat
echo ""
git diff pyproject.toml | head -20
echo ""

read -r -p "Proceed with release v${NEW_VERSION}? [y/N] " confirm
if [[ ! "$confirm" =~ ^[Yy]$ ]]; then
    warn "Aborted by user"
    exit 1
fi

# --- Commit + Tag ------------------------------------------------------------

git add pyproject.toml CHANGELOG.md

COMMIT_MSG="chore(release): v${NEW_VERSION}"
git commit -m "$COMMIT_MSG"

TAG_NAME="v${NEW_VERSION}"
git tag -a "$TAG_NAME" -m "Release ${TAG_NAME}"

success "Created commit and tag ${TAG_NAME}"

# --- Optional push -----------------------------------------------------------

if [[ "$PUSH_TAG" == true ]]; then
    log "Pushing commit and tag..."
    git push origin "$(git rev-parse --abbrev-ref HEAD)" --tags
    success "Pushed ${TAG_NAME}"
else
    echo ""
    echo "Next steps:"
    echo "  git push origin $(git rev-parse --abbrev-ref HEAD) --tags"
    echo ""
    echo "After pushing, you can publish to PyPI with:"
    echo "  python -m build"
    echo "  python -m twine upload dist/*"
fi

success "Release v${NEW_VERSION} prepared successfully."