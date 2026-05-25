# Postmortem — INC-2026-05-14-001 (critical)

## Witnessed Timeline (with citations)
- 2026-05-14T14:22:03Z [auth-svc] deploy v2.3.1 triggered by CD (citation: pipeline run #4821)
- 2026-05-14T14:23:11Z [auth-svc] health check failed on /ready (2/3 replicas) (obs: pod log)
- ...

## Blast Radius
- 47 user sessions affected (witnessed count from lb metrics + session store)
- Contradiction: support reported 120, metrics said 47 -> root: double counting of health probes

## Root Cause (causal)
Primary: missing feature flag for new rate limiter in v2.3.1
Contributing: no canary, alert fatigue on prior warnings, shared redis pool not isolated

## Action Items
- [owner: infra] Roll back + isolate redis by 2026-05-15 EOD
- [owner: auth-team] Add integration test for rate limiter + flag 2026-05-16
- [owner: sre] Update runbook with "verify feature flags in canary" checklist

Prevention design: mandatory 2-stage rollout + automated flag audit in CD.
