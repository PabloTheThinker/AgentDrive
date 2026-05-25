# AgentDrive v2 — Research

> Source dossier for [`AGENTDRIVE-V2.md`](AGENTDRIVE-V2.md). Every claim about
> ProtonDrive / Google Drive / Dropbox / iCloud / Syncthing / Resilio /
> Tahoe-LAFS in the v2 architecture proposal is sourced here.
>
> Compiled: 2026-05-24. Word count: ~2,350.

## 1. ProtonDrive

**Primitives.** Files are split into ≤4 MB blocks. Each block is AES-encrypted, and block content-hashes are linked in succession and signed with the uploader's address key to prevent reorder/removal.

**Key hierarchy.** Address Key → Share Key → Node Key (per file/folder) → Content Key. The share passphrase is wrapped by each member's address key, so adding a collaborator does NOT require re-encrypting the data — only re-wrapping the share passphrase. Node passphrases are wrapped by the parent node's key (Merkle-shaped key tree).

**Sharing.** A "Share" is the access-card primitive. Multiple members per share with admin/read/write roles. Public link sharing uses a password the Proton server never receives.

**Sync, conflicts, versioning.** Free: up to 10 versions / 7 days. Paid: up to 200 versions / 10 years, configurable retention. Trash is reversible but counts against quota; items remain encrypted at rest in trash.

**Distinctive choice.** Key-tree-rooted-at-share. Sharing is a re-wrap operation, not a re-encrypt; revocation requires content-key rotation to be genuinely cryptographic.

**Anti-patterns.** Revocation is the weak point of all E2EE key-wrap schemes — anyone who held a key can keep decrypting cached blocks. Collaborative editing arrived late (2024) precisely because OT/CRDT under E2EE is hard.

Sources: [Proton blog](https://proton.me/blog/protondrive-security), [ETH thesis](https://ethz.ch/content/dam/ethz/special-interest/infk/inst-infsec/appliedcrypto/education/theses/lea-micheloud-master-thesis.pdf), [Proton version history](https://proton.me/support/version-history).

## 2. Google Drive

**Primitives.** Object/BLOB storage for content; Bigtable/Spanner for metadata (per public system-design accounts — Google does not publish primary architecture docs, flag uncertainty).

**Encryption.** Server-side only; Google holds keys. No E2EE for Drive content.

**Sharing.** Granular ACLs (per-user, per-group, per-domain, per-link) with role escalation (viewer/commenter/editor/owner). Revocation is effective because the server enforces access at read time.

**Sync.** Delta sync over long-lived connections (WebSocket/gRPC per public reverse-engineering).

**Conflicts.** Binary files: optimistic locking with version vectors; loser becomes a conflict copy. Docs/Sheets/Slides: Operational Transform server-side.

**Versioning.** Native files: unlimited revision history. Uploaded binaries: 30 days / 100 versions unless "Keep forever" is set.

**Distinctive choice.** Server is the single source of truth and the transform authority — enables OT, real-time presence, and cryptographic-free revocation.

**Anti-patterns.** Zero E2EE story for the consumer product; sharing-by-link is a recurring data-leak vector.

Sources: [Educative system design](https://www.educative.io/blog/google-drive-system-design), [CRDT vs OT analysis](https://medium.com/@sohail_saifi/building-collaborative-editing-the-battle-between-operational-transform-and-crdts-fdceb63c54ac).

## 3. Dropbox

**Primitives.** Files split into 4 MB blocks (Magic Pocket), SHA-256 content-addressed, immutable. Cassandra indexes hash→location. Brotli-compressed at rest via the Broccoli pipeline.

**Sync engine.** Nucleus (Rust rewrite, 2020). Streaming events, not polling. Block-level delta sync — only changed blocks transit. Global dedup across the entire tenant.

**LAN Sync.** Discovers peers on the same subnet over a UDP broadcast and pulls blocks locally instead of from the cloud.

**Smart Sync.** Placeholder files via kernel extensions / projfs / FUSE-like mounts; metadata only until accessed.

**Conflicts.** "Conflicted copy" pattern: never destroys data; renames the losing version with device + timestamp.

**Versioning.** 30 days standard, 180 days Plus, up to 10 years Business.

**Distinctive choices.** (1) Content-addressed immutable blocks → dedup and cheap versioning come for free. (2) The sync engine and the storage engine are decoupled, allowing Nucleus rewrites without touching Magic Pocket.

**Anti-patterns.** Smart Sync × LAN Sync interactions are buggy. Conflicted copies multiply silently in heavy-concurrent workloads.

Sources: [Dropbox tech blog — Magic Pocket](https://dropbox.tech/infrastructure/inside-the-magic-pocket), [Broccoli](https://dropbox.tech/infrastructure/-broccoli--syncing-faster-by-syncing-less), [Akshay Ghalme — delta sync](https://akshayghalme.com/blogs/how-dropbox-delta-sync-works/).

## 4. iCloud / CloudKit / Keychain

**Primitives.** CloudKit Records (structured) + Assets (large blobs), grouped in Containers with public/private/shared databases.

**Encryption.** Tiered: "available-after-authentication" (Apple holds keys) vs "end-to-end encrypted" (Apple does not). Advanced Data Protection (ADP) promotes most categories to E2EE.

**Key sync — the genuinely interesting part.** iCloud Keychain uses a *syncing circle of trust*: each device generates a P-384 identity keypair, signs the trust-list, and other devices vote a new device in via signed vouchers. CloudKit Service Keys are then synced through this circle. No central authority — Apple servers cannot join the circle.

**Sharing under E2EE.** CKShare primitive; participants exchange keys peer-to-peer through the trusted-device fabric.

**Conflicts.** Record-level optimistic concurrency with a server change-token; clients merge or rewrite on conflict (developer-defined).

**Distinctive choice.** Device-trust circle for key sync — a working production example of zero-knowledge key distribution without a central authority.

**Anti-patterns.** Circle bootstrapping requires at least one trusted device; full-account loss = data loss. Recovery via iCloud Security Code adds attack surface.

Sources: [Apple — keychain syncing](https://support.apple.com/guide/security/secure-keychain-syncing-sec0a319b35f/web), [iCloud encryption](https://support.apple.com/guide/security/icloud-encryption-sec3cac31735/web), [Advanced Data Protection](https://support.apple.com/guide/security/advanced-data-protection-for-icloud-sec973254c5f/web).

## 5. Syncthing

**Primitives.** Files in variable-size blocks (128 KiB–16 MiB, powers of two). Each device announces a Local Model (file list + block hashes); the *Global Model* is the union, picking the highest-version per file. Devices pull missing blocks from any peer that has them.

**Trust.** Device IDs are self-signed Ed25519 public keys; pairing is manual key exchange. No central authority.

**Conflicts.** Per-file version vectors. On divergence, the loser is renamed `name.sync-conflict-<date>-<deviceID>.ext`. Zero data loss; resolution deferred to the human.

**Versioning.** Pluggable: simple/staggered/trash-can/external.

**Distinctive choice.** Global Model as deterministic merge function across N peers using version vectors — no quorum, no leader.

**Anti-patterns.** Conflict files pile up; no automatic merge. Pure push-model means a device offline for weeks can resurrect deleted files unless tombstones are honored.

Sources: [BEP spec](https://docs.syncthing.net/specs/bep-v1.html), [DeepWiki](https://deepwiki.com/syncthing/syncthing/2.2-synchronization-model).

## 6. Resilio Sync

**Primitives.** Similar block model to BitTorrent (Resilio's heritage). Folder identity is a *Key* (Ed25519); RW key derives RO key and Folder ID via hash.

**Trust.** Pure capability model: possession of the key = membership. DHT for peer discovery; AES-128 session over TLS.

**Distinctive choice.** Read-only key derived from read-write key — a capability degradation primitive without server mediation.

**Anti-patterns.** Key leakage = unrevocable access (no central authority can rotate). Closed source limits auditability.

Sources: [Resilio Security Brief](https://www.resilio.com/docs/Resilio_Sync_Security_and_Privacy_Brief.pdf), [Key structure](https://help.resilio.com/hc/en-us/articles/206767810-Key-structure-and-flow).

## 7. Tahoe-LAFS

**Primitives.** Files are AES-encrypted client-side, then erasure-coded into N=10 shares (default), K=3 needed to reconstruct ("3-of-10"). Shares scattered across storage servers; servers see only opaque ciphertext shares.

**Capability URIs.** The unforgeable URL-like string `URI:CHK:<readkey>:<verifykey>:K:N:size` IS the access right. Three flavors: write-cap → read-cap → verify-cap (each derivable from the previous via one-way functions). No ACLs anywhere — possession of the cap is authorization.

**Directories.** Mutable dirnodes contain (name, read-cap, write-cap, metadata) tuples for children.

**Distinctive choice.** Pure capability-based security. No identity, no authentication, no ACLs. The cap IS the permission. Combine with erasure coding and you get a system where storage providers are untrusted by design.

**Anti-patterns.** Cap revocation is impossible — you must re-encrypt, mint a new cap, and tell everyone. Mutable files use a complex Small/Medium Distributed Mutable File protocol; concurrent writes can produce uncoordinated update conflicts.

Sources: [Tahoe-LAFS architecture](https://tahoe-lafs.readthedocs.io/en/latest/architecture.html), [dirnodes spec](https://github.com/tahoe-lafs/tahoe-lafs/blob/master/docs/specifications/dirnodes.rst).

---

## Cross-cutting patterns

| Dimension | ProtonDrive | Google Drive | Dropbox | iCloud/CK | Syncthing | Resilio | Tahoe-LAFS |
|---|---|---|---|---|---|---|---|
| **Atom** | 4 MB block | object | 4 MB content-addr block | Record + Asset | 128 KiB–16 MiB block | block | erasure-coded share |
| **Encryption** | E2EE, key tree | server-side | server-side (E2EE add-on) | tiered; E2EE under ADP | TLS in transit | E2EE per folder | E2EE, cap-derived key |
| **Sharing** | re-wrap share passphrase | server-ACL | server-ACL | CKShare via trust circle | manual device pairing | possession of Key | possession of Cap |
| **Sync** | client/server, delta | delta, push events | streaming delta, LAN | CloudKit change-tokens | pull-from-global-model | DHT + P2P pull | client pull from N servers |
| **Conflicts** | last-write + version | OT (docs) / conflict copies | conflict copies | optimistic concurrency | version vectors + .sync-conflict | conflict copies | mutable-file UCWE |
| **Versioning** | 10–200 versions | 30 days / 100 binaries | 30d–10y | per-record | pluggable | configurable | mutable file history |
| **Coherence** | server-coordinated | strong (server-truth) | strong (server-truth) | eventual via circle | eventual (vector-vector merge) | eventual | eventual + erasure |
| **Distinctive** | key-tree-per-share | OT + server-truth | content-addr immutability | device trust circle | global-model merge | RW→RO key derivation | capability URIs |

---

## Flagged uncertainties

- Google Drive internals are not primary-source — no official architecture paper; described from third-party system-design reconstructions.
- Dropbox Nucleus details come from blog summaries, not the source.
- Proton SRP login flow not confirmed in fetched docs.

These uncertainties do not affect the v2 design choices — we're lifting patterns at the architectural level, not implementation details.
