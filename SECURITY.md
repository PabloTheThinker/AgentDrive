# Security Policy for Agent Drive

Agent Drive gives AI agents persistent memory and the ability to evolve. Security is critical because the installer runs with user privileges and the framework can execute arbitrary agent code.

## Supported Versions

| Version | Supported          |
| ------- | ------------------ |
| 0.2.x   | :white_check_mark: |
| < 0.2   | :x:                |

## Reporting a Vulnerability

**Please do NOT open a public issue for security vulnerabilities.**

Instead:

1. Email **pablo@vektraindustries.com** (or the address listed in the GitHub security advisories if available).
2. Use GitHub's private vulnerability reporting: Go to the repo → Security → Report a vulnerability.

Include:
- Description of the issue and potential impact
- Steps to reproduce
- Affected versions / environments
- Any proof-of-concept or logs (redact secrets)

We aim to respond within 48 hours and will coordinate a fix + disclosure timeline with you.

## Security Model & Threat Model

### High-Risk Areas

1. **Installer (`curl | bash`)**
   - The primary attack surface. A compromised `install.sh` or any binary it downloads (e.g. `gum`) can fully compromise the user's machine.
   - We treat the installer with extreme caution (see hardening below).

2. **Supply Chain**
   - `pip install git+...`
   - Downloaded binaries during bootstrap (gum, future Node/Python tools)
   - Dependencies in `pyproject.toml`

3. **Agent Execution Surface**
   - AgentDriveHarness + genome execution can run user-provided (or pool-sourced) code.
   - Pools can contain arbitrary reasoning patterns and tool compositions.

4. **Data at Rest**
   - `~/.agentdrive/` contains genomes, reasoning traces, and potentially sensitive agent memory.

### What We Do Today (Hardening)

- `set -euo pipefail` + environment variable hardening (`PYTHONPATH`, `PYTHONHOME` unset)
- HTTPS + TLS 1.2 enforcement on all downloads
- Checksum verification for bootstrapped binaries (gum)
- No execution of unverified downloaded code without user review path
- Clear separation between global pool and per-swarm isolated pools
- Explicit user consent for swarm pool creation

## Installer Security Recommendations for Users

The safest ways to install Agent Drive (in order):

1. **Review the script first** (strongly recommended for first-time users):
   ```bash
   curl -fsSL https://raw.githubusercontent.com/PabloTheThinker/AgentDrive/main/scripts/install.sh -o agentdrive-install.sh
   # Review the file
   less agentdrive-install.sh
   bash agentdrive-install.sh
   ```

2. Use the branded URL only after you trust the project:
   ```bash
   curl -fsSL https://vektraindustries.com/agentdrive/install | bash
   ```

3. Pin to a specific release tag when available:
   ```bash
   curl -fsSL https://raw.githubusercontent.com/PabloTheThinker/AgentDrive/v0.2.0/scripts/install.sh | bash
   ```

We publish the SHA256 of the installer script for each release in the GitHub release notes.

## Dependency Security

- We use `git-cliff` + conventional commits for transparent changelog.
- Dependabot is enabled for Python and GitHub Actions.
- We aim for minimal dependencies in the core package.

## Future / Roadmap Security Improvements

- [ ] Signed tags + commit signing requirement for releases
- [ ] SBOM generation on release
- [ ] Reproducible builds / lockfile for the installer bootstrap
- [ ] Optional verified install mode that checks script hash against release metadata
- [ ] Integration with OS keyrings for sensitive pool data (future)

## Credits

Shaped by the rigorous security practices we have seen across the open agent
ecosystem and by lessons learned the hard way.

Thank you for helping keep the agent ecosystem trustworthy.

— The Agent Drive Maintainers

---

## Snapshot Backup — localhost UI threat model (v2 Milestone 2d)

The Snapshot Backup UI binds `127.0.0.1:8420` by default. Three threats
specifically addressed by the implementation, in order of likelihood:

### Path traversal via `agent_id` / `snapshot_id`

The UI takes both identifiers from query strings and joins them into
filesystem paths under `~/.agentdrive/backups/`. A malicious
`agent_id="../../etc/passwd"` would otherwise escape the backup tree.

**Defense:** every identifier passes `_validate_id` in
`agentdrive.backup.snapshot` — strict whitelist `[A-Za-z0-9._:-]{1,128}`,
explicit rejection of `.` and `..`, plus a post-join `resolve()` check
that the path remains a descendant of `backup_root`. Failures raise
`SnapshotError`; the HTTP layer maps them to a 400 with no path
disclosure.

### CSRF from any same-browser cross-origin page

A page on `evil.example.com` open in the same browser as the operator
could otherwise issue
`fetch("http://localhost:8420/api/snapshots?agent_id=any", {method:"POST"})`
and the browser would carry the request — the localhost-only bind
doesn't help when the *browser* is the attacker's vector.

**Defense:** every `POST` and `DELETE` checks `_csrf_ok()` which requires
the request's `Origin` (or `Referer` if `Origin` is absent) to match the
bind address. Requests with no `Origin` and no `Referer` are allowed
(curl / direct CLI use). Any explicit cross-origin write returns 403.

### Clickjacking / framing

A page could embed `http://localhost:8420/` in an iframe and trick the
operator into clicking restore/delete actions in the embedded UI.

**Defense:** every response carries `X-Frame-Options: DENY` and the HTML
endpoint additionally ships `Content-Security-Policy: frame-ancestors
'none'`. The UI cannot be embedded by any third-party page.

### Out of scope (explicitly)

- **DNS rebinding** against `localhost`. Modern browsers' rebinding
  protections + the Origin check together make this very hard, but the
  threat is acknowledged. Operators concerned about it should bind to a
  Unix domain socket (not yet supported — v3 work).
- **Operators who explicitly override the bind to a non-loopback
  interface.** Once `host` is anything other than `127.0.0.1`, the
  caller has opted into a network-exposed service and is responsible
  for additional protection (reverse proxy with auth, firewall, etc.).
- **Auditing snapshot manifests for tampering.** Manifests aren't
  signed in v2 — assumed in-trust-boundary. Cap-URI signing for
  snapshot operations is v3 work tracked under M3 follow-ups.

## History-rewrite policy

If a credential or genuinely-private identifier ever lands in a commit,
the policy is: rewrite + force-push immediately, then notify any known
consumers. Non-credential cruft from the early-iteration period is
periodically squashed into clean release-marker commits to keep
``git log -S`` searches honest.
