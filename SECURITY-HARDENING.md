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
---

## Production deploy checklist

The single-operator daemon is meant to run behind a reverse proxy (nginx,
Caddy, Tailscale Serve, Cloudflare Tunnel) on a host the operator owns.
The defaults are safe on `127.0.0.1`; the moment that surface faces a
network — even a private one — the items below MUST be set.

### Bind + transport

- `agentdrive web` binds to `127.0.0.1:8421` by default. Do NOT bind it
  to `0.0.0.0` directly; put it behind a reverse proxy that terminates
  TLS.
- `AGENTDRIVE_SECURE_COOKIES=1` — flips session cookies to `Secure`.
  Without it, a misconfigured reverse-proxy step can serve the cookie
  over plaintext.
- `AGENTDRIVE_TRUST_PROXY=1` — tells the rate limiter to honor
  `X-Forwarded-For`. Without it, every request looks like it's coming
  from `127.0.0.1` and the limiter degenerates to a single shared
  bucket. Only set it when the daemon is actually behind a proxy that
  strips spoofed inbound headers.

### Capability transport

- Browser operators get implicit owner rights via session cookie.
- **Non-browser callers** (SDKs, sub-agents, automation) MUST present
  a capability via `Authorization: Bearer <cap_id>` where `cap_id` is
  the UUID returned by `CapStore.mint()` (or by `POST /capabilities`
  in the web UI).
- The cap is verified against the route's required `(scheme, action,
  resource_kind, resource_id)` context. Narrower-than subset rules in
  `agentdrive.cap.uri.is_narrower_than` mean a `drive:write:agent:personal`
  cap covers an `agentdrive` import request scoped to that resource,
  but a `drive:read:…` cap does not.
- Every allow / deny is appended to `~/.agentdrive/audit.log` (JSONL)
  with `ts`, `decision`, `reason`, `principal`, `scheme`, `action`,
  `resource_kind`, `resource_id`, `request_id`, `path`. Ship that file
  to your log aggregator.

### Process supervision

- Run the daemon as a non-root user that owns `~/.agentdrive/`.
- Restart on failure (systemd `Restart=on-failure`, k8s `restartPolicy:
  Always`, monit, etc.).
- `/healthz` returns 200 + `{status, version, uptime_s}` once the app
  is wired. Use it as your liveness probe. It is intentionally narrow:
  no `has_users`, no DB stats, no enumeration vector.
- `/metrics` exposes Prometheus counters (genomes, snapshots, active
  caps, swarms, peers, quarantine pending). Scrape with Prometheus,
  point a Grafana board at it, or alert on `quarantine_pending > 0`.

### Storage

- `~/.agentdrive/` should be on a disk you back up. The content store
  is hash-addressed, so any incremental backup tool (restic, borg)
  will dedupe well across snapshots.
- All sqlite databases (`auth.db`, `caps.db`, `grants.db`,
  `dna/<agent>/...`, plus per-Drive registries) are opened in **WAL**
  mode with `synchronous=NORMAL` and a 5-second `busy_timeout`. Safe
  for concurrent reads alongside writes, but a hostile process with
  filesystem access can corrupt them — protect via file permissions
  (`chmod 700 ~/.agentdrive/`).

### What NOT to do

- Do not expose `agentdrive web` directly to the public internet
  without TLS in front of it.
- Do not set `AGENTDRIVE_TRUST_PROXY=1` if you are NOT behind a proxy
  that scrubs inbound `X-Forwarded-For` — clients can otherwise spoof
  the IP the rate limiter sees.
- Do not run as root.
- Do not log `Authorization` headers or session cookies — the JSON
  request logger never does, but custom middleware authors should
  keep this in mind.
