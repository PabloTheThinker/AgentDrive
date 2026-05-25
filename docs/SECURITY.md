# AgentDrive Capability Boundary Notes

`agentdrive.cap.RequestAuthorizer` is the first concrete boundary adapter for
the capability URI model. It wraps `CapStore.verify_request()` and provides
named checks for Drive reads/writes and DNA pulls, including short-lived session
caps minted through `CapStore.mint_session()`.

## DNA Workflow Gaps

- `DNADrive.pull_inherited()` accepts `max_depth` and `min_eval`, but it does
  not yet require a `dna:pull:lineage:<agent>` capability. The next call-site
  wiring is to invoke `RequestAuthorizer.verify_dna_pull()` before reading
  ancestors.
- `LineageShareGrant` TTL currently gates new cousin pulls only; data already
  received remains local by design. A future cap-backed cousin pull should
  translate grant scope into a short-TTL `dna:pull` cap for the grantee.
- Cross-source grant pulls still return `InheritedGenome` objects directly.
  The existing contract says those results must route through quarantine before
  active use; `DNADrive.pull_inherited()` has no quarantine step because direct
  ancestors are trusted by default.

## Remaining Boundary Integration Points

- `AgentDrive.ingest()` -> require `drive:write:swarm:<id>` or
  `drive:write:agent:<id>`.
- `AgentDrive.query()` -> require `drive:read:swarm:<id>` or
  `drive:read:agent:<id>`.
- Web snapshot actions -> require `backup:read|write|restore:agent:<id>` before
  list/create/delete/restore.
- Peer sync -> require `drive:write:peer:<peer_id>` before accepting remote
  material, then continue routing all remote DNA through quarantine.
- `DNADrive.pull_inherited()` -> require `dna:pull:lineage:<agent_id>` with
  matching `max_hops` and `min_eval` attenuations.
