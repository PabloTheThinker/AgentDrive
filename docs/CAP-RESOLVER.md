# The Capability Resolver — AgentDrive's Single Access Primitive

> Every boundary in AgentDrive — local Drive, swarm Drive, peer federation, web daemon, SDK call — authorizes the same way, against the same code path. The capability URI is the only access primitive. This file shows the whole verifier in one screen.

## The grammar (one line)

```
agentdrive://scheme:action:resource_kind/resource_id?attenuation=value&...
```

| Slot            | Meaning                                              | Example                |
|-----------------|------------------------------------------------------|------------------------|
| `scheme`        | The subsystem this cap acts on                       | `drive`, `dna`, `peer` |
| `action`        | The verb                                             | `read`, `write`, `pull`, `mint`, `revoke` |
| `resource_kind` | The kind of thing being acted on                     | `agent`, `swarm`, `grant`, `quarantine` |
| `resource_id`   | The instance                                         | `personal`, `mission-payments-20260523` |
| `attenuation`   | Optional narrowing (`expires`, `sub`, `topic`, …)    | `expires=1748140800`   |

A cap is **signed by an issuer** (an Ed25519 keypair). Issuance is a separate concern; verification — what this document is about — assumes you already have a `SignedCap`.

## The resolver (30 lines)

This is the canonical verification path. The production implementation lives at [`src/agentdrive/cap/store.py:408`](../src/agentdrive/cap/store.py) (`CapStore.verify`) and [`store.py:434`](../src/agentdrive/cap/store.py) (`CapStore.verify_request`). The annotated reference:

```python
def verify_request(cap: SignedCap, ctx: CapVerifyContext, trust_roots, revoked) -> None:
    """The single arbiter. Every Drive boundary calls this."""

    # 1. Signature — was this URI signed by the claimed issuer's key?
    pub = Ed25519PublicKey.from_public_bytes(bytes.fromhex(cap.issuer_pubkey_hex))
    try:
        pub.verify(bytes.fromhex(cap.signature_hex), cap.uri.encode("utf-8"))
    except InvalidSignature as exc:
        raise CapInvalidError("signature check failed") from exc

    # 2. Trust root — is this issuer one we recognize?
    if (cap.issuer, cap.issuer_pubkey_hex) not in trust_roots:
        raise CapInvalidError(f"issuer {cap.issuer!r} not in trust roots")

    # 3. Expiry — has the cap's own expiry attenuation passed?
    expires = cap.capability.attenuation("expires")
    if expires is not None and time.time() > float(expires):
        raise CapInvalidError(f"cap expired at {expires}")

    # 4. Revocation — has the issuer (or operator) revoked it since it was minted?
    if cap.cap_id in revoked:
        raise CapInvalidError(f"cap {cap.cap_id} has been revoked")

    # 5. Scope — does the cap's capability cover the request the caller is making?
    requested = ctx.as_capability()                          # e.g. drive:write:agent/personal
    if not requested.is_narrower_than(cap.capability):       # subset check, not equality
        raise InsufficientCapability(
            f"cap {cap.uri!r} does not authorize request {requested.to_uri()!r}"
        )

    # No exception → access authorized. Caller appends an audit entry.
```

## Why this is "the AgentDrive moment"

Five checks, in a fixed order, with no escape hatches:

1. **Signature** proves the URI hasn't been forged in flight.
2. **Trust root** proves the issuer is someone this Drive recognizes — `trust_level` adjusts later behavior (peer quorum, quarantine policy), it does **not** bypass this check.
3. **Expiry** lets us mint short-lived caps without a revocation round-trip.
4. **Revocation** lets us kill a cap immediately, locally, without coordinating with the issuer.
5. **Scope** is the only check that depends on the request — and it's a single subset comparison (`is_narrower_than`), not a policy engine.

Every component verifies the same `SignedCap` the same way. The FastAPI daemon calls it through `require_cap()` in [`src/agentdrive/web/authz.py`](../src/agentdrive/web/authz.py:110). The SDK calls it through `RequestAuthorizer` in [`src/agentdrive/cap/store.py:450`](../src/agentdrive/cap/store.py). The peer federation layer calls it before promoting a quarantined genome. There is one verification function, and `CapStore.verify_request()` is it.

A contributor reading this file can hold the entire access model in their head.

## The 4 documented bypasses

There are exactly four routes that intentionally do **not** route through this function — operations *on* the auth system itself:

| Route                                     | Gate           | Why |
|-------------------------------------------|----------------|-----|
| `POST /setup`                             | unauthenticated| First-run bootstrap |
| `POST /signup`                            | unauthenticated| Onboarding |
| `POST /logout`                            | session-bound  | Session cleanup |
| `POST /settings/users/{user_id}/approve`  | `require_admin`| User lifecycle is admin-role meta |

These are documented in [`SECURITY-HARDENING.md`](../SECURITY-HARDENING.md). They still write to the audit log; their `decision` field reads `allow_admin` rather than `allow_cap`.

## Where to read next

- [`SECURITY-HARDENING.md`](../SECURITY-HARDENING.md) — production deploy checklist + admin-role notes
- [`docs/POOL-EVOLUTION.md`](POOL-EVOLUTION.md) — federation + quarantine + how trust roots interact with peer learning
- [`src/agentdrive/cap/uri.py`](../src/agentdrive/cap/uri.py) — the `is_narrower_than` implementation
- [`tests/test_capabilities.py`](../tests/test_capabilities.py) — adversarial tests for every check above
