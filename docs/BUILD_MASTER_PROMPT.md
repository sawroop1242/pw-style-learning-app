# StudySpace — Master Build Prompt for the Coding Agent

> **Purpose:** Turn this repository from a visual prototype into a complete, reliable, production-minded learning platform.  
> **Execution rule:** Build it incrementally, **one milestone at a time**. Do not attempt a giant rewrite or claim completion without tests.

## Split frontend/backend plans

Before implementing any feature, read the relevant plan:
- [Frontend implementation plan](FRONTEND_IMPLEMENTATION_PLAN.md) defines student/staff screens, API integration, responsive/accessibility requirements, PWA/offline safety, and frontend tests.
- [Backend implementation plan](BACKEND_IMPLEMENTATION_PLAN.md) defines authoritative models, endpoints, role/ownership checks, scoring/import behavior, operational controls, and backend tests.

Both documents describe the same StudySpace application from separate responsibilities. The ordered milestone sequence in [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md) remains authoritative. Keep the API contract consistent across frontend and backend, implement one milestone per run, and do not claim a feature is shipped based on documentation alone.

## 1. Your role

Act as the lead full-stack engineer responsible for auditing, implementing, testing, documenting, and hardening StudySpace. Work in the existing repository and preserve useful code. Do not merely write plans or documentation: implement working code and tests.

Before changing anything:
1. Inspect the entire repository tree, README, existing frontend, Django settings, models, serializers, views, routes, migrations, and deployment configuration.
2. Identify what is implemented, what is only a mock/prototype, bugs, security gaps, missing tests, and conflicting architecture.
3. Create or update `docs/IMPLEMENTATION_PLAN.md` and `docs/BUILD_STATUS.md` with evidence-based findings and a milestone checklist.
4. Do not overwrite working functionality without a reason. Keep changes focused and reviewable.

## 2. Product goal

Build **StudySpace**, a mobile-first, installable learning platform inspired by the general usability of modern Indian ed-tech apps. It is an independent product and must not copy proprietary PW branding, assets, course content, or bypass paid-course protections.

The finished product should support:
- Student registration with unique username, email, and password; login, logout, token refresh, profile management, authenticated password change, and forgot-password reset using email OTP sent through owner-configured Gmail SMTP or another supported SMTP provider. Follow `docs/FEATURE_SPEC_AUTHENTICATION.md`; never commit mail credentials.
- Course catalogue, subject/category filters, search, course details, lesson lists, and lesson completion.
- Video lesson links or authorized embeds, with graceful handling of unavailable or unsupported embeds. Never scrape or bypass DRM, authentication, paywalls, or access controls.
- Quizzes with questions, answer submission, server-validated scoring, explanations, attempt history, and score summaries.
- Student notes that persist to the authenticated user's account and sync across devices.
- Progress tracking and dashboard statistics calculated from backend data.
- Advanced test analytics based on persisted server-scored attempts, with student-only personal trends and role-scoped staff aggregates. Follow `docs/FEATURE_SPEC_ADVANCED_TEST_ANALYTICS.md`.
- Private notes, bookmarks, saved questions/resources, and revision lists integrated with existing notes/progress. Follow `docs/FEATURE_SPEC_NOTES_BOOKMARKS_REVISION.md`.
- Searchable/filterable course discovery using published catalogue data only. Follow `docs/FEATURE_SPEC_COURSE_DISCOVERY.md`.
- Main-admin and sub-admin dashboards for real course, access-code, progress, and test metrics with strict ownership scoping. Follow `docs/FEATURE_SPEC_ADMIN_ANALYTICS.md`.
- Safe offline PWA shell and low-data mode; private APIs, active tests, answer keys, tokens, notes, and protected media must not be stored in shared caches. Follow `docs/FEATURE_SPEC_PWA_OFFLINE.md`.
- Personal study planner, goals, task reminders, and daily/weekly views with privacy-safe, best-effort browser notifications. Follow `docs/FEATURE_SPEC_STUDY_PLANNER.md`.
- Responsive UI for small Android phones, tablets, and desktop browsers.
- Installable PWA, offline app shell, accessible controls, loading states, empty states, error states, and retry actions.
- Admin workflows for managing courses, lessons, quizzes, questions, choices, publication status, and content ordering.
- Automated tests, secure configuration, API documentation, and deployment instructions.
- Production security and reliability controls covering RBAC, audit logging, endpoint throttling, verified backups/restores, CI release gates, structured monitoring, secure deployment, cache privacy, protected-resource delivery, safe exports, accessibility, and performance. Follow `docs/FEATURE_SPEC_PRODUCTION_SECURITY_RELIABILITY.md`.

Do not represent demo/localStorage data as a real account-backed feature. Demo content may be used only as clearly labelled fallback content during development.

## 3. Required architecture

### Course management, provider contact, and access codes

Follow `docs/FEATURE_SPEC_COURSES_AND_ACCESS_CODES.md` as a required product specification. The main admin creates/deactivates sub-admins; sub-admins manage only their own courses. Courses support image URLs, free/paid pricing, provider Telegram contact, subject folders, video embed URLs, and chapter PDF download resources. Free courses require no code. Paid courses are unlocked only by server-validated, course-bound access codes generated by the main admin or authorized course owner. **Do not add a payment gateway or any other in-app payment option.** Protect paid PDF/video access server-side, use secure one-time-by-default code redemption with hashing, rate limits and concurrency protection, and test ownership boundaries. Integrate these requirements into the existing milestone sequence; do not skip ahead.

### Test series, question banks, CSV, and timers

Follow `docs/FEATURE_SPEC_TEST_SERIES.md` and `docs/agent-prompts/FEATURE_TEST_SERIES.md`. The main admin and authorized sub-admins must be able to create and manage owned test series, tests, sections, questions/options/correct answers, and CSV imports. Support timed, untimed, total-duration and section-duration modes; server-authoritative deadlines; autosave/resume; question navigation and mark-for-review; configured scoring/negative marking; attempt limits; randomized question/option order; result-release policies; and safe result review/analytics as defined by the spec. CSV imports must use a documented template and a CSV HTTPS URL hosted externally. The backend stores only the source URL and minimal import metadata—not the CSV file/blob or raw CSV contents—while imported questions/options/answers are stored as structured records. Fetch and parse in memory under strict size/row/time limits with SSRF-safe host, redirect, and IP validation; preview rows before confirmation and report errors safely. Never expose answer keys before release, trust client scores/timers, or allow question edits to change a historical attempt. Integrate with the existing quiz engine and implement one milestone per run.

### Advanced analytics, revision, discovery, and planning

Follow the feature specifications and matching prompts linked from `docs/agent-prompts/README.md`. Extend the existing course, notes/progress, and test models instead of creating parallel systems. Analytics must be derived from persisted server data, must obey result-release policies, and must enforce main-admin/sub-admin ownership. Notes, bookmarks, revision state, and planner tasks are private user-owned data. Course search may return published catalogue metadata only and must never reveal protected resources. Offline behavior must never cache authenticated API responses or protected media in shared Cache Storage. Browser notifications are opt-in and best-effort; do not promise guaranteed background delivery. Implement each part only in its authorized milestone and add real tests.

### Production security and reliability

Follow `docs/FEATURE_SPEC_PRODUCTION_SECURITY_RELIABILITY.md` and its coding-agent prompt. Integrate the controls into the existing milestones: foundation and configuration checks in Milestone 1, authorization and throttling in Milestone 3, regression/security/accessibility/performance tests in Milestone 10, and verified deployment/backup/monitoring procedures in Milestone 11. Do not treat a written checklist as evidence of implementation. Never claim backups are working without a restore drill, monitoring is active without a verified target setup, or production is ready without real environment smoke tests.

### Backend
Use the existing Django project and Django REST Framework unless the audit proves a concrete blocker. Prefer a clear modular app structure over a monolithic file. Keep the existing database models if sound; add migrations for every schema change.

Required backend capabilities:
- Django REST Framework API with consistent JSON responses and pagination where appropriate.
- JWT authentication using Simple JWT; authenticated ownership checks for notes, progress, quiz attempts, and profile data.
- Public read access only for published course/lesson/quiz content. Write operations must require authentication and ownership or staff permissions.
- Server-side quiz scoring. Never expose the correct-answer flag in the student-facing quiz payload before submission.
- Validation for URLs, IDs, request sizes, and allowed state transitions.
- Search/filter/order API parameters with documented limits.
- CORS configured by environment variables, not wildcard production defaults.
- Environment-based `SECRET_KEY`, `DEBUG`, `ALLOWED_HOSTS`, database URL, and trusted frontend origins. Fail safely when production secrets/configuration are missing.
- Production-ready static-file handling, health endpoint, structured logging, and database migrations.
- Use PostgreSQL in deployment; SQLite may remain the local development default.
- Never commit credentials, tokens, real student data, or secret environment files.

### Frontend
First inspect the existing vanilla HTML/CSS/JS frontend. Continue with it if it can meet requirements cleanly; do not migrate to a framework solely for fashion. If a framework migration is genuinely needed, document the trade-off and perform it as its own approved milestone.

Required UI behavior:
- Consistent purple/white design system with reusable styles and clear visual hierarchy.
- Mobile-first layout and touch-friendly targets; no horizontal overflow at 320 px viewport width.
- Proper navigation and route/view behavior for dashboard, catalogue, course detail, lesson/video, notes, quiz, profile, login, and registration.
- API client with centralized base URL, auth token handling, expiry/401 handling, loading, empty, offline, and error states.
- Use the Django API as the source of truth when configured. Do not silently hide API errors behind fake success states.
- Notes, progress, bookmarks, revision state, and planner tasks must use authenticated APIs and server-side ownership checks. Local storage may cache non-sensitive preferences and a carefully designed offline queue, but must not be treated as secure storage.
- Accessible labels, keyboard navigation, visible focus, semantic elements, and useful contrast.
- Safe rendering of user/course text; do not inject untrusted HTML.
- PWA manifest and service worker with versioned cache strategy. Do not cache authenticated API responses or private user data in a shared cache.

### API and frontend integration
- Keep the API base URL configurable for local, staging, and production deployments.
- Add automated tests for auth, permission boundaries, serializers, quiz scoring, course publication, notes ownership, and progress ownership.
- Add integration tests for frontend API behavior where practical.
- Provide an OpenAPI schema or browsable API documentation.
- Ensure API pagination is handled correctly by the frontend.
- Do not assume CORS is a substitute for authentication or authorization.

## 4. Milestones — implement strictly in order

Complete **only one milestone per agent run** unless the user explicitly asks for more. At the end of each run, stop, report the result, and wait for the next instruction. Never claim that later milestones are done.

### Milestone 0 — Repository audit and plan
- Inspect all existing code and Git history where useful.
- Run existing checks and record baseline failures.
- Identify prototype-only features and security issues.
- Add `docs/IMPLEMENTATION_PLAN.md` and `docs/BUILD_STATUS.md`.
- Make no unrelated refactors.
- Exit criteria: plan includes milestones, acceptance criteria, risks, dependencies, and exact test commands.

### Milestone 1 — Make the Django foundation reliable
- Verify installed dependencies and supported Python/Django versions.
- Fix settings, URL routing, app registration, migrations, health endpoint, and environment handling.
- Add lint/test configuration if absent.
- Add tests for basic API and database setup.
- Exit criteria: migrations apply on a clean database; Django system checks and initial tests pass.

### Milestone 2 — Data model and admin
- Audit and complete models for courses, lessons, quizzes, questions, choices, notes, progress, quiz attempts, and user profile as justified.
- Add model constraints, ordering, indexes, timestamps, and migrations.
- Configure useful Django admin search, filters, inlines, and publication workflows.
- Exit criteria: migrations and model/admin tests pass; admin content can be managed without manual database edits.

### Milestone 3 — Authentication and authorization
- Implement registration, login, refresh, logout/token invalidation strategy, and current-user profile.
- Enforce permissions and ownership on all private resources.
- Add rate limiting or throttling to authentication endpoints and secure password validation.
- Exit criteria: tests prove anonymous access is rejected for private data and users cannot read or modify another user's records.

### Milestone 4 — Course and lesson API
- Implement list/detail/search/filter endpoints for published courses and lessons.
- Add authorized video URL/embedding metadata, safe validation, duration, ordering, and lesson completion endpoints.
- Ensure draft/unpublished content is hidden from non-staff users.
- Exit criteria: API tests cover pagination, filters, publication rules, URL validation, and completion ownership.

### Milestone 5 — Quizzes and scoring
- Implement student quiz payloads that do not reveal correct answers.
- Implement server-side submission validation, scoring, explanations after submission, and attempt history.
- Prevent client-submitted scores or answer keys from being trusted.
- Exit criteria: tests cover correct/incorrect answers, malformed submissions, duplicate/invalid IDs, permissions, and answer-key secrecy.

### Milestone 6 — Notes and progress sync
- Implement CRUD for the authenticated user's notes and progress.
- Integrate private bookmarks and revision state using `docs/FEATURE_SPEC_NOTES_BOOKMARKS_REVISION.md`; reuse existing models and add ownership/duplicate-resource tests.
- Add robust validation, pagination, update semantics, and conflict behavior as appropriate.
- Exit criteria: data persists in the database and user-isolation tests pass.

### Milestone 7 — Frontend foundation and API client
- Build navigation/view structure, shared components/styles, API client, auth flow, and state handling.
- Replace fake success behavior and prototype-only state with real API integration.
- Add responsive layout, accessible interactions, and loading/empty/error/retry states.
- Exit criteria: frontend can register/login and display real API responses in a local end-to-end run.

### Milestone 8 — Complete learning experience
- Implement catalogue/search and filters according to `docs/FEATURE_SPEC_COURSE_DISCOVERY.md`, course detail, lesson playback/link handling, completion, quiz taking/results, notes/bookmarks/revision, progress dashboard, and profile.
- Add study planner and daily/weekly task views according to `docs/FEATURE_SPEC_STUDY_PLANNER.md` once the required account and resource APIs exist.
- Add student-facing test performance insights from `docs/FEATURE_SPEC_ADVANCED_TEST_ANALYTICS.md` only when persisted attempts and result-release behavior are available.
- Implement the authenticated Community feed and role-scoped post authoring per `docs/FEATURE_SPEC_COMMUNITY_POSTS.md` and `docs/agent-prompts/FEATURE_COMMUNITY_POSTS.md`. Main admins can manage global and course posts; sub-admins can manage only authorized course posts; students can read published posts in scope. Do not add comments/reactions/chat in v1.
- Make every visible control work or clearly label it as unavailable; remove dead buttons and misleading placeholders.
- Exit criteria: core learner journey works from login through course lesson, quiz, notes, and progress.

### Milestone 9 — PWA and offline behavior
- Validate manifest, app icons, install flow, service worker updates, offline shell, cache invalidation, and low-data mode per `docs/FEATURE_SPEC_PWA_OFFLINE.md`.
- Add only explicitly approved offline queues with documented conflict/idempotency behavior; never cache private API data or protected media.
- Cache only safe public static assets; do not cache private API payloads or tokens.
- Provide clear offline messages and safe retry/sync behavior.
- Exit criteria: installability and offline behavior are tested in supported browsers and documented.

### Milestone 10 — Quality, security, and performance
- Follow `docs/FEATURE_SPEC_PRODUCTION_SECURITY_RELIABILITY.md` for role/ownership regression coverage, endpoint throttling, audit-log redaction, CI release gates, private-cache inspection, safe exports, accessibility, and performance checks.
- Add/complete unit, API, integration, and end-to-end tests where practical.
- Verify privacy, permission scoping, metric correctness, export safety, planner timezone behavior, and offline cache rules for the new feature specifications.
- Run formatters, linters, Django checks, migration checks, dependency/security checks, and production settings checks.
- Fix accessibility issues, N+1 queries, avoidable frontend payloads, and mobile overflow.
- Exit criteria: all required CI checks pass, or remaining failures are explicitly documented with reproducible evidence.

### Milestone 11 — Deployment and operations
- Follow `docs/FEATURE_SPEC_PRODUCTION_SECURITY_RELIABILITY.md` for HTTPS/host/origin configuration, least-privilege secrets, health/monitoring behavior, backup retention and an actual isolated restore drill, and rollback verification. Report unconfigured controls as gaps; do not claim production readiness without evidence.
- Provide environment examples with placeholders only, backend deployment configuration, frontend hosting instructions, database migration instructions, health checks, logs, backup/restore notes, and rollback steps.
- Document any real notification infrastructure or analytics collection only if approved, configured, and tested; browser reminders alone are best-effort.
- Keep frontend hosting and Django API hosting clearly separate.
- Document HTTPS, allowed hosts, CORS origins, secrets, database persistence, and post-deployment smoke tests.
- Exit criteria: a fresh maintainer can deploy from documentation without guessing. Do not claim deployment until a real deployment is verified.

### Milestone 12 — Final acceptance
- Walk through all product acceptance criteria.
- Verify a clean setup from scratch and test with a normal student account plus a staff account.
- Update README and `docs/BUILD_STATUS.md` with completed milestones, commands run, results, known limitations, and deployment state.
- Exit criteria: evidence-based completion report; no unresolved critical security issues.

## 5. Engineering rules

1. **One milestone per run.** Begin by reading `docs/BUILD_STATUS.md` and the milestone's plan. Implement only the next incomplete milestone.
2. **Inspect before editing.** Do not guess the current file contents or overwrite changes without reading them.
3. **Small, coherent changes.** Prefer focused commits and avoid giant unrelated rewrites.
4. **Test every meaningful change.** Run the narrow tests first, then relevant broader checks. Never say tests passed unless you ran them and saw the result.
5. **Migrations are mandatory.** If models change, generate or author migrations and verify them against a clean database.
6. **No secrets.** Never print or commit secret values. Use environment variable names and redacted diagnostics.
7. **Security first.** Treat all input as untrusted; enforce authorization server-side; do not expose quiz answers, private notes, or other users' progress.
8. **No fake completion.** A button must work, be disabled with a reason, or be removed. No mock response should be presented as real persisted data.
9. **No unrelated scope.** Do not add payment processing, live classes, chat, certificates, recommendation AI, or mobile native apps until the core product is complete and the user explicitly prioritizes them.
10. **Keep documentation current.** Update build status and setup instructions in the same milestone as the relevant code.
11. **No deployment claims without proof.** Distinguish code committed, tests run, and service deployed.
12. **Keep content lawful.** Support user-owned or authorized course content and links only. Do not reproduce protected course materials or bypass access restrictions.

## 6. Definition of done for every milestone

At the end of each milestone:
- Code is implemented, not merely proposed.
- Relevant tests/checks were run and their exact results recorded.
- New migrations and configuration are included when needed.
- `docs/BUILD_STATUS.md` records what changed, what passed/failed, and the next milestone.
- No secrets or unrelated files were added.
- The agent gives a concise report containing:
  1. milestone completed;
  2. files changed;
  3. tests/checks actually run and results;
  4. known limitations or blockers;
  5. the next milestone to execute.
- Then **stop and wait**. Do not automatically begin the next milestone in the same run.

## 7. Prompt-pack execution

Detailed, copy-ready prompts for each stage are maintained in `docs/agent-prompts/README.md` and its milestone files. Before executing a milestone, read the matching prompt and treat its requirements and acceptance criteria as part of this master contract. The prompt pack is instructions for implementing the real application; do not treat adding Markdown files as implementation completion.

The initial repository audit and implementation plan already exist. Start with `docs/agent-prompts/MILESTONE_01_FOUNDATION.md` to verify and stabilize the existing foundation. The current status records that runtime verification is pending and CI runs failed before visible steps; investigate that with actual logs and commands. Do not skip to Milestone 2 until Milestone 1 exit criteria pass. Continue one milestone per agent run, in order, and stop after each report.
