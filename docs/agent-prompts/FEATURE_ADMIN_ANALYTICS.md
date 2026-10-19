# Coding-Agent Prompt — Admin and Sub-Admin Analytics

Read `docs/FEATURE_SPEC_ADMIN_ANALYTICS.md`, `docs/FEATURE_SPEC_ADVANCED_TEST_ANALYTICS.md`, existing course/access-code/progress/test models, and the current milestone prompt.

## Rules
- Respect the existing milestone order; Milestone 1 is verification only.
- Reuse real persisted data and the existing admin/staff permission model.
- Main admin scope is platform-wide; sub-admin scope is owned/assigned resources only.
- Never invent historical metrics or expose private student data by default.
- Do not add third-party analytics services without explicit approval.

## Tasks when authorized
1. Inventory which events and metrics are already reliably stored.
2. Define formulas and identify gaps before adding models or migrations.
3. Implement bounded, permission-safe aggregate endpoints and responsive dashboard UI in the correct milestones.
4. Add audit records for sensitive exports/admin actions, without storing secrets.
5. Add tests for aggregate correctness, role boundaries, privacy, filtering, exports, and query behavior.
6. Update status/plan from actual evidence only.

## Report
List metrics actually backed by data, missing historical signals, changed files, tests and exact results, privacy risks, and next milestone. Stop after the authorized milestone.
