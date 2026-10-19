# StudySpace Implementation Plan

**Repository:** sawroop1242/pw-style-learning-app  
**Default branch:** main  
**Scope:** Turn the current mobile-first HTML/CSS/JavaScript PWA prototype and Django starter into a tested learning platform, delivered in small, reviewable milestones.

## Coding-agent prompts

Detailed execution prompts are maintained in [`docs/agent-prompts/README.md`](agent-prompts/README.md). Use exactly one milestone prompt per agent run. The prompts define implementation tasks, tests, security requirements, acceptance criteria, and stop conditions; they are not substitutes for working code.

## Product requirements addendum

The course-management and access-code requirements are specified in [`docs/FEATURE_SPEC_COURSES_AND_ACCESS_CODES.md`](FEATURE_SPEC_COURSES_AND_ACCESS_CODES.md) and the execution wrapper is [`docs/agent-prompts/FEATURE_COURSE_MANAGEMENT_ACCESS_CODES.md`](agent-prompts/FEATURE_COURSE_MANAGEMENT_ACCESS_CODES.md). Apply the relevant subset during Milestones 2, 3, 4, and 8. The payment policy is code-only: no checkout or payment gateway. A public external PDF URL cannot be access-controlled; paid resources must use a protected delivery path or be explicitly documented as public.

## Additional product feature specifications

The following are required product extensions, integrated into the existing milestones rather than separate parallel implementations:

- [Advanced test analytics](FEATURE_SPEC_ADVANCED_TEST_ANALYTICS.md) extends the test series spec with personal trends, staff aggregates, documented formulas, release-policy enforcement and export safety.
- [Notes, bookmarks and revision](FEATURE_SPEC_NOTES_BOOKMARKS_REVISION.md) extends the existing notes/progress system with private saved resources and revision states.
- [Course discovery](FEATURE_SPEC_COURSE_DISCOVERY.md) extends the published course catalogue with bounded search, filters and sorting without leaking protected resources.
- [Admin analytics](FEATURE_SPEC_ADMIN_ANALYTICS.md) provides main-admin platform aggregates and sub-admin owner-scoped metrics based only on persisted data.
- [PWA offline and low-data mode](FEATURE_SPEC_PWA_OFFLINE.md) supplements Milestone 9 with a resource-class cache policy, safe offline states and no shared caching of private data.
- [Study planner and reminders](FEATURE_SPEC_STUDY_PLANNER.md) adds private tasks/goals and opt-in best-effort browser reminders.

Matching coding-agent prompts are indexed in [docs/agent-prompts/README.md](agent-prompts/README.md). The requested product features remain specifications until implemented and verified through the existing milestone sequence.

Production hardening is specified in [FEATURE_SPEC_PRODUCTION_SECURITY_RELIABILITY.md](FEATURE_SPEC_PRODUCTION_SECURITY_RELIABILITY.md), with its [coding-agent prompt](agent-prompts/FEATURE_PRODUCTION_SECURITY_RELIABILITY.md). It covers RBAC, audit logs, rate limits, backup/restore drills, CI gates, monitoring, secure deployment, cache privacy, protected media, export safety, accessibility, and performance. Integrate it with Milestones 1, 3, 10, and 11 rather than creating a parallel implementation track.

## Working rules

1. Complete exactly one milestone per agent run. After reporting evidence and updating docs/BUILD_STATUS.md, stop.
2. Inspect the live code before each milestone. Preserve useful code; do not rewrite the frontend framework without a documented technical reason.
3. Implement code and tests, not documentation alone, for implementation milestones.
4. Never claim a test, deployment, or production readiness unless supported by an actual command result or observable deployment.
5. Do not include paid/proprietary course content or bypass access controls. Store only video URLs the project is authorized to use.
6. Keep secrets out of source control. Use environment configuration and safe defaults.
7. Do not cache authenticated/private API responses in the service worker.
8. Treat security and operations checklist items as unverified until supported by actual test, restore, browser, or deployment evidence.

## Initial audit — observed state

The repository contains a small vanilla frontend (frontend/index.html, styles.css, app.js), a service worker and manifest, plus a Django REST Framework backend with models, serializers, viewsets, admin registration, URL routing and one initial migration. The master prompt is at docs/BUILD_MASTER_PROMPT.md.

Confirmed gaps from source inspection:

- The frontend sets API_BASE to an empty string, so it falls back to local demo courses and does not connect to the Django API by default.
- Notes and completion state are stored in browser localStorage; the UI does not use the existing notes/progress API for normal reads or writes.
- The frontend has no complete account/login flow, quiz-taking/scoring flow, or full lesson-learning page.
- Quiz endpoints are read-only; no server-side submission/scoring endpoint is present. The question serializer currently includes the explanation in the quiz response.
- The service worker caches every successful GET response, not just static assets. It can therefore cache API or other private responses and returns the app shell as a fallback for arbitrary failed GET requests.
- Django uses a development fallback secret and defaults DEBUG to true. Production-safe startup behavior and deployment security checks need verification and hardening.
- The REST framework's global default permission is AllowAny; sensitive viewsets add authentication and user-filtered querysets, but endpoint-by-endpoint authorization and ownership need regression tests.
- No automated test module, CI workflow, or established frontend test/lint setup was found in the inspected repository tree.
- README feature descriptions are broader than the currently connected end-user experience; documentation should distinguish implemented, partially implemented, and planned features.

These are audit findings, not claims that the backend has been executed or runtime-verified.

## Milestones and acceptance criteria

### Milestone 0 — Repository audit and plan
- [x] Inspect repository tree and primary frontend/backend files.
- [x] Record observed implementation gaps and risks.
- [x] Create this plan with acceptance criteria, dependencies, risks and exact baseline commands.
- [ ] Execute baseline checks in a real checkout and record exact output/status.
- [ ] Confirm migration consistency and characterize current API behavior with runtime evidence.

**Exit criteria:** Evidence-based inventory; commands and acceptance criteria documented; baseline commands executed or an explicit execution blocker recorded. No implementation work from Milestone 1 begins in this milestone.

### Milestone 1 — Reliable Django foundation
- [x] Harden environment configuration and production secret/host/debug checks (runtime verification pending).
- [x] Add a minimal GET-only liveness endpoint and foundation endpoint tests (runtime verification pending).
- [x] Add WhiteNoise as an explicit dependency and document production environment variables.
- [ ] Confirm supported Python/Django versions and install dependencies in a clean environment.
- Make configuration environment-driven; ensure production cannot silently start with the development secret or DEBUG=True.
- Verify URL configuration, database settings, static-file handling, health/readiness behavior and startup checks.
- Add foundation tests and document local setup.
- **Acceptance:** clean dependency install; Django system check passes; migration consistency passes; startup configuration failures are clear and safe; tests pass.

### Milestone 2 — Data model and Django admin
- Review Course, Lesson, Quiz, Question, Choice, Note and Progress models, constraints, ordering, indexes and migration history.
- Add only justified fields/constraints with reversible migrations.
- Ensure admin supports efficient and understandable content maintenance.
- **Acceptance:** fresh database migrates; model constraints behave as intended; admin registrations and key workflows are covered by tests.

### Milestone 3 — Authentication and authorization
- Follow [`docs/FEATURE_SPEC_AUTHENTICATION.md`](FEATURE_SPEC_AUTHENTICATION.md) and [`docs/agent-prompts/FEATURE_AUTHENTICATION.md`](agent-prompts/FEATURE_AUTHENTICATION.md).
- Require unique normalized username, unique normalized email, and password on registration; use Django password hashing and validators.
- Implement documented login/token refresh/logout behavior, authenticated password change, and forgot-password OTP sent to the registered email through environment-configured Gmail SMTP or another supported SMTP provider.
- OTPs must be short-lived, single-use, securely hashed, rate-limited, purpose-bound, and consumed atomically; forgot-password responses must not reveal whether an account exists.
- Enforce authenticated access for private user data and ownership on every list/detail/create/update/delete path. Keep SMTP credentials in deployment secrets, never source control.
- **Acceptance:** registration uniqueness and password validation, OTP expiry/replay/concurrency/rate-limit, mocked email delivery/failure, token behavior, anonymous/private-access, and cross-user isolation tests pass; no user can read or modify another user's private records.

### Milestone 4 — Course and lesson API
- Define stable response shapes, published-content filtering, ordering, pagination and course/lesson relationships.
- Validate video URLs and prevent unpublished content leaking through nested or detail routes.
- Add API tests for normal, empty, invalid and permission-sensitive cases.
- **Acceptance:** documented endpoints return predictable responses; published/unpublished visibility and filtering are tested; query behavior suits the expected catalog.

### Milestone 5 — Quizzes, test series, CSV import, scoring and analytics

Read [`docs/FEATURE_SPEC_TEST_SERIES.md`](FEATURE_SPEC_TEST_SERIES.md) and [`docs/agent-prompts/FEATURE_TEST_SERIES.md`](agent-prompts/FEATURE_TEST_SERIES.md). For advanced reporting, also follow [`docs/FEATURE_SPEC_ADVANCED_TEST_ANALYTICS.md`](FEATURE_SPEC_ADVANCED_TEST_ANALYTICS.md) and its linked coding prompt. Extend the current quiz engine into test series with sections, CSV URL-based question import, configurable timed/untimed modes, per-section timing, immutable attempt snapshots, autosave/resume, scoring policy, retakes, result release, and staff/student result views. CSV source files stay in external storage: persist only the URL and minimal import metadata, never the CSV blob/raw body; store imported questions as structured records. The importer must mitigate SSRF and enforce host/redirect/IP, size, row-count, and timeout limits.
- Implement an authenticated or explicitly specified quiz-attempt/submission contract and server-side scoring.
- Never accept client-provided correct answers or scores as authoritative.
- Return questions and choices without answer keys before submission; return score and explanations according to the defined attempt flow.
- Decide attempt history and retake behavior and test it.
- Add documented student performance trends and role-scoped staff test analytics only from persisted, server-scored attempts; never leak unreleased results or other students' private data.
- **Acceptance:** correct/incorrect scoring, malformed submissions, duplicate choices, missing answers, unpublished quizzes, answer-key exposure, analytics formulas, result-release restrictions, and cross-user/staff-scope boundaries are covered by tests.

### Milestone 6 — Notes, progress, bookmarks and revision
- Connect notes and lesson progress to authenticated endpoints; preserve user isolation.
- Extend the existing notes/progress system with private bookmarks and revision lists per [`docs/FEATURE_SPEC_NOTES_BOOKMARKS_REVISION.md`](FEATURE_SPEC_NOTES_BOOKMARKS_REVISION.md); do not create a parallel notes store.
- Make create/update/delete behavior, validation and duplicate progress updates predictable.
- Handle offline/failed requests without falsely reporting that server sync succeeded.
- **Acceptance:** user data persists in the database across sessions/devices; network errors are visible and recoverable; notes/bookmarks/revision ownership, uniqueness and resource-availability tests pass.

### Milestone 7 — Frontend foundation and API client
- Keep the vanilla frontend unless audit evidence justifies another approach.
- Add one API client for base URL, JSON parsing, errors, pagination and auth token handling.
- Add loading, empty, error and signed-out states; avoid leaking tokens or rendering untrusted HTML.
- **Acceptance:** frontend works with configured API base URL; API errors are surfaced; no demo fallback is presented as live server data.

### Milestone 8 — Complete learning experience, discovery and planner
- Implement functional sign-up/sign-in, searchable/filtered course discovery per [`docs/FEATURE_SPEC_COURSE_DISCOVERY.md`](FEATURE_SPEC_COURSE_DISCOVERY.md), course and lesson navigation, lesson playback/link opening, quiz attempt/results, notes/bookmarks/revision and synced progress.
- Add personal study tasks, daily/weekly planner views and opt-in browser reminders per [`docs/FEATURE_SPEC_STUDY_PLANNER.md`](FEATURE_SPEC_STUDY_PLANNER.md), after required APIs exist.
- Add student test-performance insights only from real persisted attempts and only when result policy allows.
- Ensure every visible control has a real action and mobile layouts remain usable.
- Use accessible labels, keyboard navigation, appropriate status messages and responsive states.
- **Acceptance:** core learner journeys pass a documented manual checklist on a narrow mobile viewport and desktop viewport; no primary action is inert.

### Milestone 9 — PWA, offline behavior and low-data mode
- Scope precaching to versioned static assets only; exclude authenticated/API responses and sensitive data from Cache Storage.
- Define offline behavior explicitly, including stale-shell behavior, cache upgrades, API failures and low-data mode per [`docs/FEATURE_SPEC_PWA_OFFLINE.md`](FEATURE_SPEC_PWA_OFFLINE.md).
- Do not cache authenticated API responses, tokens, private notes/progress/planner data, active tests, answer keys or protected media in shared caches. Queue updates only where retry/conflict behavior is documented.
- Validate manifest, installation and service-worker update behavior.
- **Acceptance:** installability checks pass where supported; static shell works offline; private responses are not cached; service-worker upgrades remove obsolete app caches without deleting unrelated caches.

### Milestone 10 — Quality, security, analytics and performance
- Add automated backend tests and practical frontend checks; add CI for repeatable checks.
- Review CORS, hosts, HTTPS/cookie/security headers, secret handling, throttling, API serialization/query behavior and dependency updates.
- Follow [FEATURE_SPEC_PRODUCTION_SECURITY_RELIABILITY.md](FEATURE_SPEC_PRODUCTION_SECURITY_RELIABILITY.md): test RBAC boundaries, rate limits, audit-log redaction, CI gates, private-cache behavior, safe exports, accessibility, and representative performance.
- Verify analytics formulas and staff scopes, spreadsheet-safe exports, private planner/notes/bookmark ownership, timezone handling, and offline cache privacy.
- Check accessibility, safe DOM rendering, error handling, responsive behavior and service-worker privacy.
- **Acceptance:** CI checks pass; high-risk security findings are resolved or documented with mitigation; performance and accessibility checks are recorded.

### Milestone 11 — Deployment and operations
- Provide reproducible deployment configuration for Django, static assets, database migrations and static files.
- Document environment variables, database backup/migration procedure, logs, health checks and rollback.
- Verify HTTPS and security headers in the target environment; test a real isolated backup restore; verify monitoring/health behavior and document any controls not configured. Follow [FEATURE_SPEC_PRODUCTION_SECURITY_RELIABILITY.md](FEATURE_SPEC_PRODUCTION_SECURITY_RELIABILITY.md).
- Verify deployment only against an actual host and observed successful smoke tests.
- **Acceptance:** clean deployment and migrations succeed in the target environment; HTTPS, allowed hosts, database persistence and API/frontend connectivity are verified; no secrets are committed.

### Milestone 12 — Final acceptance
- Run the full test suite and all configured static checks from a clean checkout.
- Walk through learner journeys, authorization boundaries, quiz scoring, offline behavior and mobile responsiveness.
- Reconcile README, implementation plan and build status with what is actually shipped.
- **Acceptance:** evidence-backed release report, known limitations listed, no unresolved critical security issue, and no unsupported claim of production readiness.

## Test and verification commands

Run from the repository root in a clean Python environment with dependencies installed:

    cd backend
    python -m pip install -r requirements.txt
    python manage.py check
    python manage.py makemigrations --check --dry-run
    python manage.py test
    python -m compileall -q config courses
    cd ..
    node --check frontend/app.js

For later milestones, add tests specific to the changed behavior and run the complete suite. Where a command needs a real database, browser, secret, or deployed service, record the exact environment and result. Do not infer success from a file existing.

## Main risks and mitigations

| Risk | Mitigation |
|---|---|
| Private learner data leaks through API permissions or caches | Add ownership regression tests; keep API responses out of service-worker caches |
| Insecure production settings inherited from development defaults | Fail safely when production environment variables are missing; add deployment checks |
| Quiz answers exposed before submission or scores trusted from the client | Keep answer keys server-side; calculate scores on the backend |
| Analytics reveal unreleased results or cross-owner student data | Derive reports from server records; enforce role scopes in querysets and test result-release boundaries |
| Offline cache leaks private data or stale access decisions | Cache only approved public assets; test logout, account switch, and protected-resource changes |
| Planner reminders are presented as guaranteed | Use opt-in browser notifications and clearly document best-effort delivery and timezone behavior |
| Frontend appears functional while using local demo data | Clearly signal demo/offline states; wire real API flows and test them |
| Scope expands into a large rewrite | One milestone per run, focused changes, explicit acceptance criteria |
| Deployment is described as complete without evidence | Require host-specific smoke-test outputs and verified configuration |

## Dependencies and sequencing

The order is intentional: secure and test the Django foundation before widening the API; establish auth and data ownership before syncing user data; build the frontend client before full learning journeys; review service-worker behavior after API integration; deploy only after automated and manual acceptance checks pass.
