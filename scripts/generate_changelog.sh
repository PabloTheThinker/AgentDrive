#!/usr/bin/env bash
# Professional changelog generator for Agent Drive (uses git-cliff when available).
#
# Usage:
#   ./scripts/generate_changelog.sh                    # regenerate full changelog
#   ./scripts/generate_changelog.sh v0.2.0             # prepare for specific version
#   TAG=v0.2.0 ./scripts/generate_changelog.sh

set -euo pipefail

VERSION="${1:-${TAG:-}}"
CHANGELOG_FILE="CHANGELOG.md"

if ! command -v git-cliff >/dev/null 2>&1; then
    echo "Error: git-cliff is required for high-quality changelogs."
    echo "Install it: https://git-cliff.org/ (or cargo install git-cliff)"
    echo ""
    echo "Alternative: use 'git cliff' manually after installing."
    exit 1
fi

echo "→ Generating CHANGELOG.md ..."

if [ -n "$VERSION" ]; then
    # Prepare changelog for a specific upcoming release
    git cliff --tag "$VERSION" --output "$CHANGELOG_FILE"
    echo "✓ Generated $CHANGELOG_FILE for version $VERSION"
else
    # Regenerate the full history (useful after many changes)
    git cliff --output "$CHANGELOG_FILE"
    echo "✓ Regenerated full $CHANGELOG_FILE"
fi

echo ""
echo "Review the top of $CHANGELOG_FILE, then:"
echo "  git add $CHANGELOG_FILE pyproject.toml"
echo "  git commit -m 'chore: prepare release vX.Y.Z'"