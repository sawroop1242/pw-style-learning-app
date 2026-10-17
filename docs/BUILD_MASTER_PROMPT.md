# StudySpace — Master Build Prompt for the Coding Agent

> **Purpose:** Turn this repository from a visual prototype into a complete, reliable, production-minded learning platform.  
> **Execution rule:** Build it incrementally, **one milestone at a time**. Do not attempt a giant rewrite or claim completion without tests.

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
- Student registration, login, logout, token refresh, and profile management.
- Course catalogue, subject/category filters, search, course details, lesson lists, and lesson completion.
- Video lesson links or authorized embeds, with graceful handling of unavailable or unsupported embeds. Never scrape or bypass DRM, authentication, paywalls, or access controls.
- Quizzes with questions, answer submission, server-validated scoring, explanations, attempt history, and score summaries.
- Student notes that persist to the authenticated user's account and sync across devices.
- Progress tracking and dashboard statistics calculated from backend data.
- Responsive UI for small Android phones, tablets, and desktop browsers.
- Installable PWA, offline app shell, accessible controls, loading states, empty states, error states, and retry actions.
- Admin workflows for managing courses, lessons, quizzes, questions, choices, publication status, and content ordering.
- Automated tests, secure configuration, API documentation, and deployment instructions.

Do not represent demo/localStorage data as a real account-backed feature. Demo content may be used only as clearly labelled fallback content during development.

## 3. Required architecture

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
- Notes and progress must sync through authenticated API endpoints. Local storage may cache non-sensitive preferences and a carefully designed offline queue, but must not be treated as secure storage.
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
- Add robust validation, pagination, update semantics, and conflict behavior as appropriate.
- Exit criteria: data persists in the database and user-isolation tests pass.

### Milestone 7 — Frontend foundation and API client
- Build navigation/view structure, shared components/styles, API client, auth flow, and state handling.
- Replace fake success behavior and prototype-only state with real API integration.
- Add responsive layout, accessible interactions, and loading/empty/error/retry states.
- Exit criteria: frontend can register/login and display real API responses in a local end-to-end run.

### Milestone 8 — Complete learning experience
- Implement catalogue/search, course detail, lesson playback/link handling, completion, quiz taking/results, notes, progress dashboard, and profile.
- Make every visible control work or clearly label it as unavailable; remove dead buttons and misleading placeholders.
- Exit criteria: core learner journey works from login through course lesson, quiz, notes, and progress.

### Milestone 9 — PWA and offline behavior
- Validate manifest, app icons, install flow, service worker updates, offline shell, and cache invalidation.
- Cache only safe public static assets; do not cache private API payloads or tokens.
- Provide clear offline messages and safe retry/sync behavior.
- Exit criteria: installability and offline behavior are tested in supported browsers and documented.

### Milestone 10 — Quality, security, and performance
- Add/complete unit, API, integration, and end-to-end tests where practical.
- Run formatters, linters, Django checks, migration checks, dependency/security checks, and production settings checks.
- Fix accessibility issues, N+1 queries, avoidable frontend payloads, and mobile overflow.
- Exit criteria: all required CI checks pass, or remaining failures are explicitly documented with reproducible evidence.

### Milestone 11 — Deployment and operations
- Provide environment examples with placeholders only, backend deployment configuration, frontend hosting instructions, database migration instructions, health checks, logs, backup/restore notes, and rollback steps.
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

## 7. Start instruction

Start with **Milestone 0 only**. Inspect the actual repository, write the implementation plan and build status, and report evidence. Do not begin Milestone 1 until the user or orchestrator starts the next run.
