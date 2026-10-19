# StudySpace Coding-Agent Prompt Pack

These files are **execution prompts for a coding agent**, not implementation deliverables. The agent must use them to modify and test application source code. Do not satisfy a prompt by merely writing more documentation.

## How to use

1. Open the repository in your coding agent with write access and terminal access.
2. Give the agent `docs/BUILD_MASTER_PROMPT.md` and this index.
3. Run **one milestone prompt per agent session**. Start at Milestone 1 because the initial repository audit is recorded already, but its verification remains pending.
4. The agent must inspect current files and git status before editing, implement actual source changes, run tests, update `docs/BUILD_STATUS.md` and `docs/IMPLEMENTATION_PLAN.md`, and stop at the end of that milestone.
5. If the current milestone fails its exit criteria, the agent must fix it or report the exact blocker. It must not skip ahead or mark it complete.

## Frontend and backend implementation plans

Use the separate plans to clarify ownership while preserving the single ordered milestone sequence:
- [Frontend implementation plan](../FRONTEND_IMPLEMENTATION_PLAN.md) — user journeys, screens, API client, UI states, PWA/offline, accessibility and browser checks.
- [Backend implementation plan](../BACKEND_IMPLEMENTATION_PLAN.md) — models, API contracts, authentication/authorization, scoring, CSV URL imports, analytics, security and operations.

These plans complement rather than replace the master prompt, shared implementation plan, feature specs, or milestone prompts. Start with Milestone 1 foundation verification and proceed in order. A Markdown plan is not implementation evidence.

## Product feature specification

Read [Course management and code-based access](../FEATURE_SPEC_COURSES_AND_ACCESS_CODES.md) for the required admin/sub-admin roles, course folders, video/PDF resources, free/paid course rules, Telegram provider contact, and secure access-code redemption. The execution wrapper is [Course-management coding-agent prompt](FEATURE_COURSE_MANAGEMENT_ACCESS_CODES.md). These requirements are integrated into the relevant existing milestones; do not skip the milestone order.

## Authentication specification

Read [Authentication and email OTP reset](../FEATURE_SPEC_AUTHENTICATION.md) and follow [the authentication coding-agent prompt](FEATURE_AUTHENTICATION.md). Registration requires unique username, email, and password; users can change their password and reset forgotten passwords with a short-lived email OTP. OTP mail uses owner-configured Gmail SMTP or another supported SMTP provider through deployment environment secrets. Never commit SMTP credentials.

## Test-series specification

Read [Test series, CSV question bank, timers, and results](../FEATURE_SPEC_TEST_SERIES.md) and follow [the test-series coding-agent prompt](FEATURE_TEST_SERIES.md). CSV imports use an externally hosted CSV URL: backend stores the URL and minimal import metadata, never the CSV file/blob/raw contents; imported question data is stored as structured records. Apply SSRF-safe fetching and the existing milestone sequence.

## Additional feature specifications and coding prompts

These are feature-level requirements integrated into the existing milestones, not permission to skip the milestone sequence:

- [Advanced test analytics](../FEATURE_SPEC_ADVANCED_TEST_ANALYTICS.md) — [coding prompt](FEATURE_ADVANCED_TEST_ANALYTICS.md). Extends the existing test engine; respect result-release rules and staff ownership.
- [Notes, bookmarks, and revision](../FEATURE_SPEC_NOTES_BOOKMARKS_REVISION.md) — [coding prompt](FEATURE_NOTES_BOOKMARKS_REVISION.md). Extends existing notes/progress and avoids a parallel notes system.
- [Course discovery and search](../FEATURE_SPEC_COURSE_DISCOVERY.md) — [coding prompt](FEATURE_COURSE_DISCOVERY.md). Extends the existing published course catalogue and preserves paid-content restrictions.
- [Admin and sub-admin analytics](../FEATURE_SPEC_ADMIN_ANALYTICS.md) — [coding prompt](FEATURE_ADMIN_ANALYTICS.md). Uses real persisted data and strict ownership boundaries.
- [PWA offline and low-data mode](../FEATURE_SPEC_PWA_OFFLINE.md) — [coding prompt](FEATURE_PWA_OFFLINE.md). Supplements Milestone 9; private API data and protected media must not enter shared caches.
- [Study planner and reminders](../FEATURE_SPEC_STUDY_PLANNER.md) — [coding prompt](FEATURE_STUDY_PLANNER.md). Adds private user-owned tasks and best-effort browser reminders.
- [Community posts](../FEATURE_SPEC_COMMUNITY_POSTS.md) — [coding prompt](FEATURE_COMMUNITY_POSTS.md). Adds a published student feed and main-admin/sub-admin post authoring with server-enforced scope and ownership.

- [Production security, reliability, and operations](../FEATURE_SPEC_PRODUCTION_SECURITY_RELIABILITY.md) — [coding prompt](FEATURE_PRODUCTION_SECURITY_RELIABILITY.md). Covers RBAC, audit logs, rate limits, backup/restore drills, CI gates, monitoring, secure deployment, private-cache rules, paid-media delivery, export safety, accessibility, and performance. Integrate into Milestones 1, 3, 10, and 11; it does not replace them.

## Prompt sequence

| Order | Prompt | Goal |
|---|---|---|
| 1 | [Milestone 1 — Foundation verification](MILESTONE_01_FOUNDATION.md) | Diagnose CI, verify Django startup, dependencies, migrations, and tests |
| 2 | [Milestone 2 — Models and admin](MILESTONE_02_MODELS_ADMIN.md) | Durable learning models, course folders/resources, admin and code records |
| 3 | [Milestone 3 — Auth and authorization](MILESTONE_03_AUTH.md) | Student/staff roles, sub-admin ownership, course access and throttling |
| 4 | [Milestone 4 — Course and lesson API](MILESTONE_04_COURSE_LESSON_API.md) | Published catalog, folders/resources, code redemption, and access-checked APIs |
| 5 | [Milestone 5 — Quiz engine](MILESTONE_05_QUIZZES.md) | Server-side scoring, answer secrecy, attempts, explanations |
| 6 | [Milestone 6 — Notes and progress sync](MILESTONE_06_NOTES_PROGRESS.md) | Persistent per-user notes and learning progress |
| 7 | [Milestone 7 — Frontend API foundation](MILESTONE_07_FRONTEND_API.md) | Real API client, auth UX, error handling, responsive shell |
| 8 | [Milestone 8 — Learner experience](MILESTONE_08_LEARNING_EXPERIENCE.md) | End-to-end course, lesson, quiz, notes, dashboard, profile flows |
| 9 | [Milestone 9 — PWA and offline](MILESTONE_09_PWA_OFFLINE.md) | Safe cache policy, installability, offline and sync behavior |
| 10 | [Milestone 10 — Quality and security](MILESTONE_10_QUALITY_SECURITY.md) | CI, regression coverage, accessibility, performance, security |
| 11 | [Milestone 11 — Deployment](MILESTONE_11_DEPLOYMENT.md) | Reproducible deployment, migrations, secrets, health, rollback |
| 12 | [Milestone 12 — Final acceptance](MILESTONE_12_ACCEPTANCE.md) | Clean setup, full journey tests, evidence-backed release decision |

## Non-negotiable rules

- Work on the existing repository; preserve sound implementation and avoid needless rewrites.
- Make actual code changes for implementation milestones. Markdown-only changes do not satisfy implementation acceptance criteria.
- Run commands in the real checkout and include relevant output/exit status in the report. Never invent test results.
- Never commit credentials or paste secrets into logs.
- Treat every API input and user-generated string as untrusted.
- Private records must be scoped to the authenticated user at the queryset and object-permission level.
- Never reveal quiz answer keys before submission or trust a score supplied by the client.
- Never cache authenticated API responses, tokens, notes, private progress, planner data, active tests, answer keys, or protected media in a shared service-worker cache.
- Before claiming production readiness, verify RBAC, rate limits, audit-log redaction, backup restoration, CI gates, monitoring, deployment security, cache privacy, and export safety with actual evidence.
- Only use course materials and video URLs that the project is authorized to use.
- No payment processing, live streaming, chat, certificates, AI tutor, or recommendation engine until the core platform is accepted and the product owner prioritizes them.
- A deployed service may be called production-ready only after real target-environment smoke tests and security checks.

## Required end-of-run report

For every milestone, report: source files changed; implementation decisions; exact tests/checks run and results; failures and remaining risks; updated status/plan links; and the next milestone. Stop after the report.
- [Multi-account Cloudflare R2 storage](../FEATURE_SPEC_R2_STORAGE.md) — [coding prompt](FEATURE_R2_STORAGE.md). Mandatory sub-admin-owned storage connections across different Cloudflare accounts, used for Community post images and course thumbnails. Must preserve tenant isolation, protected credentials, private media delivery and object cleanup.
