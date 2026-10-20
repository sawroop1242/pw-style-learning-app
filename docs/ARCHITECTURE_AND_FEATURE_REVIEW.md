# StudySpace — Architecture & Feature Review

**What the docs ask for, what the code actually does, and what should be done next**

| | |
|---|---|
| **Report date** | 2026-10-20 |
| **Repository** | `sawroop1242/pw-style-learning-app` (private) |
| **Branch / commit reviewed** | `arena/d4e6056b-pw-style-learning-app` at `b79ff97` (same tree as `main`) |
| **Review type** | Documentation review + source audit + read-only runtime probing |
| **Product code changed** | None. This report is the only file added. |
| **Evidence** | Every command and result is listed in Appendix C. Claims marked **verified** were reproduced locally on 2026-10-20. |

> **How to read this document.** Sections 1–4 describe the intended product and the current build. Section 5 lists the gaps and defects. Section 6 is the answer to "what should be done": decisions to lock, a short hardening sprint, a revised roadmap, concrete build notes for each feature, and engineering standards. Sections 7–11 contain the prioritized backlog, effort estimates, risks, and open questions.

---

## 0. Executive summary

### 0.1 The short version

1. **The documentation describes a real product, not a toy.** It covers identity and email OTP, free/paid courses unlocked by one-use access codes, folders with video lessons and PDFs, a full test engine with sections and server-owned timers, CSV question imports by URL, notes/bookmarks/revision, a study planner, a community feed, student and staff analytics, multi-account Cloudflare R2 storage, a privacy-safe PWA, and production operations. That is **42 documents, ~33,700 words, 12 feature specs and 12 milestones**.
2. **The codebase is at the end of Milestone 2.** It has a solid Django foundation, **22 application models**, an ownership-scoped Django admin, environment guards, a health endpoint, and **53 passing tests**. That is genuine, usable groundwork.
3. **The API is still a Milestone-0 skeleton.** There are **5 read-only/CRUD viewsets and 2 token endpoints** — no registration, no logout, no password reset, no access-code redemption, no quiz submission, no personal workspace, no community, no analytics, no media. Most of the 22 models have no API or service behind them.
4. **Five verified defects exist in that skeleton** (detailed in §5.2):
   - paid-course lesson content, including `video_url`, is served **anonymously**;
   - quiz `explanation` is returned **before submission**;
   - `GET /api/lessons/?course=abc` returns **HTTP 500**;
   - a duplicate progress `POST` returns **HTTP 500**;
   - progress can be recorded against a **draft** lesson, leaking its title.
5. **A dependency security issue exists**: `djangorestframework>=3.15,<3.17` resolves to 3.16.1, which is affected by **CVE-2026-73228** (request-size-limit bypass / DoS), fixed in **3.17.2**. I verified that all 53 tests still pass on 3.17.2, so the upgrade is low-risk.
6. **The frontend is a demo, not a client.** It is 27 minified physical lines, loads demo courses when `API_BASE` is empty, keeps notes and completion in `localStorage`, has no authentication, and its service worker caches **every** successful GET and returns `index.html` for any failed GET — the exact behaviour the PWA spec forbids.
7. **CI has never executed a step.** The repository is private, the latest run (`39368078717`, 2026-10-20) failed in ~3 seconds with `steps: []` and no runner. The 53 green tests are therefore a local claim — reproduced in this review.
8. **The architecture is directionally right but needs four decisions before Milestone 3**: user model/email uniqueness, app boundaries, API versioning/contract, and token storage. Getting these wrong now is expensive later; getting them right now is cheap because there is no production data.
9. **Two schema gaps block promised features**: there is no `Section` model and no immutable attempt snapshot (so section timers, shuffled options, and "edits must not change history" cannot be implemented as specified), and there is no redemption-history model (so access-code analytics cannot be built).
10. **Realistic size**: the full documented scope is roughly **94–137 engineer-days before buffer** for one experienced developer (15–20 agent sessions), not 12 short runs. A one-week hardening sprint plus three roadmap inserts (hardening, assessment schema, R2) will save more time than it costs.

### 0.2 Recommended next move

**Do a short "M2.5 — Hardening & Decisions" sprint before starting Milestone 3.** Fix the verified defects, add the first real API tests, upgrade DRF, fix CI, and lock the four architectural decisions. Then execute Milestones 3–12 in the documented order, with three mandatory inserts (plus an optional early frontend shell):

- **M2.5** — hardening, decisions, CI, API test harness (3–5 days);
- **M5 (schema first)** — assessment schema extension (sections + attempt snapshots) before the test API is built;
- **M8.5** — R2 media storage before Community images and course thumbnails are marked complete (8–12 days).

### 0.3 First ten working days

| Day | Work | Done when |
|---|---|---|
| 1 | Fix paid-content leak, explanation leak, 500s, progress idempotency; make permissions deny-by-default | API tests prove anonymous users cannot read paid lessons or explanations; bad input returns 400, duplicate progress returns 200 |
| 2 | Add `pytest`-style API test module (or DRF `APITestCase`), factory helpers, query-count tests | 30+ API/permission tests run in CI-equivalent command |
| 3 | Upgrade DRF to ≥3.17.2; pin versions; add `ruff`, `pip-audit`, coverage; add `scripts/check.sh` | Full check script green locally; dependency audit clean |
| 4 | Decide user model, app boundaries, API versioning, token storage; write four short ADRs | Decisions recorded in `docs/adr/`; migrations planned |
| 5 | Fix CI (billing or alternate runner); add deploy check; reconcile `BUILD_STATUS.md` | CI job executes steps and is green, or a written blocker with an alternative gate |
| 6–10 | Start Milestone 3 (identity + OTP + roles + throttles) | Registration/login/logout/password change/OTP tests green |

---

## 1. How this review was done

### 1.1 Evidence base

| Activity | What was done |
|---|---|
| Documentation | Read all 42 files under `docs/`, including the 12 feature specs, 12 milestone prompts, master prompt, both implementation plans, and build status |
| Source | Read every backend Python file (models, admin, serializers, views, URLs, settings, tests, migration) and all frontend files |
| Runtime | Created a fresh venv, installed `requirements.txt`, ran Django checks, migration check, and the full test suite |
| API probing | Exercised 20+ requests through Django's test client against a temporary test database, including anonymous/authenticated access, draft content, paid content, invalid IDs, duplicate writes, and query counts |
| Compatibility | Re-ran the suite on `djangorestframework==3.17.2` to validate the security upgrade |
| Repo/CI | Queried the GitHub repository metadata and the latest Actions run with `gh` |
| Research | Checked Django/DRF support windows and Cloudflare R2 presigning behaviour against primary sources (Appendix E) |

### 1.2 Limits

- No real browser/device testing, no Lighthouse run, no service-worker inspection in a browser.
- No SMTP, R2, or deployment credentials exist, so email delivery, object storage, and production hosting were **not** tested.
- No load, concurrency, or penetration testing.
- The API probes use Django's test client and a temporary database; they are representative but not a production environment.
- Effort estimates are judgment-based, in ideal engineer-days, and exclude review/QA overhead.

---

## 2. What the docs describe

### 2.1 The product in one page

StudySpace is a mobile-first, installable learning PWA inspired by the usability of Indian ed-tech apps but explicitly **not** affiliated with PW. It is a Django REST API plus a static frontend. Students register, browse published courses, open free courses immediately, and unlock paid courses with a code obtained from the provider over Telegram. There is **no payment gateway and no checkout**. Staff (a main admin and owner-scoped sub-admins) manage courses, folders, lessons, PDFs, access codes, test series, question banks, analytics, community posts, and storage connections. Learning data (notes, progress, bookmarks, revision state, planner tasks, attempts) is private and server-backed. Tests are scored on the server, with server-owned timers and result-release policies. A PWA shell works offline, but private data and protected media must never enter shared caches.

### 2.2 Roles

| Role | Can do | Must not do |
|---|---|---|
| **Anonymous** | Read the published catalogue and published course metadata/lessons allowed by the spec | Access private data, drafts, answer keys, protected PDFs/video URLs, staff endpoints, tests that require an account |
| **Student** | Register, log in, redeem codes, take tests, keep private notes/progress/bookmarks/planner, read community posts in scope | Manage content, see other students' data, see unreleased results |
| **Sub-admin / provider** | Manage **only owned/assigned** courses, folders, lessons, PDFs, access codes, tests, imports, community posts; connect **their own** R2 targets | Create other admins, change global settings, touch another provider's content, see others' credentials |
| **Main admin** | Full platform authority; manage sub-admins; global analytics; moderation; all codes and content | Read secret credentials by default; bypass audit; see unreleased results through aggregates |

### 2.3 Feature inventory (12 specs)

| # | Feature area | What is required | Primary spec |
|---|---|---|---|
| 1 | **Identity & access** | Unique normalized username and email, password validation, JWT login/refresh/logout, authenticated password change, 6-digit email OTP reset, throttling, no account enumeration, main-admin sub-admin lifecycle | `FEATURE_SPEC_AUTHENTICATION.md` |
| 2 | **Courses & access codes** | Course/folder/lesson/PDF hierarchy, free vs paid pricing invariant, Telegram contact, publication, cryptographic one-use codes bound to one course, atomic redemption, durable grants, revocation policy, audit | `FEATURE_SPEC_COURSES_AND_ACCESS_CODES.md` |
| 3 | **Course discovery** | Published-only search across title/description/subject/provider, free/paid filters, allowlisted sorting, pagination, no protected URL leakage, 320 px usability | `FEATURE_SPEC_COURSE_DISCOVERY.md` |
| 4 | **Test series** | Series → test → sections → questions → choices; timed/untimed/section timing; server deadlines; autosave/resume; shuffle; attempt limits; negative marking; result release; immutable attempt snapshots; CSV import by URL with SSRF controls | `FEATURE_SPEC_TEST_SERIES.md` |
| 5 | **Student test analytics** | Per-attempt score/percentage/counts/duration; trends over released attempts; topic/section insights only with sufficient data; no cross-student comparison | `FEATURE_SPEC_ADVANCED_TEST_ANALYTICS.md` |
| 6 | **Personal workspace** | Private notes linked to lessons/questions; idempotent progress; bookmarks for courses/lessons/PDFs/questions; revision states; unified "My Revision" | `FEATURE_SPEC_NOTES_BOOKMARKS_REVISION.md` |
| 7 | **Study planner** | Private tasks/goals, due dates with timezone correctness, daily/weekly views, completion, opt-in best-effort browser reminders | `FEATURE_SPEC_STUDY_PLANNER.md` |
| 8 | **Community** | Authenticated feed; published, pinned-first posts; main-admin global posts; sub-admin course-scoped posts; students read-only; no comments/reactions in v1; optional images via R2 | `FEATURE_SPEC_COMMUNITY_POSTS.md` |
| 9 | **Staff analytics** | Main-admin global and sub-admin owner-scoped aggregates; documented formulas; date filters; bounded CSV exports with formula-injection protection; no PII in aggregates | `FEATURE_SPEC_ADMIN_ANALYTICS.md` |
| 10 | **R2 storage** | Each sub-admin connects multiple R2 buckets across multiple Cloudflare accounts; encrypted credentials; uploads only to owned targets; server validation; private buckets; short-lived signed URLs; cleanup/outbox; audit | `FEATURE_SPEC_R2_STORAGE.md` |
| 11 | **PWA/offline** | Installable shell, versioned static precache, offline indicator, low-data mode, no private API/media caching, safe logout/account switching, update prompts | `FEATURE_SPEC_PWA_OFFLINE.md` |
| 12 | **Production security** | RBAC everywhere, audit logs, throttles, request bounds, backups + restore drill, CI gates, structured logs, monitoring, HTTPS, secure deployment, export safety, accessibility, performance | `FEATURE_SPEC_PRODUCTION_SECURITY_RELIABILITY.md` |

### 2.4 Explicit non-goals

The docs repeatedly rule out: payments/checkout, comments/reactions/chat, live classes, certificates, AI tutoring/recommendations, proctoring/webcam surveillance, native apps, third-party analytics vendors by default, and any attempt to bypass DRM, paywalls, or provider access controls. These exclusions should survive the whole build.

### 2.5 The milestone contract

| Milestone | Goal |
|---|---|
| 1 | Reliable Django foundation |
| 2 | Data models + ownership-scoped admin |
| 3 | Auth, roles, ownership, throttling |
| 4 | Course/lesson API + access codes + protected resources |
| 5 | Quizzes/tests, CSV import, scoring, analytics |
| 6 | Notes, progress, bookmarks, revision |
| 7 | Frontend API foundation |
| 8 | Complete learning experience + discovery + planner + community |
| 9 | PWA, offline, low-data |
| 10 | Quality, security, performance |
| 11 | Deployment and operations |
| 12 | Final acceptance |

Each milestone must end with real code, real tests, a status update, and a stop. Markdown alone is explicitly **not** completion.

### 2.6 Documentation map and authority

| Layer | Documents | Role |
|---|---|---|
| Contract | `BUILD_MASTER_PROMPT.md` | Product goal, architecture rules, definition of done, non-negotiables |
| Sequence | `IMPLEMENTATION_PLAN.md` | Authoritative milestone order and exit criteria |
| Plans | `BACKEND_IMPLEMENTATION_PLAN.md`, `FRONTEND_IMPLEMENTATION_PLAN.md` | Responsibility-specific detail; must not override the sequence |
| Specs | 12 `FEATURE_SPEC_*.md` | Feature requirements and test matrices |
| Prompts | `agent-prompts/*.md` | Per-session execution instructions; not deliverables |
| Status | `BUILD_STATUS.md` | Evidence of what was actually run |

**Assessment:** the documentation is unusually detailed and security-aware. The problem is not quality; it is **volume relative to implementation** and the absence of a single, trustworthy status source. See §5.7.

---

## 3. Intended architecture

### 3.1 Runtime topology

```
┌──────────────────────────────┐          HTTPS/JSON          ┌──────────────────────────────┐
│  Static PWA frontend         │  ─────────────────────────►  │  Django 5.2 + DRF API        │
│  (Cloudflare Pages / CDN)    │  Authorization: Bearer ...   │  (gunicorn, WhiteNoise)      │
│  HTML/CSS/JS + service worker│  ◄─────────────────────────  │  /api/v1/...                 │
└──────────────────────────────┘                              └───────────┬──────────────────┘
                                                                          │
                              ┌───────────────────────────────────────────┼──────────────────────────┐
                              ▼                                           ▼                          ▼
                    ┌──────────────────┐                     ┌────────────────────┐      ┌──────────────────┐
                    │ PostgreSQL       │                     │ Private R2 buckets │      │ SMTP (OTP mail)  │
                    │ users, content,  │                     │ per sub-admin,     │      │ Gmail app pwd or │
                    │ attempts, media  │                     │ signed GET URLs    │      │ transactional    │
                    │ metadata, audit  │                     │ (no file bytes in  │      │ provider         │
                    └──────────────────┘                     │  the database)     │      └──────────────────┘
                                                             └────────────────────┘
```

Serving model: frontend and API are **separate origins** (the plans require this). That makes CORS, token transport, and cookie `SameSite` rules architectural decisions, not details. See §6.1, decision 4 and 9.

### 3.2 Backend layering (as documented, and what it implies)

The plans require consistent JSON, JWT auth, server-side ownership on every object, server-side scoring, SSRF-safe imports, throttling, audit, and safe exports. That is more than serializers can carry. The implied layering is:

```
HTTP views/viewsets  →  permissions  →  serializers (shape + validation)
        ↓
service/domain layer (transactions, locks, scoring, redemption, imports, media)
        ↓
models + constraints  →  PostgreSQL
        ↓
audit + structured logs + metrics
```

Today only the outer and inner layers exist; there is almost no service layer. That is acceptable at Milestone 2 and dangerous at Milestones 4–5, where row locks, idempotency, and snapshotting are mandatory.

### 3.3 Domain model map

The schema is already broad (22 models). Status here means "model exists", not "feature works".

| Domain | Models | Status | Notable missing pieces |
|---|---|---|---|
| Identity | `Profile`, `PasswordResetOTP`, `AuditEvent` | Exists | Custom/normalized user, unique email, OTP service, audit writer, role→`is_staff` sync |
| Catalogue | `Course`, `CourseFolder`, `Lesson`, `PdfResource` | Exists | DB constraints, provider URL allowlist, protected delivery, thumbnail media |
| Access | `AccessCode`, `CourseAccessGrant` | Exists | Redemption history, `EXPIRED` status, atomic redemption service, re-grant policy |
| Assessment | `TestSeries`, `Quiz`, `Question`, `Choice`, `QuizAttempt`, `AttemptAnswer`, `CsvImportJob` | Partial | `Section`, attempt question/choice snapshots, option order, section deadlines, unique in-progress attempt, import preview/errors |
| Personal | `Note`, `Progress`, `Bookmark`, `RevisionItem`, `StudyTask` | Exists | API, idempotent upsert, GFK orphan handling, timezone/reminders, note links |
| Community | `CommunityPost` | Exists | API, scope validation, media, sanitization, pin policy |
| Storage | — | **Missing** | `StorageTarget`, `MediaAsset`, encrypted credentials, adapter, cleanup outbox |
| Analytics | — | **Missing** | Queries/services; needs event/history data and indexes |

### 3.4 API surface implied by the specs

Roughly grouped, the finished API needs about **90–120 endpoints**:

| Area | Approx. endpoints |
|---|---|
| Auth (register, login, refresh, logout, me, password change, OTP request/verify/reset) | 8 |
| Staff user management (sub-admin create/list/deactivate/reactivate) | 4–6 |
| Catalogue public (courses list/detail/content, lessons, PDF download, discovery filters) | 6–8 |
| Staff course authoring (course/folder/lesson/PDF CRUD, reorder, publish) | 12–16 |
| Access codes (generate, list, revoke, redeem, grant status/revoke) | 6–8 |
| Tests public (series list/detail, test detail/instructions) | 4 |
| Attempts (start, get, autosave, submit, result, review, history) | 6–8 |
| Staff tests (series/test/section/question/choice CRUD, import preview/confirm, export) | 14–18 |
| Personal (notes, progress, bookmarks, revision, planner tasks, goals) | 12–16 |
| Community (feed, detail, staff CRUD, publish, pin) | 6–8 |
| Analytics (student summary, staff aggregate, export, attempt detail) | 6–8 |
| Storage (targets CRUD, test, defaults, upload, signed read, delete) | 8–10 |
| Ops (health, readiness, schema) | 3 |

Today: **14 functional routes** (5 viewsets × list/detail, token + refresh, API root, health). The API is roughly **10–15%** of the implied surface.

### 3.5 Frontend design implied

The specs require roughly ten screens: auth (6 forms), dashboard, catalogue/search, course detail, lesson view, test instructions/taking/result, notes/bookmarks/revision, planner, community, profile/security, plus staff course authoring, test management, analytics, and R2 connections. Required behaviours include timer state, autosave status, question palette, mark-for-review, resumable attempts, offline indicators, install prompts, accessible dialogs, and 320 px layouts.

That is a **multi-thousand-line application**. The existing 27-line demo is not a foundation for it; it is a placeholder with useful CSS tokens and an `esc()` helper.

### 3.6 Key flows that must be designed, not improvised

**Access-code redemption**

```
student → POST /courses/{id}/redeem {code}
        → throttle (user + IP)
        → normalize code → keyed hash
        → transaction: SELECT ... FOR UPDATE the code row
        → validate course binding, revoked, expiry, uses remaining
        → create AccessCodeRedemption row
        → create/reactivate CourseAccessGrant (unique user+course)
        → audit event (no raw code)
        → 200 access status, or a generic 400
```

**Test attempt**

```
start   → validate availability, attempt limit, no in-progress attempt
        → snapshot questions/choices/rules/section deadlines
        → return payload WITHOUT is_correct or explanation
save    → validate against the SNAPSHOT, not the live question bank
submit  → lock attempt, score from snapshot, set score/max, release per policy
expire  → lazy check on access + cron/management command
```

**Media upload**

```
staff → multipart upload (server-side, not browser-direct)
      → validate byte size, decode with Pillow, allowlist format, strip metadata
      → object key: purpose/owner/uuid.ext
      → upload to the selected owned R2 target
      → create MediaAsset row (metadata only)
      → on DB failure: delete object; on object failure: no row
student → GET /media/{id}/ → visibility check → 302 to 5-minute presigned GET
```

### 3.7 Security invariants that must hold at every milestone

1. Every endpoint has an explicit authentication and permission policy; **deny by default**.
2. Object-level ownership is checked on list, detail, create, update, delete, export, and nested routes.
3. Answer keys and explanations never appear in pre-submission payloads, DOM, localStorage, URLs, logs, or cache.
4. The server owns scores, timers, attempt state, publication state, prices, and grants.
5. Private data is never returned to another user, never in aggregates, never in shared caches.
6. Protected media is delivered only after an authorization check, with short-lived URLs.
7. Imports and any server-side fetch are SSRF-safe: HTTPS, resolved-IP validation, no unchecked redirects, size/time caps.
8. Secrets (SMTP, R2, JWT, OTP, codes) are never committed, logged, returned, or rendered.
9. Destructive or sensitive staff actions are audited with redacted metadata.
10. A feature is "done" only with executed tests and recorded evidence.

### 3.8 Operations model implied

PostgreSQL in production, `gunicorn`, WhiteNoise for static assets, HTTPS behind a proxy, environment-managed secrets, structured logs, liveness and readiness, backups **with a restore drill**, CI release gates, and a documented rollback. Today there is a `Procfile` and a settings guard; everything else is missing.

---

## 4. Current state (verified)

### 4.1 Numbers

| Metric | Measured |
|---|---|
| Documentation | 42 files, 33,656 words |
| Backend Python (excluding migrations and `.venv`) | 2,258 lines |
| Frontend physical lines | 27 (minified; ~14 KB total) |
| Application models | 22 (accounts 3, courses 19) |
| Functional API routes | 14 |
| Tests | 53 (35 model + 15 admin + 3 foundation) |
| API/viewset tests | **0** (one smoke test hits `/api/` root) |
| Migrations | 2 initial migrations |
| Top-level dependencies | 8 |
| Git history | 1 commit (`b79ff97`) |
| Working tree | Clean at review start (this report is the only addition) |

### 4.2 What genuinely works

- **Settings hardening**: `ENVIRONMENT` validation, production fail-fast on missing/short `SECRET_KEY`, empty `ALLOWED_HOSTS`, and `DEBUG=True`; booleans reject typos; CORS/CSRF are environment-driven.
- **Health endpoint**: GET-only `/healthz/` returns minimal JSON (POST → 405).
- **Admin ownership model**: main admins see all; sub-admins are scoped by course/series owner; foreign-key choice fields are restricted; cross-owner FK injection is tested; ownership cannot be reassigned by a sub-admin; private data admins are main-admin-only/read-only.
- **Access-code generation in admin**: 12-character high-entropy code, secret-prefix SHA-256 hash stored, raw value shown once; `uses_count` is not editable; grants cannot be hand-created.
- **Data model breadth**: almost every future feature has a sensible starting table, with unique constraints for folders, grants, progress, bookmarks, revision items, attempt answers, and active OTPs.
- **Test quality (for models/admin)**: 53 tests cover constraints, ownership boundaries, access-code hashing, and admin injection attempts. They are real tests, not placeholders.
- **Deployment basics**: `psycopg`, `dj-database-url`, WhiteNoise, gunicorn, a `Procfile`, and a GitHub Actions workflow.

### 4.3 What is only "schema on paper"

These models exist but have **no service, API, or UI**: `CourseFolder`, `PdfResource`, `AccessCode` (redemption), `CourseAccessGrant`, `TestSeries`, `Quiz` (attempt lifecycle), `Question`, `Choice`, `QuizAttempt`, `AttemptAnswer`, `CsvImportJob`, `Bookmark`, `RevisionItem`, `StudyTask`, `CommunityPost`, `AuditEvent`, `PasswordResetOTP`.

### 4.4 What is demo-only

| Thing | Current behaviour |
|---|---|
| Course data | If `API_BASE` is empty (it is), three hard-coded demo courses are shown |
| Notes | `localStorage`, not the Notes API |
| Completion | `localStorage` Set, with a fire-and-forget POST only if a token manually exists |
| Auth | No sign-up/login UI; `studyspace-token` would have to be set by hand |
| Quiz | Not rendered at all |
| Service worker | Caches every successful GET, including future API responses; offline fallback returns `index.html` for any failed GET |
| Manifest | One SVG icon; no 192/512 PNG; no `id`; no screenshots |
| Fonts | Google Fonts `@import` blocks offline fidelity and adds a third-party request |

### 4.5 CI status (verified)

`gh run view 39368078717` (latest, 2026-10-20 04:09 UTC):

- conclusion: **failure**;
- job started 04:09:40, completed 04:09:42;
- `steps: []`, no runner assigned.

This matches the blocker documented in `BUILD_STATUS.md`: a private repository whose Actions billing/spending limit prevents runners from starting. The workflow YAML itself is valid; every command it runs passed locally in this review. **The practical consequence is that nothing is gated today.**

---

## 5. Gap analysis

### 5.1 Feature readiness

Status key: **Missing** = no code; **Schema** = models only; **Partial** = some API/UI but not usable; **Usable** = end-to-end for the happy path; **Hardened** = tests + security + ops evidence.

| Area | Model | API | Frontend | Tests | Status |
|---|---|---|---|---|---|
| Identity & OTP | Yes | No | No | No | **Schema** |
| Catalogue public | Yes | Partial (title/description/subject only) | Demo only | Smoke | **Partial** |
| Course authoring | Yes | Admin only | No | Admin tests | **Partial** |
| Access codes | Yes | No | No | Model/admin only | **Schema** |
| Protected media | URL fields only | No | No | No | **Missing** |
| Assessments | Partial | No | No | Model only | **Schema** |
| CSV import | Metadata model | No | No | No | **Schema** |
| Personal workspace | Yes | Notes + progress only | localStorage | Model only | **Partial** |
| Planner | Yes | No | No | Model only | **Schema** |
| Community | Yes | No | No | Model only | **Schema** |
| R2 storage | No | No | No | No | **Missing** |
| Analytics | No | No | No | No | **Missing** |
| PWA | — | — | Prototype, unsafe SW | No | **Demo** |
| Security/ops | — | — | — | Local only | **Partial** |

### 5.2 Verified defects

| ID | Severity | Defect | Evidence | Required fix |
|---|---|---|---|---|
| **D1** | **Critical** | Paid-course lesson content is public: anonymous `GET /api/lessons/` returned a paid course's published lesson with `video_url` | `200` with `"title":"Paid video lesson","video_url":"https://youtu.be/x"` | Gate `LessonViewSet` by course access; hide `video_url` unless free, staff/owner, or active grant. Add tests. |
| **D2** | **High** | Quiz explanation leaks before submission | `GET /api/quizzes/` returned `"explanation":"SECRET EXPLANATION"` | Split public and staff/result serializers; never include `explanation` or `is_correct` pre-submit. |
| **D3** | **High** | Unhandled `ValueError` → HTTP 500 on invalid filter | `GET /api/lessons/?course=abc` → 500 (`Field 'id' expected a number`) | Validate query params with a serializer/filter; return 400. |
| **D4** | **High** | Duplicate progress → HTTP 500 `IntegrityError` | Second `POST /api/progress/` for the same lesson → 500 | Use `update_or_create` inside a transaction; return 200 on update. |
| **D5** | **High** | Progress can be recorded for **draft** lessons, and the response leaks the title | `POST /api/progress/` with a draft lesson → 201 + `lesson_title` | Validate publication and course access before writing; do not echo inaccessible titles. |
| **D6** | **Medium** | `AllowAny` is the global DRF permission | `settings.REST_FRAMEWORK` | Default to `IsAuthenticated`; mark public endpoints `AllowAny` explicitly. |
| **D7** | **Medium** | Notes API cannot link to a lesson/question; unknown `lesson` field is silently ignored | `POST /api/notes/ {lesson: 1}` → 201 without any link | Add validated `lesson`/`question` fields; reject conflicting or inaccessible links. |
| **D8** | **Medium** | N+1 query on progress list | 10 progress rows → **13 queries** because `lesson_title` follows `lesson` without `select_related` | `select_related("lesson")`; add a query-count test. Course list is fine (12 courses → 3 queries thanks to prefetch). |
| **D9** | **Medium** | DRF pinned below a security fix | `requirements.txt`: `>=3.15,<3.17`; installed 3.16.1; CVE-2026-73228 fixed in 3.17.2 | Upgrade to `>=3.17.2,<3.19`; verified 53/53 tests still pass on 3.17.2. |
| **D10** | **Medium** | A fresh `createsuperuser` is **not** a main admin | Verified: `is_superuser=True`, `profile.role="student"`, `is_main_admin=False` | Assign `MAIN_ADMIN` for superusers (signal/manager) or provide a bootstrap command; document. |
| **D11** | **Medium** | Role and `is_staff` can diverge | Verified: role `sub_admin`, `is_staff=False`; model admin reports module permission, Django admin login denies | One role service updates both; test every transition; block admin access for non-staff roles at the site level. |
| **D12** | **Medium** | No API tests, so 500s and leaks pass "green" | Only `config/tests.py` and `test_admin.py` use the test client; 2 references to `/api/` | Add viewset/permission/API tests before M3. |

### 5.3 Schema-level gaps (blocking promised features)

| # | Gap | Why it matters | Fix timing |
|---|---|---|---|
| S1 | **No `Section` model**; `Question` has no section FK | Section timing, navigation policy, section analytics are impossible | M5, before endpoints |
| S2 | **No immutable question/choice snapshot**; `QuizAttempt.question_order` is JSON only; `AttemptAnswer` points at live `Choice` rows | Editing a question changes historical attempts and scoring; `shuffle_options` cannot be reproduced (no option-order field) | M5 |
| S3 | No `AttemptSection` (per-section deadlines/status) | "Earliest deadline wins" cannot be computed reliably | M5 |
| S4 | No unique constraint for one in-progress attempt per user+quiz | Double-start races; duplicate scoring | M5 |
| S5 | `Choice.is_correct` has no per-question-type validation | Zero or multiple correct answers on single-choice questions produce wrong scores | M5 (service + admin form + DB checks where possible) |
| S6 | `AttemptAnswer.selected_choices` has no check that choices belong to the question | Forged IDs could be scored or rejected unpredictably | M5 |
| S7 | No `AccessCodeRedemption` history | Redemption trends, failure counts, per-learner history impossible; only `uses_count` and `last_redeemed_by` exist | M4 |
| S8 | `AccessCode.status` never returns `EXPIRED` | Admin/UI cannot distinguish expired from unused | M4 |
| S9 | `CourseAccessGrant` is unique on `(user, course)` | After revocation, a new code cannot create a grant; must reactivate, and no policy is defined | M4 |
| S10 | `Quiz` allows both `series` and `course` null (or both set) | Orphan tests and ambiguous ownership scoping | M5 |
| S11 | No `LearningEvent`/history; `Progress` has only `completed` + `updated_at` | Trends, time-to-complete, and "continue learning" position cannot be derived | M4/M6 |
| S12 | `PdfResource.file_url` and `Lesson.video_url` are public URL fields | "Protected" is unenforceable for externally hosted files; hiding a URL is not access control | M4 |
| S13 | No `MediaAsset`/`StorageTarget` | R2 feature has no data model at all | M8.5 |
| S14 | `Bookmark`/`RevisionItem`/`StudyTask` use `GenericForeignKey` with no cleanup | Orphan rows after resource deletion; "unavailable" state undefined | M6 |
| S15 | `Note` allows both `lesson` and `question`, or neither, with no rule | Ambiguous semantics and analytics | M6 |
| S16 | Pricing and Telegram invariants exist only in `clean()` | `objects.create()` and future APIs bypass them; no DB `CheckConstraint` | M4 |
| S17 | `StudyTask` has no user timezone or reminder state | Daily/weekly views and notification dedupe are underspecified | M8 |
| S18 | `CommunityPost` has no scope type beyond nullable course and no media link | Global vs course semantics are implicit; images cannot attach | M8 |
| S19 | `AuditEvent` has no writer, index on actor/action, or retention policy | Audit requirement is unmet despite the table existing | M3 |
| S20 | Auth uses `auth.User` with non-unique `email`; `Profile` holds role | Case-insensitive unique email and a single identity source are required | **Decide before M3** |
| S21 | Access-code hash is `sha256(SECRET_KEY + code)`, not HMAC | Rotating `SECRET_KEY` silently invalidates every unused code; no dedicated key separation | M4 |

### 5.4 API-level gaps

- No API versioning; routes are `/api/...` and will change under clients.
- No OpenAPI schema; the frontend plan requires a stable documented contract.
- No consistent error envelope or machine-readable error codes.
- No throttling on token endpoints (credential stuffing) or any other endpoint.
- Pagination is a fixed 50 with no documented contract or maximum; ordering and search limits are not defined.
- No object-level permission classes; only queryset filtering.
- Progress list has no `select_related("lesson")` (10 rows → 13 queries); no query-count tests.
- No `Cache-Control` policy on private endpoints.
- No `/readyz`, no structured logs, no request IDs.

### 5.5 Frontend gaps

- No auth screens, session handling, or 401 refresh flow.
- No router/views beyond a single scrolling page; no course detail, lesson, test, planner, community, profile, or staff screens.
- No API client abstraction, timeout/abort, or error normalisation.
- No loading/empty/error/retry states beyond one text line.
- No accessibility work (focus management, live regions, dialogs, skip links).
- Service worker privacy defect: caches all GETs and returns the shell for failed API requests.
- Manifest/installability gap (SVG only).
- Google Fonts blocks offline rendering and adds a third-party dependency.
- No build pipeline, cache busting, or module structure.

### 5.6 Operations gaps

- No `Dockerfile`, no platform config (Render/Fly/Railway), no release/migrate command.
- No production logging configuration, error tracking, metrics, or alerting.
- No backups, restore drill, retention, RPO/RTO.
- No `SECURE_PROXY_SSL_HEADER`, no CSP, no permissions policy.
- No dependency scanning, coverage gate, formatter/linter, or pre-commit.
- No README section on environment matrix, deployment, or runbook.
- No `LICENSE`, `SECURITY.md`, or privacy policy.

### 5.7 Documentation inconsistencies (fix these)

| Document | Issue |
|---|---|
| `BUILD_STATUS.md` | "Current stage: Milestone 2" and, four lines later, "Milestones 1 and 2 verified … Next: Milestone 3". A "Milestone 2 changes (in progress)" section remains above "Milestone 2 result - verified". |
| `BUILD_STATUS.md` | Test breakdown says "33 model tests, 20 admin tests"; actual is **35 model + 15 admin + 3 foundation = 53**. |
| `BUILD_STATUS.md` | Says `POST /healthz/` returns 403; the test asserts **405**. |
| `IMPLEMENTATION_PLAN.md` | Milestone 0 baseline boxes are unchecked even though the commands are recorded; Milestone 1 boxes say "runtime verification pending" although runtime evidence exists; Milestone 2 has no checkboxes despite being marked complete. |
| `BUILD_MASTER_PROMPT.md` | Still instructs "Start with Milestone 1 … do not skip to Milestone 2" even though both are complete. |
| `BACKEND_IMPLEMENTATION_PLAN.md` | Section numbering is broken: the R2 section is numbered `## 10` and appended after `## 11`. |
| `FRONTEND_IMPLEMENTATION_PLAN.md` | Header says "Planning only" although a prototype exists; add an as-built note. |
| `FEATURE_SPEC_COMMUNITY_POSTS.md`, master/backend/frontend plans | R2 is appended as a mandatory addendum without a milestone number or dependency map. It needs an explicit phase. |
| `BUILD_STATUS.md` | "53 backend tests green" is accurate but omits that **no API tests exist**; that overstates confidence. State the scope. |

### 5.8 Root causes

1. **Docs-first drift.** 33.7k words of specification were produced before the corresponding code; status and plans were updated by hand and diverged.
2. **Schema ahead of services.** 22 models exist, but the transactions, locks, scoring, import, and media services that make them safe do not.
3. **Serializer-sized thinking.** The current API is a thin DRF tutorial layer; it cannot carry ownership, throttling, versioning, or scoring.
4. **No feedback loop.** CI never runs, there are no API tests, and the frontend is not connected, so defects have no way to surface.
5. **No binding contract.** Without OpenAPI and client-generated types, the frontend and backend can drift indefinitely.

---

## 6. What should be done

### 6.1 Decisions to lock before Milestone 3

These are cheap now and expensive later. Each should become a one-page ADR in `docs/adr/`.

| # | Decision | Options | Recommendation | Why |
|---|---|---|---|---|
| 1 | **User model** | (a) custom `accounts.User`; (b) keep `auth.User` + `Profile` + expression unique index | **(a) custom user now**, resetting the two initial migrations in development | No production data exists. A custom user gives unique normalized email, role on one row, case-insensitive constraints, and no split identity. Option (b) needs a raw SQL index, normalization discipline, and still leaves `is_staff` divergence. |
| 2 | **App boundaries** | (a) keep everything in `courses`; (b) split into domain apps | **(b) split now**: `accounts`, `catalog`, `assessments`, `personal`, `community`, `storage`, `analytics` | `courses` already holds 19 models and will hold ~35. Splitting with `db_table` preserved is painless before data exists and painful after. |
| 3 | **API contract** | (a) unversioned; (b) `/api/v1/` + OpenAPI | **(b)** | The frontend will be built against it for months. Add `drf-spectacular`, commit the schema, and run a schema-diff check in CI. |
| 4 | **Token transport** | (a) access + refresh in `localStorage`; (b) access in memory + refresh in `HttpOnly` cookie; (c) session auth | **(b) if app and API share a registrable domain**; otherwise (a) with rotation/blacklist | Cookies avoid refresh-token exfiltration by XSS. `SameSite=Lax` works for `app.example.com` → `api.example.com`. If hosts are `*.pages.dev` + `*.onrender.com`, cookies are cross-site and painful — which links this decision to hosting. |
| 5 | **Paid media reality** | (a) public external URLs; (b) private object storage + signed/streamed delivery | **(b)** for anything labeled "protected" | A public PDF/video URL cannot be protected by hiding it. If the owner insists on public links, mark them `is_protected=False` and label them "external; access not enforceable". |
| 6 | **Attempt snapshot** | (a) JSON snapshot; (b) normalized `AttemptQuestion`/`AttemptChoice` tables | **(b)** | Normalized snapshots support section analytics, answer validation, and reliable scoring; JSON-only makes relational queries and integrity checks hard. |
| 7 | **R2 credentials** | (a) plaintext DB; (b) app-level encryption; (c) external secret manager | **(b) Fernet/MultiFernet** with `MEDIA_CREDENTIAL_KEY`, migration path to (c) | No plaintext ever. Key rotation via `MultiFernet`; document backup and rotation. |
| 8 | **Frontend stack** | (a) vanilla ES modules + Vite; (b) Svelte; (c) React/Preact | **(a) for M7, with a documented re-evaluation at M8**; choose (b) if the owner wants lower long-term UI risk | The plans require a documented reason to leave vanilla. Maintenance risk is a reason, not proof of impossibility. Modular vanilla is viable for v1; a test-taking UI with timers/autosave is where hand-rolled DOM usually breaks. |
| 9 | **Hosting** | Render / Fly / Railway; Neon / Supabase / RDS; Pages / Netlify | **Fly.io Mumbai + Supabase Mumbai + Cloudflare Pages + R2** for India latency; **Render + Neon** for simplest ops | The audience is Indian students; latency and same-site cookies matter. Keep app/API on subdomains of one domain. |
| 10 | **v1 scope** | Full 12-spec build vs a cut line | **Core v1**: auth, catalogue/access, protected PDFs, lessons, tests, notes/progress, dashboard, PWA shell, admin. **v1.1**: bookmarks/revision, planner, community, analytics dashboards, R2 images (unless images are required at launch) | The full scope is a 5–8 month build. A cut line protects quality; the docs' own rule is "no fake completion". |

**If decision 4 is the cookie option:** set `CORS_ALLOW_CREDENTIALS=True` with exact origins, `HttpOnly; Secure; SameSite=Lax; Path=/api/v1/auth/`, and require a CSRF token on refresh/logout. Keep the access token in memory only. If the frontend and API cannot share a registrable domain, use the header option with rotation, blacklist, and a short refresh lifetime instead.

### 6.2 Milestone 2.5 — hardening sprint (3–5 days)

**Goal:** make the existing skeleton safe and trustworthy before adding features.

| # | Task | Acceptance |
|---|---|---|
| 1 | Fix D1–D8 | API tests prove paid lesson data and explanations are absent; invalid filters return 400; duplicate progress returns 200; draft lessons rejected; notes can link; progress list has no N+1 |
| 2 | Change global permission to `IsAuthenticated`; explicitly mark public views | Anonymous access matrix test passes for every route |
| 3 | Add API test module + factories | ≥30 tests covering auth, ownership, publication, pagination, errors, query counts |
| 4 | Upgrade DRF to `>=3.17.2,<3.19`; pin exact versions; add `pip-audit` | `pip-audit` reports no known vulnerabilities; 53+ tests pass |
| 5 | Add `ruff` (lint + format), `coverage`, `scripts/check.sh` | One command runs check, migrations, tests, compile, lint, audit |
| 6 | Fix CI: billing or alternate runner | A workflow run shows executed, green steps (or a documented alternative gate) |
| 7 | Add `SECURE_PROXY_SSL_HEADER`, readiness endpoint, basic `LOGGING` with redaction | `check --deploy` clean except intentional HSTS preload; `/readyz` checks DB |
| 8 | Write ADRs for §6.1 decisions 1–4 | Four short ADRs merged |
| 9 | Fix `BUILD_STATUS.md` contradictions; add "scope of evidence" | Status matches reality; no duplicate "in progress" section |
| 10 | Add `docs/README.md` as the single documentation index | Every doc has an owner, status, and last-verified date |

**Exit criteria:** no known critical/high defect in the existing API; API tests exist; dependency audit clean; CI or an equivalent gate runs on every push; four ADRs approved; status docs consistent.

### 6.3 Revised roadmap

The documented order is sound. The edits below make it executable.

| Phase | Scope | Change vs docs | Effort (ideal days) |
|---|---|---|---|
| **M2.5** | Hardening + decisions | **New** | 3–5 |
| **M3** | Identity, roles, OTP, throttles, audit, staff user management | As documented, plus custom-user decision | 7–10 |
| **M4** | Catalogue, folders/PDFs, access codes, protected delivery, discovery, OpenAPI | As documented, plus redemption history and re-grant policy | 9–13 |
| **M4.5** *(optional)* | Frontend shell + auth UI against the real API | **New, recommended early** | 6–9 |
| **M5** | Assessment schema + API + scoring + CSV + student analytics | As documented, plus sections/snapshots | 12–18 |
| **M6** | Notes, progress, bookmarks, revision | As documented, plus idempotency and GFK handling | 5–7 |
| **M7** | Frontend API foundation (if not done at M4.5) | As documented | 8–12 |
| **M8a** | Learner journeys: catalogue, course, lesson, tests, notes, dashboard, profile | **Split from M8** | 12–15 |
| **M8b** | Planner + community + staff analytics UI | **Split from M8** | 8–12 |
| **M8.5** | R2 storage target + media upload/delivery | **New mandatory phase** | 8–12 |
| **M9** | PWA rewrite, offline, low-data | As documented | 4–6 |
| **M10** | Quality, security, accessibility, performance | As documented | 6–9 |
| **M11** | Deployment, backups, monitoring, runbook | As documented | 4–6 |
| **M12** | Acceptance and release evidence | As documented | 2–3 |

**Total:** ~94–137 engineer-days (before buffer), i.e. roughly **5–8 months for one full-time developer**. With an agent doing the implementation and a part-time reviewer, calendar time can compress to **~3–5 months** or **15–20 focused sessions**. This is the honest number; the docs' 12 short sessions understate it.

**Critical path:** user model → permissions → catalogue access checks → assessment snapshots → frontend contract. R2 is not on the critical path unless community images or thumbnails are launch requirements.

### 6.4 Build notes by feature

#### 6.4.1 Identity, roles, and OTP (M3)

- **Custom user** with `email` unique and normalized to lowercase; case-insensitive unique `username` via `UniqueConstraint(Lower("username"))`; `role` choices; `create_superuser` sets `MAIN_ADMIN`; a `sync_staff_flag` service keeps `is_staff = role in {main_admin, sub_admin}`.
- **Registration**: serializer-level validation, Django password validators, no client-settable role/flags, atomic create, generic duplicate-email/username errors (or field errors only if the product accepts enumeration; document the choice).
- **Tokens**: SimpleJWT with `token_blacklist`; access 15 min, refresh 7 days; rotation + blacklist after rotation; logout blacklists the refresh token; password change/reset blacklists all outstanding tokens.
- **OTP**: 6 digits from `secrets`; HMAC-SHA256 with a dedicated key or `SECRET_KEY`; 10-minute expiry; 5 attempts; one active OTP per user/purpose (constraint already exists); atomic consume via `filter(consumed_at__isnull=True).update(...)` returning 1; generic forgot-password response; throttle per email and per IP; email via `send_mail` with `fail_silently=False`; log failures without the code.
- **Staff lifecycle**: main-admin-only endpoints to create/list/deactivate/reactivate sub-admins; deactivation sets `is_active=False` and blacklists tokens; audit every transition.
- **Permissions**: `IsMainAdmin`, `IsStaffRole`, `IsOwnerOrMainAdmin`, `IsSelf`; object-level checks in services and viewsets.
- **Tests**: registration races, password policy, OTP expiry/replay/concurrency, enumeration resistance, token revocation, role escalation, deactivation, throttle boundaries.

#### 6.4.2 Catalogue, access codes, protected resources (M4)

- **Public read**: published only; expose slug, description, subject, image, pricing mode/price/currency, Telegram, lesson count, access state. Never expose drafts, code hashes, audit data, or protected URLs.
- **Content**: `/courses/{slug}/content/` returns folders, lessons, and PDF metadata with `locked` flags; `video_url` only after access; PDFs expose a `download_url` endpoint, never a raw `file_url` when protected.
- **Pricing invariant**: `CheckConstraint` for free=0 and paid>0; currency allowlist; Telegram handle regex and `t.me` host check.
- **Codes**: replace the current `sha256(SECRET_KEY + code)` construction with HMAC-SHA256 under a dedicated `ACCESS_CODE_KEY`; normalized input, 12+ characters, single-use default, course binding, expiry, revocation; keep admin creation and add staff API generation.
- **Redemption**: transaction + `select_for_update`; generic errors; throttle; create `AccessCodeRedemption`; upsert/reactivate grant; audit; return access status. Add tests for wrong course, expired, revoked, reused, concurrent, and free-course attempts.
- **Grants**: define re-grant policy (recommended: reactivate the existing row, keep history in redemptions/audit); add staff revoke endpoint with audit.
- **Protected delivery**: prefer private storage + 60–300 s signed GET or a streamed response; for external URLs, mark unprotected and label honestly.
- **Discovery**: `django-filter` with allowlisted fields; search length 2–100; ordering allowlist; page size ≤50; `annotate` counts; query-count tests.
- **Audit**: generation, revocation, redemption, grant change, publication, pricing change.

#### 6.4.3 Assessment engine (M5)

- **Schema additions**: `Section` (test, title, position, duration, navigation policy), `Question.section`, `AttemptSection`, `AttemptQuestion`, `AttemptChoice`, `UniqueConstraint(user, quiz, status="in_progress")`, `Question` validation for exactly one correct choice on single/true-false and at least one on multiple-choice.
- **Start**: validate availability window, attempt limit (count submitted+expired), and no in-progress attempt; snapshot questions, choices, rules, and section deadlines; return payload with no answer keys or explanations.
- **Save**: bulk endpoint; validate each question/choice against the attempt snapshot; update `answered`, `marked_for_review`, optional time spent.
- **Submit**: lock row; idempotent re-submit returns the same result; score with `Decimal`; per-question marks, negative marks only for wrong answers, document unanswered and partial-credit rules; set score/max/submitted_at; apply release policy.
- **Deadlines**: server clock only; lazy expiry on read; a management command finalises expired attempts every minute; store `deadline` and per-section deadlines; test refresh/clock manipulation.
- **Shuffle**: store attempt-specific question order **and** option order in snapshot rows; never reshuffle on refresh.
- **Result release**: `immediate`, `after_close`, `manual`; before release, return only status/timestamps; after release, return score, percentage, counts, section breakdown, answers and explanations.
- **Analytics**: derive from submitted/expired attempts only; document formulas and denominators; never include unreleased attempts.
- **CSV import**: versioned template; HTTPS URL only; preview returns row errors + a hash of normalized rows; confirm re-fetches, verifies the hash, and imports atomically; no CSV bytes in the database; SSRF controls as in §6.4.4.
- **CSV export**: staff-only, bounded, formula-injection escaping (`=`, `+`, `-`, `@`), audit.

#### 6.4.4 SSRF-safe fetcher (used by CSV import)

1. Accept only `https://`.
2. Resolve A/AAAA records once; reject loopback, private, link-local, multicast, unspecified, and `169.254.169.254`.
3. Connect to the **validated IP** while sending the original `Host` header and SNI; do not re-resolve at connect time.
4. Do not follow redirects automatically; if allowed, re-validate every hop and cap at 1–2.
5. Enforce connect/read timeouts (3 s/5 s), max bytes (2 MB), max rows (1,000), max field length, and UTF-8.
6. Parse with `csv.DictReader`; reject NUL/control characters; validate the correct-option key against options on the same row.
7. Return sanitized errors; never echo the fetched body, headers, or internal paths.

This matches OWASP guidance on resolved-IP validation and DNS rebinding (Appendix E).

#### 6.4.5 Personal workspace (M6)

- Notes: optional `lesson` or `question` link (enforce at most one), visibility validation, pagination, safe text rendering, no HTML.
- Progress: idempotent `update_or_create`, set `completed_at`/clear on uncomplete, validate lesson publication and course access, return 200/201 consistently.
- Bookmarks/revision: API takes `resource_type` + `resource_id`, validates the allowlist and visibility, resolves GFK, handles duplicates with `get_or_create`, returns `available: false` for deleted/unpublished resources.
- GFK cleanup: signal or nightly command; never cascade into unrelated user data.
- Tests: cross-user isolation, duplicates, inaccessible IDs, deleted resources, pagination, safe rendering.

#### 6.4.6 Planner (M8)

- CRUD tasks with title, notes, due_at (UTC), duration, priority, completion; optional link to accessible course/lesson/test.
- Store the user's timezone (new field or profile setting); render daily/weekly bounds in that timezone.
- No recurrence in v1 unless rules are specified and tested.
- Browser reminders: opt-in, client-side, deduplicated, best-effort; never claim delivery; in-app fallback.
- Tests: ownership, invalid dates, timezone/DST, completion idempotency, notification denied.

#### 6.4.7 Community (M8)

- Scope: `course=None` = global; course posts require ownership (sub-admin) and publication.
- Visibility: authenticated users; global posts visible to all; course posts visible only when the course is published and the user has access (define this and test it).
- Staff authoring: main admin any scope; sub-admin own courses only; author and timestamps server-assigned; pin policy by role; delete confirmation.
- Body: plain text with line breaks; no raw HTML; optional maintained Markdown allowlist later.
- Pagination 20; pinned first, then newest; empty/error/offline states.
- Media: depend on M8.5; `MediaAsset` FK on the post.
- Cache: `private, no-store`; service worker network-only.
- Tests: scope, hidden posts, author spoofing, pin, delete, pagination, XSS.

#### 6.4.8 R2 storage (M8.5)

- `StorageTarget`: owner, name, Cloudflare account ID, bucket, endpoint, region (`auto`), purposes, enabled, health, `is_default_*`, encrypted credentials, `key_version`, timestamps.
- Encryption: `MEDIA_CREDENTIAL_KEY` (32-byte urlsafe base64) → `Fernet`/`MultiFernet`; never return secrets; rotation documented.
- Adapter: `boto3.client("s3", endpoint_url=f"https://{account_id}.r2.cloudflarestorage.com", region_name="auto", config=Config(signature_version="s3v4"))`; per-target client; no global `STORAGES` shortcut.
- Test connection: `head_bucket` or `list_objects_v2(MaxKeys=1)` with 5 s timeout; sanitized errors; throttle.
- Upload: server-side multipart, max 5 MB, Pillow decode/verify, JPEG/PNG/WebP only, reject SVG, dimension caps, re-encode to strip EXIF, random object key, upload, then DB row; compensating delete.
- Delivery: visibility check → `generate_presigned_url("get_object", ExpiresIn=300)` → 302 with `private, no-store`.
- Cleanup: `pending_delete` outbox + management command; never delete referenced objects; disconnect shows references and requires a keep/migrate/break decision.
- Tests: two accounts per sub-admin, tenant isolation, redaction, invalid credentials, rotation, upload validation, URL expiry, quota errors, cleanup, private-cache absence.

#### 6.4.9 Analytics (M5 student, M8b staff)

- Derive from persisted attempts, progress, redemptions, and audit — never from client values.
- Document formulas: completion rate, average percentage, pass rate, section average, question difficulty, denominator, date boundary.
- Use `submitted_at` for score metrics and `started_at` for starts; display IST but store UTC.
- Aggregates omit email/username; detail is role-scoped and audited.
- Exports: bounded, formula-safe, permission-checked, audited.
- If trends are required beyond current fields, add a minimal append-only `LearningEvent` and start writing it in M4/M6; otherwise dashboards will be empty forever.

#### 6.4.10 PWA (M9)

- Rewrite `sw.js`: precache only versioned static assets; network-only for `/api/`; navigation fallback only for navigation requests; never return the shell for API failures.
- Version caches with a build hash; activation deletes only `studyspace-*`; handle quota errors.
- Manifest: PNG 192/512 + maskable, `id`, `start_url`, `scope`, `display_override`.
- Offline page, online/offline banner, update prompt with `skipWaiting` after user confirmation.
- Low-data toggle: defer images, no autoplay, system fonts; keep errors visible.
- Test with Lighthouse, an offline Playwright run, and a Cache Storage inspection after logout/account switch.

#### 6.4.11 Admin and operations (M11)

- Settings split: `base.py`, `dev.py`, `test.py`, `prod.py`; secrets from env; `SECURE_PROXY_SSL_HEADER`; HSTS only after HTTPS is verified; CSP; secure cookies.
- JSON logs with request ID and redaction of `Authorization`, `Cookie`, OTPs, codes, and note bodies.
- `/healthz` liveness; `/readyz` DB check (and optional cache check), minimal output.
- Backups: provider PITR + nightly `pg_dump` to a separate bucket; RPO 24 h, RTO 4 h for MVP; **perform and record a restore drill**.
- Monitoring: uptime check, error tracking (Sentry), slow queries, failed emails/imports; alert thresholds.
- Runbook: deploy, migrate, rollback, rotate secrets, restore, incident triage.

### 6.5 Target repository structure

```
backend/
  config/
    settings/{base,dev,test,prod}.py
    urls.py, asgi.py, wsgi.py, health.py, logging.py
  accounts/        User, roles, OTP, audit, auth API, permissions
  catalog/         Course, Folder, Lesson, PdfResource, access codes, grants, delivery
  assessments/     Series, Test, Section, Question, Choice, Attempt*, ImportJob, scoring
  personal/        Note, Progress, Bookmark, RevisionItem, StudyTask
  community/       Post, post media links
  storage/         StorageTarget, MediaAsset, adapters/r2.py, crypto.py, cleanup.py
  analytics/       query services, exports
  ops/             audit helpers, readiness, management commands
  tests/           factories, api/, services/, security/
frontend/
  index.html
  src/{app.js, router.js, store.js, api/, views/, components/, styles/}
  public/{manifest.webmanifest, icons/, offline.html}
  sw.js
  vite.config.js
docs/
  README.md, BUILD_STATUS.md, IMPLEMENTATION_PLAN.md
  adr/, api/, runbook.md, specs/, agent-prompts/
```

**Migration note:** if models move between apps, set explicit `db_table` values and use `SeparateDatabaseAndState` so existing tables are not recreated. Do this **before** there is production data.

### 6.6 Engineering standards

- **Python**: `ruff` (lint + format), `pip-audit`, `django-upgrade` optional; no `black`/`isort` duplication.
- **Tests**: `pytest` + `pytest-django` + `factory_boy` (or DRF `APITestCase` if minimizing dependencies). Coverage gate 80% on services/views, not a global vanity number.
- **API**: `/api/v1/`, OpenAPI via `drf-spectacular`, committed schema, CI schema-diff check, consistent error envelope with `code` and `request_id`.
- **DB**: constraints for every invariant that can be expressed; `select_for_update` for redemption/attempt/submit; expand/contract migrations; no destructive migration in the same release as the code change.
- **Security**: deny-by-default permissions; throttles on auth/OTP/redeem/submit/import/export; request size limits; SSRF-safe fetcher; no secrets in logs.
- **Frontend**: ES modules, one API client, one store, accessible components, no `innerHTML` with server data, no tokens in URLs, JSDoc + `tsc --checkJs` optional.
- **Git**: one milestone per branch/PR, conventional commits, a status update in the same PR, no generated artifacts or `.venv` in Git.
- **Docs**: ADRs for irreversible decisions; one status file; API docs generated; runbook maintained.

### 6.7 Test plan

| Layer | What | Approx. count at v1 |
|---|---|---|
| Model/constraint | uniqueness, invariants, ordering, deletion | 60–80 |
| Service | redemption, scoring, snapshots, imports, media, analytics | 60–80 |
| API/permission | anonymous/auth/role/owner matrix, validation, pagination, errors | 120–160 |
| Security | OTP replay/concurrency, SSRF, exports, cache privacy, secret redaction | 30–40 |
| Frontend unit | API client, auth state, URL validation, formatting | 30–50 |
| E2E (Playwright) | register → browse → lesson → test → note → logout; staff create course/code; upload image | 8–12 journeys |
| Non-functional | axe accessibility, Lighthouse PWA/perf, query-count, load smoke | per release |

### 6.8 CI/CD gates

| Gate | Command | Blocks merge |
|---|---|---|
| Lint/format | `ruff check . && ruff format --check .` | Yes |
| Django check | `python manage.py check` | Yes |
| Deploy check | production-like env + `manage.py check --deploy` | Yes (warnings reviewed) |
| Migrations | `makemigrations --check --dry-run` | Yes |
| Tests | `pytest --cov` | Yes, 80% services/views |
| Dependency audit | `pip-audit` | Yes for high/critical |
| Schema diff | `drf-spectacular` schema committed | Yes |
| Frontend | `npm ci && npm run lint && npm test && npm run build` | Yes |
| E2E smoke | Playwright against staging | Yes on release |
| Cache privacy | Playwright inspects Cache Storage after logout | Yes |

Until GitHub Actions billing is fixed, run the same gates via a local `scripts/check.sh` and a second CI provider (GitLab/CircleCI) so "green" means something.

### 6.9 Deployment reference

| Component | Recommendation | Notes |
|---|---|---|
| API | Fly.io (Mumbai) or Render (Singapore) | gunicorn, 2+ workers, health check, release command runs migrations |
| Database | Supabase/Neon Postgres (Mumbai if available) | daily backups/PITR, connection pooling |
| Frontend | Cloudflare Pages | preview deploys, `_headers` for CSP/cache, SPA fallback |
| Media | Cloudflare R2 private buckets | per-sub-admin targets, presigned GET 300 s |
| Email | Gmail SMTP for MVP; Resend/Brevo for scale | app password, SPF/DKIM, monitor bounces |
| DNS/TLS | Cloudflare | `app.` + `api.` on one registrable domain (cookie decision) |
| Monitoring | Uptime check + Sentry + provider logs | alert on 5xx rate, latency, failed OTP/import jobs |
| Backups | PITR + nightly dump to a separate bucket | quarterly restore drill; record date and result |

### 6.10 Documentation cleanup

1. Add `docs/README.md` with a table: document, purpose, authority, status, last verified. Make it the only entry point.
2. Keep **one** status file (`BUILD_STATUS.md`) with exact commands, dates, scope of tests, and known gaps. Remove duplicate "in progress" sections.
3. Add a status banner to every spec: `Draft | Approved | In progress | Implemented (commit/date)`.
4. Fix the specific inconsistencies in §5.7.
5. Add ADRs for decisions 1–10 in §6.1.
6. Generate API docs from OpenAPI; do not hand-maintain endpoint tables.
7. Add `docs/runbook.md` (deploy, migrate, rollback, rotate, restore).
8. Archive superseded prompts under `docs/archive/` rather than deleting them.
9. Add `LICENSE`, `SECURITY.md`, and a short privacy/data-retention note (important for Indian student data under DPDP).
10. Reduce duplication: the master prompt, implementation plan, and both plans repeat the same rules. Keep the master as the contract, the plan as the sequence, and link rather than restate.

---

## 7. Prioritized backlog

### P0 — before any new feature

| ID | Item | Acceptance |
|---|---|---|
| P0-1 | Fix paid-lesson leak (D1) | Anonymous cannot get `video_url` or protected content |
| P0-2 | Fix explanation leak (D2) | Pre-submit payload has no `explanation`/`is_correct` |
| P0-3 | Fix 500s (D3, D4) and draft-progress leak (D5) | 400/200 as appropriate; no title leak |
| P0-4 | Deny-by-default permissions (D6) | Public routes explicit; anonymous matrix test |
| P0-5 | User model decision + implementation plan | ADR approved; migration path tested |
| P0-6 | DRF ≥3.17.2 (D9) | Tests green; audit clean |
| P0-7 | CI or equivalent gate | Green run with executed steps |
| P0-8 | Status/docs reconciliation | BUILD_STATUS matches reality |

### P1 — Milestones 3–6

| ID | Item |
|---|---|
| P1-1 | Registration/login/logout/refresh, password change |
| P1-2 | OTP reset with throttling and atomic consumption |
| P1-3 | Sub-admin lifecycle + role/is_staff sync + audit |
| P1-4 | Catalogue/detail/content API with access checks |
| P1-5 | Access-code redemption + history + re-grant policy |
| P1-6 | Protected PDF delivery |
| P1-7 | Discovery filters/search/sort + OpenAPI |
| P1-8 | Assessment schema: sections + snapshots |
| P1-9 | Attempt API + scoring + result release |
| P1-10 | CSV import/export with SSRF controls |
| P1-11 | Notes/progress/bookmarks/revision APIs |

### P2 — Milestones 7–12

| ID | Item |
|---|---|
| P2-1 | Frontend modules, API client, auth UI |
| P2-2 | Learner journeys (catalogue → lesson → test → result) |
| P2-3 | Planner UI + reminders |
| P2-4 | Community feed + staff authoring |
| P2-5 | R2 storage panel + uploads |
| P2-6 | Staff dashboards + exports |
| P2-7 | PWA rewrite + low-data |
| P2-8 | Accessibility/performance hardening |
| P2-9 | Deployment + restore drill |
| P2-10 | Acceptance report |

### Won't do in v1

Payments, comments/reactions/chat, live classes, certificates, AI tutor/recommendations, proctoring/webcam, native apps, third-party analytics by default, browser-direct uploads with credentials.

---

## 8. Effort and sequencing

### 8.1 Assumptions

- One experienced full-stack developer (or agent + reviewer), 5 days/week.
- Estimates are ideal days; add **25–30%** for review, QA, and surprises.
- Backend and frontend can overlap only after the API contract is frozen at the end of M4.

### 8.2 Phase effort

| Phase | Ideal days | Cumulative |
|---|---|---|
| M2.5 | 3–5 | 5 |
| M3 | 7–10 | 15 |
| M4 | 9–13 | 28 |
| M4.5 (optional frontend shell) | 6–9 | 37 |
| M5 | 12–18 | 55 |
| M6 | 5–7 | 62 |
| M7 | 8–12 | 74 |
| M8a | 12–15 | 89 |
| M8b | 8–12 | 101 |
| M8.5 | 8–12 | 113 |
| M9 | 4–6 | 119 |
| M10 | 6–9 | 128 |
| M11 | 4–6 | 134 |
| M12 | 2–3 | 137 |

With a 25–30% buffer: **~118–178 engineer-days**. A lean v1 that stops after M8a, M9, M10, and a minimal M11 is roughly **72–104 days**.

### 8.3 Delivery checkpoints (demoable value)

| Checkpoint | What a stakeholder can see |
|---|---|
| End of M3 | Register, log in, reset password, roles enforced |
| End of M4 | Browse courses, open a free lesson, redeem a code, download a protected PDF |
| End of M5 | Take a timed test, resume, submit, see a released result |
| End of M6 | Notes, progress, bookmarks, revision synced across devices |
| End of M8a | Complete learner journey in a real UI on a phone |
| End of M8.5 | Staff upload course thumbnails and community images |
| End of M9 | Installable PWA that works offline safely |
| End of M11 | A real deployment with backups and monitoring |

### 8.4 Parallelization

- After M4, frontend work (M4.5/M7) can proceed against the frozen OpenAPI schema while backend M5/M6 continues.
- R2 (M8.5) can start once M3 roles and M4 course ownership are stable; it does not need M5.
- Analytics UI (M8b) should wait for M5 persisted attempts; the query services can be written in parallel.

---

## 9. Risks

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Documentation keeps growing faster than code | High | High | Freeze specs at v1.0; only change via ADR; status file is the single truth |
| Scope is 5–8 months, not 12 sessions | High | High | Publish the estimate; agree a v1 cut line; deliver vertical slices |
| Paid content cannot be protected with public links | High | High | Private storage + signed delivery; label public links honestly |
| Security regression while adding features | Medium | High | API permission matrix tests; deny-by-default; CI |
| OTP email deliverability/spam | Medium | Medium | Use a transactional provider for production; SPF/DKIM; monitor bounces; in-app fallback messaging |
| R2 credential breach | Low | High | Fernet encryption, least-privilege tokens, redaction, rotation runbook, audit |
| CI remains broken | High | High | Fix billing immediately; add a second gate; local script is not enough long-term |
| Solo bus factor / agent drift | Medium | High | ADRs, runbook, small PRs, status evidence, tests as documentation |
| Low-end Android performance | Medium | Medium | Bundle budget, lazy loading, pagination, low-data mode, test on a real device |
| Analytics privacy leak | Medium | High | Aggregate-only endpoints, sample-size floors, release-policy checks, tests |
| Legal/compliance (DPDP, minors, content rights) | Medium | High | Privacy policy, minimal PII, parental-consent review, licensed content only, brand review |
| Database migration accident in production | Low | High | Expand/contract, backups, staging rehearsal, rollback plan |

---

## 10. Open questions for the owner

1. **Is v1 for a real cohort or a demo?** The answer changes the quality bar, timeline, and infrastructure budget.
2. **Is a data reset acceptable?** If yes, adopt a custom user model now (strongly recommended). If no, choose the profile + expression-index path.
3. **Will the frontend and API share one registrable domain** (e.g., `app.example.com` + `api.example.com`)? This determines whether HttpOnly refresh cookies are practical.
4. **Where are paid videos and PDFs actually hosted?** If they are public YouTube/Drive links, "protected" must be relabeled; if private R2, build signed delivery.
5. **Who provides SMTP and R2 credentials, and where will they be stored?** Never in chat or Git.
6. **Are community images and course thumbnails required at launch?** If yes, R2 moves into v1 and ahead of M8b.
7. **Do tests need sections, negative marking, and partial credit in v1?** These drive the M5 schema.
8. **What is the expected cohort size** (100, 10k, 100k)? It determines caching, throttling, and whether Redis is needed.
9. **Deployment budget and region preference?** India latency suggests Mumbai; the cheapest option may not be the best UX.
10. **What is the legal/brand position?** The repo name contains "pw-style"; before a public launch, review trademark risk, add a disclaimer, and confirm content rights.
11. **Is the repository staying private?** If it can be public, GitHub Actions may work without billing changes.
12. **Who reviews and merges agent work?** A named reviewer and a PR checklist prevent unreviewed security changes.

---

## 11. Recommended next action

**Run Milestone 2.5 this week.** It is 3–5 days, it fixes real security defects, it makes the test suite meaningful, and it locks the four decisions that everything else depends on. Then begin Milestone 3 with a custom user model, deny-by-default permissions, and an API test harness already in place.

If only one thing is done from this report, do this: **stop adding features until anonymous users cannot read paid lesson URLs or pre-submission explanations, and until a bad query parameter cannot return a 500.** Those are not roadmap items; they are the difference between a demo and a platform.

---

## Appendix A — Actual API routes (verified)

| Method | Route | Auth | Notes |
|---|---|---|---|
| GET | `/healthz/` | Public | Minimal `{"status":"ok"}` |
| GET | `/api/` | Public | API root links |
| GET | `/api/courses/` | Public | Published only; title/description/subject/lesson_count |
| GET | `/api/courses/{id}/` | Public | Same fields |
| GET | `/api/lessons/` | Public | Published only; `?course=` filter; **leaks paid content** |
| GET | `/api/lessons/{id}/` | Public | Same |
| GET | `/api/quizzes/` | Public | Published only; **leaks explanations** |
| GET | `/api/quizzes/{id}/` | Public | Same |
| GET/POST/PUT/PATCH/DELETE | `/api/notes/` and `/{id}/` | JWT | User-scoped; cannot link lesson/question |
| GET/POST/PATCH | `/api/progress/` and `/{id}/` | JWT | User-scoped; duplicate POST → 500 |
| POST | `/api/token/` | Public | SimpleJWT pair |
| POST | `/api/token/refresh/` | Public | SimpleJWT refresh |
| * | `/admin/` | Staff session | Ownership-scoped model admin |

## Appendix B — Model inventory (22)

| App | Model | Key constraint |
|---|---|---|
| accounts | Profile | OneToOne user; role |
| accounts | PasswordResetOTP | One active OTP per user+purpose |
| accounts | AuditEvent | Append-only intent; no writer yet |
| courses | Course | unique slug; no DB price check |
| courses | CourseFolder | unique title per course |
| courses | Lesson | folder must match course (clean only) |
| courses | PdfResource | folder FK; URL field |
| courses | AccessCode | unique code hash; default one use |
| courses | CourseAccessGrant | unique user+course |
| courses | TestSeries | unique slug; owner |
| courses | Quiz | timing/release fields; owner property |
| courses | Question | type/marks/topic; no section |
| courses | Choice | `is_correct`; no per-type check |
| courses | QuizAttempt | status/score/JSON order; no in-progress uniqueness |
| courses | AttemptAnswer | unique attempt+question; M2M to live choices |
| courses | CsvImportJob | URL + counts only |
| courses | Note | user; optional lesson/question |
| courses | Progress | unique user+lesson |
| courses | Bookmark | unique user+resource; GFK |
| courses | RevisionItem | unique user+resource; GFK |
| courses | StudyTask | user; GFK link |
| courses | CommunityPost | author; nullable course |

## Appendix C — Commands and evidence

Run from `backend/` with a fresh venv on 2026-10-20 unless stated.

| Command | Result |
|---|---|
| `python -m pip install -r requirements.txt` | Success; Django 5.2.18, DRF 3.16.1, SimpleJWT 5.5.1 |
| `manage.py check` | Exit 0, "no issues" |
| `manage.py makemigrations --check --dry-run` | Exit 0, "No changes detected" |
| `manage.py test` | **53 tests, OK, ~12 s** |
| `manage.py check --deploy` (production-like) | 2 warnings: W009 (throwaway key) and W021 (HSTS preload not set) |
| `GET /api/lessons/` (anon, paid course) | **200**, returns paid `video_url` |
| `GET /api/quizzes/` | **200**, returns `explanation` |
| `GET /api/lessons/?course=abc` | **500** (`ValueError`) |
| `POST /api/progress/` duplicate | **500** (`IntegrityError`) |
| `POST /api/progress/` draft lesson | **201** + draft title |
| `POST /api/notes/` with `lesson` | **201**, field ignored |
| `GET /api/courses/` (12 courses) | **3 queries** (count + page + prefetch; efficient) |
| `GET /api/progress/` (10 rows) | **13 queries** (N+1 on `lesson_title`) |
| `POST /api/token/` | 200; wrong password 401 |
| `POST /api/register/` | 404 (no route) |
| Fresh superuser | `role=student`, `is_main_admin=False` |
| `pip install djangorestframework==3.17.2` + tests | **53 tests, OK** |
| `gh run view 39368078717` | failure, `steps: []`, 2 s, no runner |
| `gh repo view` | private, default branch `main`, pushed 2026-10-20 04:09 UTC |

Frontend inspection: `API_BASE=""`, demo courses, `localStorage` notes/completion, SW caches all GETs and falls back to `index.html`, one SVG icon.

## Appendix D — Documentation index and recommended status

| Document | Use | Recommended status |
|---|---|---|
| `BUILD_MASTER_PROMPT.md` | Product contract | Approved; update "next milestone" text |
| `IMPLEMENTATION_PLAN.md` | Milestone order | Approved; fix checkboxes |
| `BACKEND_IMPLEMENTATION_PLAN.md` | Backend detail | Approved; fix section numbering |
| `FRONTEND_IMPLEMENTATION_PLAN.md` | Frontend detail | Approved; add as-built note |
| `BUILD_STATUS.md` | Evidence | Authoritative; fix contradictions, add test scope |
| `FEATURE_SPEC_AUTHENTICATION.md` | Identity/OTP | Approved; decide user model |
| `FEATURE_SPEC_COURSES_AND_ACCESS_CODES.md` | Catalogue/access | Approved; decide protected delivery |
| `FEATURE_SPEC_TEST_SERIES.md` | Assessment engine | Approved; add sections/snapshots to schema |
| `FEATURE_SPEC_ADVANCED_TEST_ANALYTICS.md` | Student analytics | Approved; define denominators |
| `FEATURE_SPEC_ADMIN_ANALYTICS.md` | Staff analytics | Approved; define event sources |
| `FEATURE_SPEC_NOTES_BOOKMARKS_REVISION.md` | Personal workspace | Approved |
| `FEATURE_SPEC_COURSE_DISCOVERY.md` | Search/filter | Approved |
| `FEATURE_SPEC_STUDY_PLANNER.md` | Planner | Approved; v1.1 candidate |
| `FEATURE_SPEC_COMMUNITY_POSTS.md` | Community | Approved; v1.1 candidate |
| `FEATURE_SPEC_PWA_OFFLINE.md` | PWA | Approved; rewrite SW in M9 |
| `FEATURE_SPEC_R2_STORAGE.md` | Storage | Approved; needs milestone slot |
| `FEATURE_SPEC_PRODUCTION_SECURITY_RELIABILITY.md` | Ops | Approved; apply in M2.5/M3/M10/M11 |
| `docs/agent-prompts/*` | Execution prompts | Keep; archive superseded versions |

## Appendix E — Sources consulted

- Django 5.2 LTS support timeline (extended support to April 2028; latest 5.2.18): <https://www.djangoproject.com/download/> and <https://endoflife.date/django>
- Django annual release cycle / future LTS planning: <https://www.djangoproject.com/weblog/2026/aug/10/annual-release-cycle/>
- DRF 3.16 announcement (Django 5.2 support): <https://www.django-rest-framework.org/community/3.16-announcement/>
- DRF release notes (3.17.2 fixed CVE-2026-73228): <https://www.django-rest-framework.org/community/release-notes/>
- CVE-2026-73228 advisory: <https://github.com/advisories/GHSA-2m8g-3cmr-wg3w>
- Cloudflare R2 presigned URLs (1 s to 7 days; endpoint and `region: auto`): <https://developers.cloudflare.com/r2/api/s3/presigned-urls/>
- Cloudflare R2 boto3 examples: <https://developers.cloudflare.com/r2/examples/aws/boto3/>
- django-storages Cloudflare R2 notes: <https://django-storages.readthedocs.io/en/1.14.3/backends/s3_compatible/cloudflare-r2.html>
- OWASP SSRF Prevention Cheat Sheet (resolve, validate, pin IP; no unchecked redirects): <https://cheatsheetseries.owasp.org/cheatsheets/Server_Side_Request_Forgery_Prevention_Cheat_Sheet.html>
- OWASP Top 10 A10:2021 SSRF: <https://owasp.org/Top10/2021/A10_2021-Server-Side_Request_Forgery_%28SSRF%29/>

---

*End of report. No product code was modified. Evidence reflects the repository at `b79ff97` on 2026-10-20.*
