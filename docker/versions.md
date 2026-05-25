# Image versions

Track which base + AgentDrive versions a given compose file is pinned to. Bump on every release.

| Component        | Pin              | Notes                              |
|------------------|------------------|-------------------------------------|
| Base image       | `python:3.12-slim` | Track Python LTS                   |
| AgentDrive image | `0.1.0`          | Built from `pyproject.toml` version |
| Genome schema    | `v1`             | Bump when `drive/genome.py` changes |
| Cap URI grammar  | `v1`             | Bump when `cap/uri.py` changes      |

The schema-version and cap-grammar pins matter because they govern **compatibility between peers**. A 0.2.0 daemon with cap grammar `v2` will not federate cleanly with a 0.1.0 daemon. The release notes call out the bump explicitly.

To check what a running daemon advertises: `curl http://127.0.0.1:8421/healthz` returns `version`. To check the schema version of stored genomes: open any file under `~/.agentdrive/genomes/` and read the `schema_version` field.
