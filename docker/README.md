# AgentDrive — Self-Host

This directory ships a minimal, opinionated self-host story: a Dockerfile, a docker-compose deployment with one parent Drive, two sub-agent Drives, and a peer, plus a version manifest.

If you want a "kick the tires" local setup, prefer `make dev` from the repo root (see [`DEVELOPERS.md`](../DEVELOPERS.md)) — it runs without Docker. Use this directory when you want a deployment shape that looks like production.

## Quick start

```bash
cd docker
docker compose build
docker compose up -d
```

Wait ~20 seconds for healthchecks, then:

| Service       | URL                        | First-run setup            |
|---------------|----------------------------|----------------------------|
| Parent Drive  | http://127.0.0.1:8421      | Visit and complete `/setup`|
| Sub-agent A   | http://127.0.0.1:8431      | Visit and complete `/setup`|
| Sub-agent B   | http://127.0.0.1:8432      | Visit and complete `/setup`|
| Simulated peer| http://127.0.0.1:8441      | Visit and complete `/setup`|

Each daemon is a fresh AgentDrive instance with an empty pool, an empty cap store, and no admin user — the same first-run flow as a real deployment.

## Wiring the peer

1. On the **peer** daemon, mint a peer cap: `Capabilities → Mint` with scheme `peer`, action `publish`, resource `registry/root`.
2. On the **parent** daemon, register the peer: `Peers → Add Peer` with the peer's URL (`http://peer:8441` from inside the network, or `http://127.0.0.1:8441` from your host) and paste the cap.
3. Publish a genome on the peer side; watch it land in quarantine on the parent side.
4. Approve or reject from the parent's `Peers → Quarantine` page.

The federation handshake is described in detail in [`../docs/POOL-EVOLUTION.md`](../docs/POOL-EVOLUTION.md).

## State

State lives in named Docker volumes (`parent-data`, `subagent-a-data`, `subagent-b-data`, `peer-data`). `docker compose down` keeps the volumes; `docker compose down -v` wipes them.

## Production posture

This compose file is a **demo shape**, not a production recipe. Before exposing any of these ports beyond `127.0.0.1`:

- Put a reverse proxy with TLS in front of each Drive.
- Set `AGENTDRIVE_SECURE_COOKIES=1` and `AGENTDRIVE_TRUST_PROXY=1`.
- Switch from `127.0.0.1:` host bindings to internal-only Docker networks.
- Mount `/var/lib/agentdrive` to backed-up storage.

See [`../SECURITY-HARDENING.md`](../SECURITY-HARDENING.md) for the full production checklist.
