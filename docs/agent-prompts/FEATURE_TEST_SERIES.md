# Coding-Agent Prompt — Test Series, CSV Question Bank, Timers, and Results

## Read first
Read `docs/FEATURE_SPEC_TEST_SERIES.md` in full and inspect the existing quiz/test models, migrations, Django admin, API, permissions, frontend, and tests. Reuse the current quiz engine where sound. Do not create a second parallel quiz system merely because the feature is called a test series.

## Milestone discipline
- Execute only the currently authorized milestone from `docs/agent-prompts/README.md`.
- Milestone 1 remains foundation verification only; do not implement test features during foundation verification.
- Milestone 2 adds the required data model and staff admin capabilities.
- Milestone 3 secures main-admin/sub-admin/student permissions and ownership.
- Milestone 5 implements CSV import/export, immutable question snapshots, timer semantics, server-side scoring, attempts, and results.
- Milestone 8 delivers the student and staff end-to-end user journeys.
- Milestones 9 and 10 verify PWA behavior, privacy, accessibility, security, and regression coverage.
- Do not skip milestones or mark a milestone complete without running its checks.

## Required behavior
1. Main admin and authorized sub-admins can create/manage test series and tests; sub-admin access is limited to owned/assigned content.
2. A test supports questions, options, correct answer(s), optional explanation, marks, negative marks, topic/difficulty, and section membership according to the feature spec.
3. Staff can upload a documented CSV template. Validate all rows and correct-option mappings, preview row-level errors, and confirm import before writing. Prevent accidental duplicate/partial imports and formula injection on exports.
4. Admin can choose timed or untimed mode; configure a total duration and optional per-section timers, navigation/locking policies, start/end availability, attempt limits, shuffle rules, and result-release policy.
5. Server time/deadlines and server-side scoring are authoritative. Browser timers are displays only. Refresh/resume must not reset a deadline. Untimed practice must not expire because of elapsed time.
6. Autosave, mark-for-review, question palette, early submit, timeout auto-submit, idempotent submission, result review and section analytics should be implemented as supported by the existing architecture and feature spec.
7. Correct answers and explanations must not leak before the configured release point. Store a question/rule snapshot per attempt so later edits cannot change historical scoring.
8. Main admin, sub-admin, and student permissions must be enforced server-side and tested.
9. Do not add invasive proctoring/surveillance by default.
10. Do not invent working functionality: report any feature deferred due to scope or architectural limitations and update the plan.

## Required report
List changed files, schema/migration decisions, CSV schema, timing/scoring rules, exact tests and results, security gaps, deferred features, and status/plan updates. Stop after the authorized milestone.
