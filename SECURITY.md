# Security Policy for Savant

Savant gives AI agents persistent memory and the ability to evolve. Security is critical because the installer runs with user privileges and the framework can execute arbitrary agent code.

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
   - SavantHarness + genome execution can run user-provided (or pool-sourced) code.
   - Pools can contain arbitrary reasoning patterns and tool compositions.

4. **Data at Rest**
   - `~/.savant/` contains genomes, reasoning traces, and potentially sensitive agent memory.

### What We Do Today (Hardening)

- `set -euo pipefail` + environment variable hardening (`PYTHONPATH`, `PYTHONHOME` unset)
- HTTPS + TLS 1.2 enforcement on all downloads
- Checksum verification for bootstrapped binaries (gum)
- No execution of unverified downloaded code without user review path
- Clear separation between global pool and per-swarm isolated pools
- Explicit user consent for swarm pool creation

## Installer Security Recommendations for Users

The safest ways to install Savant (in order):

1. **Review the script first** (strongly recommended for first-time users):
   ```bash
   curl -fsSL https://raw.githubusercontent.com/PabloTheThinker/savant/main/scripts/install.sh -o savant-install.sh
   # Review the file
   less savant-install.sh
   bash savant-install.sh
   ```

2. Use the branded URL only after you trust the project:
   ```bash
   curl -fsSL https://vektraindustries.com/savant/install | bash
   ```

3. Pin to a specific release tag when available:
   ```bash
   curl -fsSL https://raw.githubusercontent.com/PabloTheThinker/savant/v0.2.0/scripts/install.sh | bash
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

Inspired by the rigorous security practices in:
- Hermes Agent (Nous Research)
- OpenClaw (lessons learned the hard way)

Thank you for helping keep the agent ecosystem trustworthy.

— The Savant Maintainers
