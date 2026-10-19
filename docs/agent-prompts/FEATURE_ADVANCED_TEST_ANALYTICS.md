# Coding-Agent Prompt — Advanced Test Analytics

## Read first
Read `docs/FEATURE_SPEC_ADVANCED_TEST_ANALYTICS.md`, `docs/FEATURE_SPEC_TEST_SERIES.md`, the master prompt, and current milestone instructions. Inspect the existing quiz/test models, attempt snapshots, result-release policy, APIs, permissions, frontend, and tests before proposing changes.

## Execution constraints
- Work only on the currently authorized milestone; Milestone 1 remains foundation verification and must not implement analytics.
- Reuse the current test engine. Do not create duplicate attempt or analytics models without a documented need.
- Do not change source code when the authorized task is documentation-only. During implementation runs, make source changes and tests appropriate to that milestone.
- Keep student metrics scoped to the authenticated student; restrict staff aggregates and attempt details by role and ownership.
- Never expose unreleased results, answer keys, other students' private data, or client-supplied score values.

## Implementation expectations
1. Agree and document metric formulas and denominators before coding.
2. Derive metrics from persisted server-scored attempts and immutable attempt snapshots.
3. Add authorized, bounded APIs for student insights and staff aggregate reports.
4. Handle insufficient data honestly and display sample sizes/date ranges.
5. Add mobile-friendly charts/tables with accessible labels and loading, empty, and error states; avoid decorative/fabricated data in production.
6. Escape spreadsheet-formula prefixes for permitted CSV exports; audit sensitive export access.
7. Add calculation, privacy, permission, result-release, pagination, and query-performance tests.
8. Update implementation plan/build status only with observed evidence.

## Report
List changed files, metric formulas, API permissions, tests and exact outcomes, deferred metrics, and remaining risks. Stop at the end of the authorized milestone.
