#!/usr/bin/env bash
# Generate CHANGELOG.md using git-cliff (preferred) or a basic fallback.
# Usage:
#   ./scripts/generate_changelog.sh          # appends unreleased changes
#   ./scripts/generate_changelog.sh --tag v0.2.0

set -euo pipefail

TAG="${1:-}"

if command -v git-cliff >/dev/null 2>&1; then
    if [ -n "$TAG" ]; then
        git cliff --tag "$TAG" -o CHANGELOG.md
    else
        git cliff --unreleased -o CHANGELOG.md --prepend
    fi
    echo "Changelog generated with git-cliff"
else
    echo "git-cliff not found. Install it from https://git-cliff.org/ for best results."
    echo "Falling back to basic git log (not as nice)."
    echo
    {
        echo "## Unreleased"
        echo
        git log --pretty=format:"- %s (%h)" -n 30 --no-merges
        echo
    } >> CHANGELOG.md
fi

echo "Done. Review CHANGELOG.md and commit it with your release."