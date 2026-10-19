# StudySpace Coding-Agent Prompt Pack

These files are **execution prompts for a coding agent**, not implementation deliverables. The agent must use them to modify and test application source code. Do not satisfy a prompt by merely writing more documentation.

## How to use

1. Open the repository in your coding agent with write access and terminal access.
2. Give the agent `docs/BUILD_MASTER_PROMPT.md` and this index.
3. Run **one milestone prompt per agent session**. Start at Milestone 1 because the initial repository audit is recorded already, but its verification remains pending.
4. The agent must inspect current files and git status before editing, implement actual source changes, run tests, update `docs/BUILD_STATUS.md` and `docs/IMPLEMENTATION_PLAN.md`, and stop at the end of that milestone.
5. If the current milestone fails its exit criteria, the agent must fix it or report the exact blocker. It must not skip ahead or mark it complete.

## Product feature specification

Read [Course management and code-based access](../FEATURE_SPEC_COURSES_AND_ACCESS_CODES.md) for the required admin/sub-admin roles, course folders, video/PDF resources, free/paid course rules, Telegram provider contact, and secure access-code redemption. The execution wrapper is [Course-management coding-agent prompt](FEATURE_COURSE_MANAGEMENT_ACCESS_CODES.md). These requirements are integrated into the relevant existing milestones; do not skip the milestone order.

## Test-series specification

Read [Test series, CSV question bank, timers, and results](../FEATURE_SPEC_TEST_SERIES.md) and follow [the test-series coding-agent prompt](FEATURE_TEST_SERIES.md). These requirements extend the existing quiz engine and must be implemented in the relevant milestones, without skipping the sequence.

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
- Never cache authenticated API responses, tokens, notes, or private progress in a shared service-worker cache.
- Only use course materials and video URLs that the project is authorized to use.
- No payment processing, live streaming, chat, certificates, AI tutor, or recommendation engine until the core platform is accepted and the product owner prioritizes them.
- A deployed service may be called production-ready only after real target-environment smoke tests and security checks.

## Required end-of-run report

For every milestone, report: source files changed; implementation decisions; exact tests/checks run and results; failures and remaining risks; updated status/plan links; and the next milestone. Stop after the report.
