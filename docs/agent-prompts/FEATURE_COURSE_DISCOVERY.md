# Coding-Agent Prompt — Course Discovery and Search

Read `docs/FEATURE_SPEC_COURSE_DISCOVERY.md`, the master prompt, and current course models, API endpoints, frontend catalogue, and tests before editing.

## Execution rules
- Implement only the currently authorized milestone. Milestone 1 is foundation verification only.
- Reuse the existing course catalogue and API; no duplicate catalogue and no unnecessary framework migration.
- Published content visibility and paid-resource authorization must remain server-enforced.
- Do not expose draft metadata, protected content URLs, access codes, or private provider details in search/filter responses.
- Do not invent popularity scores or silently fake API results.

## Tasks when authorized
1. Audit existing catalogue/search behavior and list gaps.
2. Add bounded, validated search, filters and ordering to the existing API.
3. Add appropriate indexes only after query-plan/data-model review.
4. Wire the mobile-first catalogue UI to real paginated API responses, preserving filters and providing loading/empty/error/offline states.
5. Add tests for visibility, filters, query safety, pagination, private-field leakage and performance.
6. Update build status and implementation plan only with observed evidence.

## Report
List changed files, API/filter behavior, tests and exact results, unresolved limitations, and next milestone. Stop after the authorized milestone.
