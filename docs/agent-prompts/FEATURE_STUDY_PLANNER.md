# Coding-Agent Prompt — Study Planner and Reminders

Read `docs/FEATURE_SPEC_STUDY_PLANNER.md`, current authentication/profile/progress/course/test APIs, PWA behavior, and the currently authorized milestone prompt.

## Rules
- Preserve milestone order; Milestone 1 is verification only.
- Planner tasks, goals and preferences are private user data. Enforce ownership server-side.
- Do not add SMS, WhatsApp, email reminders, location collection, or third-party notification services without separate approval.
- Browser notifications require explicit permission and are best-effort; do not claim guaranteed background delivery.
- Reuse current models and API patterns where sound.

## Tasks when authorized
1. Audit existing task/planner support and define any schema changes.
2. Implement private task CRUD, validation, linked-resource access checks and timezone-aware dates in the proper backend milestone.
3. Implement daily/weekly views, goals and reminders in the appropriate learner/PWA milestones.
4. Handle denied notification permissions, duplicate reminders, quiet hours and offline states.
5. Add tests for ownership, time zones, recurrence if supported, resource access, notification degradation and UI states.
6. Update build status and implementation plan using actual test evidence.

## Report
List changed files, data/time-zone decisions, notification limitations, tests and exact results, and remaining work. Stop after the authorized milestone.
