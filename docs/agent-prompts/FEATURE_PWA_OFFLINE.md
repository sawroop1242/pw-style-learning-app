# Coding-Agent Prompt — PWA Offline and Low-Data Mode

Read `docs/FEATURE_SPEC_PWA_OFFLINE.md`, Milestone 9, the master prompt, service worker/manifest, API client, and current tests.

## Execution rules
- Milestone 1 remains foundation verification. Offline implementation belongs in its authorized milestone, chiefly Milestone 9, with earlier prerequisites completed first.
- Do not cache authenticated API responses, tokens, private notes, active tests, answer keys, or protected media in shared caches.
- Do not assume a video embed can be downloaded. Respect provider terms and course access checks.
- Never tell users a queued update is saved until the server confirms synchronization.
- Avoid introducing paid services or large libraries without approval.

## Tasks when authorized
1. Inventory existing PWA behavior and define cache policy by resource type.
2. Implement versioned caches, update/cleanup logic, offline indicator, and bounded low-data preference.
3. Add safe pending-sync behavior only for APIs with documented conflict/idempotency semantics.
4. Handle logout/account switch and protected-resource access changes.
5. Add unit/browser tests and perform real install/offline/cache inspection in supported browsers.
6. Document tested offline capabilities and limitations accurately.

## Report
List cache policy, data excluded from caching, tests/browser environment and exact results, limitations, and next milestone. Stop after the authorized milestone.
