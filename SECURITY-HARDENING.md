# Savant Security Hardening Summary

This document records the security improvements made to the Savant project so it can be safely recommended to many users.

**Date:** May 2026 (last mission sprint)
**Status:** Production baseline achieved

---

## 1. Installer Hardening (Highest Priority)

The `curl | bash` path is the primary way new users install Savant. It was the biggest risk.

### Changes Made

- **Mandatory checksum verification for bootstrapped binaries** (`gum`)
  - Previously "best effort" (non-fatal)
  - Now the installer refuses to use any downloaded `gum` binary if checksum verification fails or is impossible.

- **Strict transport security on all downloads**
  - All `curl` calls now use `--proto '=https' --tlsv1.2`
  - Retries with backoff

- **Early `git` prerequisite check**
  - Detects missing `git` *before* attempting any `git+` pip install
  - Gives clear OS-specific install instructions

- **Correct git URL syntax in error messages**
  - Fixed broken `@main` suggestions → proper `#branch=main`

- **Real error output is always shown**
  - No more silent `--quiet 2>/dev/null` swallowing of pip failures

- **Environment hardening**
  - Unsets `PYTHONPATH` and `PYTHONHOME`
  - `set -euo pipefail`

- **Gum bootstrap is now safer**
  - Only used for UX (spinners/confirm); never required for core functionality

---

## 2. Repository & Supply Chain Security

- Added `SECURITY.md` with:
  - Threat model
  - Vulnerability reporting process
  - Safe installation recommendations for users

- Enabled **Dependabot** (` .github/dependabot.yml `)
  - Weekly updates for Python and GitHub Actions
  - Grouped updates to reduce noise

- Added **CodeQL** security analysis workflow
  - Runs on push/PR to `main` + weekly scheduled scan

- No `.github/` directory existed before these changes (major gap)

---

## 3. Delivery Layer (Vektra Site)

The branded installer URL (`https://vektraindustries.com/agentdrive/install`) is served by a Next.js route that fetches from GitHub raw.

Hardening applied:
- `X-Content-Type-Options: nosniff`
- `Strict-Transport-Security` (HSTS)
- `X-Frame-Options: DENY`
- Proper `text/x-sh` Content-Type

---

## 4. Release Process Security

- New `scripts/release.sh` orchestrator
- Encourages annotated tags
- Clear separation between preparation and publishing
- Future: recommend signed tags (`git tag -s`)

---

## 5. Hardening Principles

| Principle                                          | Implementation                          |
|----------------------------------------------------|-----------------------------------------|
| Environment isolation, defensive scripting         | PYTHONPATH/PYTHONHOME unset, set -euo   |
| Careful root vs user handling                      | Early git check + clear messages        |
| Mandatory checksums on downloaded binaries         | gum bootstrap verifies SHA256           |
| Never hide real errors from the user               | tmp_log is always printed on failure    |
| Least privilege for bootstrap tools                | gum is optional and only for UX         |

---

## Recommended User Installation Order (Post-Hardening)

1. **Safest**: Download + review script manually, then execute
2. Use the branded URL (now much safer)
3. Pin to a specific release tag when available

We publish the SHA256 of `install.sh` in every GitHub release.

---

## Remaining / Future Work (when credits allow)

- [ ] Require signed commits + signed tags for `main` and releases
- [ ] Add SBOM generation on release (`syft` or `cyclonedx`)
- [ ] Optional "verified install" mode that checks script hash against release metadata
- [ ] GitHub branch protection rules + required status checks
- [ ] Security.txt / `.well-known/security.txt`
- [ ] Consider reproducible builds for the Python package

---

**This baseline means Savant can now be responsibly recommended to a wider audience without the high risk of supply-chain or installer-based compromise that has affected other projects.**

The 1% credits "last mission" focused on the highest-leverage security controls for a project whose primary onboarding method is `curl | bash`.