# Backend Implementation Plan — StudySpace API

**Repository:** `sawroop1242/pw-style-learning-app`  
**Backend location:** `backend/`  
**Framework:** Existing Django / Django REST Framework starter (verify exact installed versions during Milestone 1)  
**Status:** Planning only. This document does not claim that the listed endpoints, models, or protections are implemented.

## 1. Purpose and implementation contract

Build the authoritative API and persistence layer for the StudySpace PWA. Inspect the existing Django apps, models, serializers, viewsets, URLs, settings, migrations and tests before changing them. Preserve useful code and use reversible migrations. The frontend plan is [FRONTEND_IMPLEMENTATION_PLAN.md](FRONTEND_IMPLEMENTATION_PLAN.md).

Follow [BUILD_MASTER_PROMPT.md](BUILD_MASTER_PROMPT.md), [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md), all linked feature specs and the ordered milestone prompts. Implement only one milestone per agent run, beginning with Milestone 1 foundation verification. Documentation alone does not complete an implementation milestone.

## 2. Backend responsibility and API rules

The backend is the source of truth for:
- identity, credentials, roles and authorization;
- course publication, ownership, course folders, lessons and resources;
- access-code generation/redemption and access grants;
- quiz/test configuration, attempt state, answer validation, scoring and result release;
- notes, progress, bookmarks, revision state and study planner tasks;
- student/staff analytics, safe exports and audit events;
- server-side validation, throttling, privacy boundaries and operational health.

Every endpoint must have an explicit authentication and permission policy. Never rely on the frontend, CORS, hidden buttons, client-side role state, or submitted scores to enforce security.

## 3. Domain model inventory

Audit the existing schema first; reuse existing models when appropriate and avoid parallel systems.

### Identity and roles
- User/account with normalized unique username and email and secure password hashing/validation.
- Role/permission model or equivalent documented Django groups/permissions for student, sub-admin and main-admin.
- Ownership/assignment relationships that scope sub-admin access to their own/assigned courses and permitted learners.
- Password reset OTP records with purpose, expiry, attempt/usage state and safe storage; never store OTPs as plaintext.
- Session/token lifecycle and invalidation strategy consistent with the selected authentication mechanism.

### Learning catalogue and content
- Course: title, description, publication state, owner/assigned staff, access policy, timestamps and justified catalogue metadata.
- Course folder/section and ordered hierarchy where required.
- Lesson and resource records: resource type, authorized external URL or protected delivery reference, ordering, duration/metadata, publication state.
- Access code and redemption/grant records: secure code representation, expiry/usage/limits, course scope, revocation and audit fields as appropriate. Never store plaintext secrets unnecessarily.
- Do not treat public external URLs as protected content. Paid resources require authorized backend delivery or explicit disclosure that a link is public.

### Tests and assessment
- Test series/test, sections, question bank, questions and choices/options.
- Attempt with immutable question/choice snapshot or equivalent strategy so edits to the source bank do not silently rewrite historical attempts.
- Submitted answers, scoring details, attempt status, timing metadata, release policy and explanation visibility.
- Import-job metadata containing only the external CSV URL and minimal operational metadata; never persist the CSV blob or raw body. Persist successfully imported questions/options as structured records.
- Analytics may be computed from persisted server-scored attempts; do not store unvalidated client-derived totals as authoritative.

### Community posts
- Community post with title, safely rendered body, author, timestamps, publication state, optional pinning, and global or course scope.
- Main-admin global moderation; sub-admin ownership/assigned-course scope; student read-only visibility filtering.
- Use the existing user, course, permission, audit and API infrastructure. Do not create a parallel role system.

### Personal learning data
- Notes associated with the authenticated user and optionally a lesson/resource.
- Progress/completion records unique to user and resource as appropriate.
- Bookmarks and revision status/list, integrated with existing notes/progress rather than duplicating the same concept.
- Study planner tasks/goals with user ownership, due dates/timezone semantics, completion and timestamps.
- Audit log events with actor, action, target reference, timestamp, outcome and redacted metadata.

Add database constraints, indexes, ordering and deletion behavior where justified. Include migrations and tests for any schema changes.

## 4. API capability map

Exact route names and response envelopes must be reconciled with the existing code before implementation. Publish an OpenAPI schema or browsable API documentation when practical.

| API area | Required capability |
|---|---|
| Health/readiness | Minimal liveness endpoint; readiness should check only required dependencies and avoid exposing secrets/internal diagnostics |
| Authentication | Register, login, logout/token invalidation, refresh if used, current user/profile, password change, forgot-password OTP request/verify/reset |
| Course catalogue | Published courses only, pagination, bounded search/filter/sort, safe detail and nested lesson/resource visibility |
| Course administration | Main-admin global authority; sub-admin create/update only within ownership/assignment scope; publish/unpublish and safe resource ordering |
| Access codes | Staff-authorized creation/management/revocation; student redemption with expiry, usage limits, course scope and replay-safe semantics |
| Lessons/resources | Authorized list/detail/opening metadata, completion updates, and no unpublished/protected resource leakage |
| Test series | Published test list/detail, instructions, sections, allowed attempt start/resume, answer save, submit, result/explanation according to release policy |
| CSV import | Accept approved external CSV URL, enforce safe fetch limits and validate headers/rows, return sanitized import status and counts |
| Notes | Authenticated CRUD scoped to current user; validation and pagination |
| Progress | Authenticated read/update scoped to current user; idempotent completion semantics |
| Bookmarks/revision | Authenticated create/list/update/delete; uniqueness and ownership; unavailable resource handling |
| Study planner | Private task/goal CRUD, due dates, timezone policy, completion and bounded pagination |
| Community | Paginated visible-post feed/detail; staff create/update/draft/publish/pin/delete with role and course-ownership checks |
| Student analytics | Only the user's persisted attempts and released results; documented metrics and formulas |
| Staff/admin analytics | Main-admin platform aggregates; sub-admin aggregates strictly limited to assigned/owned scope |
| Exports | Explicit permission and bounded exports, privacy-safe fields, spreadsheet formula-injection mitigation |
| Audit/operations | Redacted security-relevant events, liveness/readiness, structured logs and correlation IDs; no secret-bearing diagnostics |

## 5. Authentication and authorization

Follow [FEATURE_SPEC_AUTHENTICATION.md](FEATURE_SPEC_AUTHENTICATION.md) and [FEATURE_AUTHENTICATION.md](agent-prompts/FEATURE_AUTHENTICATION.md).

- Normalize and enforce unique usernames/emails consistently at validation and database levels.
- Use Django's password hashing and appropriate password validators; never log or return credentials.
- Implement login/session or token lifecycle consistently, including logout/revocation semantics and frontend integration contract.
- Password change requires the current password.
- Forgot-password responses must not reveal whether an email/account exists.
- Email OTP defaults/specification: six digits, short expiry (default ten minutes), single use, purpose-bound, securely hashed/HMAC stored, attempt/rate limited, invalidated after success and atomically consumed to prevent replay/concurrent reuse.
- Send OTP using configurable SMTP environment settings (Gmail SMTP or another supported provider). Use an app password where Gmail requires it. Never commit SMTP credentials or use a normal account password as an app password.
- Apply throttling to login, registration, OTP request/verify, redemption, test submission and costly exports/imports.
- Every private queryset must be scoped to the authenticated user or authorized staff scope; object-level checks must also protect detail/update/delete paths.
- Main-admin and sub-admin permissions must be tested at endpoint and object level. Do not grant global access to sub-admins by accident.
- Add regression tests for anonymous access, cross-user reads/writes, role escalation, owner changes, direct object IDs and export endpoints.

## 6. Test engine, scoring and CSV import

Follow [FEATURE_SPEC_TEST_SERIES.md](FEATURE_SPEC_TEST_SERIES.md), [FEATURE_TEST_SERIES.md](agent-prompts/FEATURE_TEST_SERIES.md), and [FEATURE_SPEC_ADVANCED_TEST_ANALYTICS.md](FEATURE_SPEC_ADVANCED_TEST_ANALYTICS.md).

- Define explicit test configuration: sections, ordering, timing, scoring/negative marking if supported, attempt limits, retake rules and result-release policy.
- Server owns attempt state and scores. Reject unknown question/choice IDs, duplicate/conflicting answers, malformed payloads, invalid transitions and submissions for unavailable tests.
- Never send correct answer keys in a pre-submission student payload. Return explanations/answers only after submission and only when policy allows.
- Use immutable attempt snapshots or a documented versioning approach to preserve historical accuracy.
- Enforce idempotent submission/retry behavior and concurrency-safe attempt finalization.
- Document timing semantics. Client timers are display aids; server validates start/deadline/submit rules.
- Analytics formulas, cohort inclusion, timezone boundaries, release rules and staff visibility must be explicit and tested.

### External CSV URL importer
- Store only the source URL and minimal import metadata (status, timestamps, sanitized counts/errors, initiating actor); do not save the downloaded CSV bytes/raw body or file blob.
- Fetch in memory with strict connect/read/total timeout, response-byte cap, row/column cap, and accepted content/encoding rules.
- Mitigate SSRF: HTTPS/approved host policy where feasible; validate every redirect; resolve and reject loopback, private, link-local, multicast and reserved IPs; defend against DNS rebinding; reject unsupported schemes/ports; do not forward credentials/cookies; restrict egress if deployment supports it.
- Validate headers, required fields, option/answer references and row-level content; reject or report malformed imports safely.
- Persist imported questions/options as structured database records in a transaction or a clearly documented partial-import strategy.
- Prevent import URLs, CSV cells and exception details from becoming executable HTML or leaking secrets in logs.
- Test oversized responses, redirects to private IPs, DNS/IP changes where testable, malformed rows, timeouts, encoding problems and repeated import behavior.

## 7. Notes, progress, discovery, planner and analytics

- Course discovery: enforce published visibility in querysets; bounded filters, search length, sort allowlist, pagination and query-cost controls.
- Notes/bookmarks/revision: all records are private by default; enforce owner scope for every operation; handle duplicate bookmarks and deleted/unpublished resources predictably.
- Progress: persist updates server-side and make repeated completion requests safe; do not accept another user's IDs without ownership checks.
- Planner: task/goal CRUD is user-scoped; define timezone handling and recurring task behavior only if explicitly supported; browser notifications are client-side best effort, not a guaranteed server notification service.
- Student analytics: calculate from persisted attempts; respect attempt validity and result-release rules.
- Admin analytics: main admin sees authorized global aggregates; sub-admin sees only owned/assigned data. Document each formula and date boundary.
- Exports: permission-check before query, limit row count, select approved fields, redact private data, neutralize spreadsheet formulas (cells beginning with formula-triggering characters), and test cross-scope isolation.

## 8. Security, reliability and operations

Follow [FEATURE_SPEC_PRODUCTION_SECURITY_RELIABILITY.md](FEATURE_SPEC_PRODUCTION_SECURITY_RELIABILITY.md).

- Fail safely in production if secret key, DEBUG, allowed hosts, database or other required settings are invalid/missing.
- Configure HTTPS/proxy behavior, trusted origins, secure cookies/headers, CORS allowlist and CSRF policy appropriate to the actual auth model and deployment.
- Use environment variables/deployment secrets; commit only placeholder environment examples.
- Add request bounds, rate limits, database constraints, transactional writes and idempotency for sensitive state changes.
- Structured logs and correlation IDs must redact tokens, passwords, OTPs, authorization headers, private note contents and other sensitive payloads.
- Audit security-relevant events without recording secrets or excessive personal data.
- Health/readiness endpoints must not leak configuration, database credentials, environment dumps or stack traces.
- Add CI gates for tests, migrations, static checks and dependency/security checks appropriate to the repository.
- Document backup schedule, retention, encryption, recovery-point/recovery-time objectives and perform an actual isolated restore drill before claiming backup readiness.
- Define migration and rollback procedures; do not imply a database rollback is always safe after data-changing migrations.
- Use least-privilege CI/deployment credentials and prevent secrets in logs/artifacts.
- Verify actual deployed configuration, monitoring and smoke tests before claiming production readiness.

## 9. Testing strategy

- Model/constraint/migration tests: uniqueness, indexes where practical, ordering, deletion semantics and fresh database setup.
- API tests: status codes, schema/validation, pagination, anonymous and authenticated behavior, role scopes, object ownership and cross-user isolation.
- Authentication tests: registration uniqueness, password validation, OTP expiry/replay/concurrency/rate limits, email success/failure, reset invalidation and logout/token behavior.
- Course/access tests: publication visibility, ownership, access-code scope/expiry/limits/revocation and direct-resource URL restrictions.
- Test engine: scoring, invalid answers, no pre-submit answer leakage, attempt snapshots, timing/retake rules, result release and concurrency.
- Importer: SSRF, redirect, private IP, size/row/time bounds, malformed CSV and sanitized diagnostics.
- Personal data: notes/progress/bookmark/planner isolation and idempotent updates.
- Analytics/export: formulas, scope boundaries, released-result policy and spreadsheet formula injection.
- Operational tests: production settings fail-safe, health/readiness, logging redaction and backup restore evidence.
- Run commands in a real checkout and record exact output/status. Do not claim a test passed because code or a test file exists.

## 10. Ordered backend delivery

1. **Milestone 1 — Foundation verification:** verify dependencies, Django checks, migrations, tests, settings and CI. Record blockers before advancing.
2. **Milestone 2 — Data models/admin:** finalize model design and admin workflows for content, access, tests and private learner data.
3. **Milestone 3 — Auth/authorization:** implement account lifecycle, email OTP, roles, ownership, throttling and regression tests.
4. **Milestone 4 — Course/lesson API:** published catalogue, content hierarchy, resource access and code redemption.
5. **Milestone 5 — Tests/CSV/scoring/analytics:** server-scored attempts, CSV URL import, release policy, history and analytics.
6. **Milestone 6 — Notes/progress/bookmarks/revision:** private synced data and reliable update semantics.
7. **Milestone 7 — API contract for frontend:** document and stabilize endpoint shapes, pagination, errors and auth expiry behavior while implementing the frontend API foundation.
8. **Milestone 8 — Planner and feature APIs:** complete planner, discovery, and analytics APIs when prerequisites are ready.
9. **Milestone 9 — PWA support:** provide explicit cacheability/security headers and offline-safe API behavior; frontend owns service-worker implementation.
10. **Milestone 10 — Quality/security:** regression suite, throttling, audit redaction, exports, CI, accessibility/performance support and query efficiency.
11. **Milestone 11 — Deployment/operations:** migrations, persistent database, secrets, HTTPS, health checks, logs, backup/restore and rollback.
12. **Milestone 12 — Final acceptance:** clean-checkout full test suite and evidence-backed release review.

The shared milestone sequence in [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md) takes precedence if there is any sequencing conflict. Frontend and backend work can be developed in parallel only when API contracts are agreed, but milestone exit criteria must not be bypassed.

## 11. Backend definition of done

A backend feature is done only when:
- models, serializers, views/routes and permission rules are implemented as required;
- migrations apply on a clean database and migration consistency checks pass;
- relevant automated tests actually run and results are recorded;
- API documentation matches real responses and errors;
- unauthorized, cross-user, role-scope and invalid-input paths are tested;
- logs and diagnostics do not expose secrets/private data;
- `docs/BUILD_STATUS.md` records evidence, failures and the next milestone.

**Current status:** Plan authored; no backend source code, tests, database, or deployment are changed or verified by this document.
## 10. Mandatory multi-account Cloudflare R2 storage

The sub-admin panel must support each sub-admin connecting multiple Cloudflare R2 buckets across multiple Cloudflare accounts. This is required for Community post image uploads and course thumbnails; it is not just a future general-storage idea.

- Model a storage target with a stable ID, tenant/sub-admin owner, display name, Cloudflare account ID, bucket, S3-compatible endpoint/region, purpose flags, enabled/health status, and timestamps. Keep credential references separate from ordinary configuration. Use a storage adapter so application features do not depend directly on one bucket.
- Credentials must be stored in a deployment secret manager where available, or encrypted at rest using managed key material and a documented rotation process. Store no secret key in plaintext application tables. Never return secret values from APIs or log credentials/provider request signatures. Environment variable names/placeholders are allowed in docs; actual secrets are not.
- Add sub-admin-scoped APIs to create/update target configuration, test connection, list sanitized target metadata, set defaults by purpose, enable/disable, rotate credentials, and disconnect. Validate account/bucket/endpoint fields and use a non-destructive bounded connection test.
- Enforce ownership in querysets and object permissions for every operation. A sub-admin can use only their own targets and only for courses/posts they own or are assigned to. Main-admin oversight must be explicit and audited; it must not expose stored secrets.
- Add media metadata records referencing the target ID and object key, with media type, detected MIME, size, safe filename, owner, related course/post, status and timestamps. The database stores metadata only, never file bytes.
- Implement upload and cleanup workflows for Community post images and course thumbnail create/replace/delete. Validate detected file type, size and image dimensions; use collision-resistant object keys; reject path traversal and active formats by default. Keep buckets private and issue short-lived signed URLs or use an approved protected delivery endpoint.
- Use safe transactional ordering or a durable cleanup/outbox strategy for database/object-store consistency. Handle partial upload, failed database writes, object deletion failure, expired credentials and quota errors without false success.
- Disconnecting a target must not silently delete media. Identify existing references and require a documented keep/migrate/confirm-break policy. Failover or automatic routing across targets is opt-in and must prevent duplicate uploads and preserve the intended privacy policy.
- Add audit events for connection changes, connection tests (without secrets), default/purpose changes, uploads, replacements, deletions, disconnections and privileged cross-tenant actions. Add redacted operational metrics and provider error classification.
- Tests must cover multiple accounts per sub-admin, tenant isolation, secret redaction, invalid credentials, key rotation, upload validation, signed URL expiry, quota/failure recovery, media cleanup, course/post authorization and the prohibition on shared-cache storage of private media.
