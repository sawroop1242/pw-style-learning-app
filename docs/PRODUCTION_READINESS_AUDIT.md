# Production Readiness Audit — StudySpace

**Date:** 23 October 2026
**Branch:** `arena/b4556565-pw-style-learning-app` (from `main` @ `fd75b2c`)
**Scope:** every source file in the repository — backend Python, frontend assets, configuration, migrations and CI.
**Verdict:** the previously reported **data-leak and tampering defects are fixed and covered by tests**. The
codebase is materially harder to break than before, but it is **not yet production-ready**. The remaining
blockers are listed in [§7](#7-what-is-still-not-production-ready), and none of them are hidden by this pass.

---

## 1. Executive summary

| | Before | After |
|---|---|---|
| Backend Python | 5,825 lines | 7,020 lines |
| Tests | 96 | **142 (all passing)** |
| API-level tests | 0 | 46 |
| Paid media exposed to anonymous users | **Yes** (video + PDF URLs) | No |
| Paid quiz papers readable anonymously | **Yes** | No |
| Anonymous `POST /api/quizzes/start/` | **HTTP 500** | 401 |
| Student can rewrite attempt status / release date | **Yes** (`PATCH`) | No (405) |
| Autosaved answers lost on submit | **Yes** (score forced to 0) | No |
| Duplicate progress `POST` | **HTTP 500** | 200, upserted |
| Progress re-pointed at a draft lesson | **Leaked the title** | 400 |
| Access-code hash | `sha256(secret + code)` | `HMAC-SHA256` (legacy still verifies) |
| Default DRF permission | `AllowAny` | `IsAuthenticated` |
| `manage.py check --deploy` | 2 warnings | 1 warning (`HSTS preload`, deliberate) |

**Thirteen defects were fixed.** Twelve lower-severity issues remain open and are documented in §6 with a
recommended fix and rough effort. Nothing in this document is claimed as tested unless the command output is
reproduced in §8.

---

## 2. Method

1. Read every file in `backend/`, `frontend/`, `docs/`, `.github/` and the repository root.
2. Built a probe suite that exercised the real HTTP surface as anonymous, student, grantee, sub-admin and
   main-admin users, and captured status codes and payloads. Probe files were deleted after evidence was
   recorded; the durable replacements live in `courses/tests/test_api_security.py`.
3. Fixed each confirmed defect, then re-ran the probe behaviours as assertions.
4. Ran the full suite, `makemigrations --check`, and `check --deploy` with production settings.

**What this audit did not do:** it did not deploy, did not run CI (CI cannot run on this repository — see
§7), and did not performance-test beyond query-count assertions.

---

## 3. Confirmed defects (all fixed)

Severity reflects exploitability and blast radius, not effort.

| ID | Sev | Defect | Evidence before fix | Fix |
|----|-----|--------|---------------------|-----|
| D1 | **Critical** | `GET /api/courses/<paid>/` returned every lesson's `video_url` and every protected PDF's `file_url` to anonymous callers | probe: `video=True pdf=True` at HTTP 200 | `LessonSerializer` / `PdfResourceSerializer` gate media through `policy.can_read_media()`; `is_locked` flag added |
| D2 | **Critical** | `GET /api/quizzes/` returned questions **and choices** for quizzes attached to paid courses | probe: `prompt=True choices=True` | `QuizSerializer.get_questions()` returns `[]` without access; `QuizViewSet` filters to accessible quizzes |
| D3 | **Critical** | Anonymous `POST /api/quizzes/start/` raised `TypeError: Field 'id' expected a number but got AnonymousUser` → HTTP 500 | probe: `anon-start status=500` | `@permission_classes([IsAuthenticated])` + `policy.can_access_quiz()` → 403 for non-grantees |
| D4 | **High** | `QuizAttemptViewSet` was a full `ModelViewSet`: `PATCH` could set `status` and `result_released_at`, bypassing the release policy | probe: `db_status=submitted`, `released=True` | Attempt API is now read-only (`ListModelMixin` + `RetrieveModelMixin`); all mutations go through `submit` / `autosave` |
| D5 | **High** | Student could `PATCH` a progress row onto a draft lesson and read its title back from the response | probe: `leak=True` at HTTP 200 | `ProgressSerializer.validate_lesson()` enforces published + accessible + immutable on update |
| D6 | **High** | Duplicate `POST /api/progress/` raised `IntegrityError`, then `TransactionManagementError` → HTTP 500 | probe: 500 | `create()` uses `get_or_create` inside `transaction.atomic`, returns 201/200 |
| D7 | **High** | Autosaved answers were discarded on submit: `POST submit {answers: []}` produced `score=0.00 max_score=0.00` | probe: `score=0.00 max=0.00` | `submit` persists payload first, then grades from the database over the frozen `question_order` |
| D8 | **High** | `max_score` was computed only from submitted answers, so skipping questions inflated the percentage | code reading + D7 probe | `grading.grade_attempt()` sums marks over the whole attempt snapshot |
| D9 | **Medium** | Result payload silently omitted `correct_choices` — the field's `source="question.choices.filter(is_correct=True)"` is not a resolvable DRF source | probe: `answers_detail` had no `correct_choices` | `SerializerMethodField` reading the prefetched choices |
| D10 | **Medium** | `LessonSerializer.video_url` was a required field, so staff could not create a lesson without a video (`400 video_url: This field is required`) | probe: `P8 body={"video_url": ["This field is required."]}` | Separate `StaffLessonSerializer` with `required=False, allow_blank=True` |
| D11 | **Medium** | Access-code hashing used `sha256(SECRET_KEY + code)` — a plain concatenated digest, not a keyed MAC | code reading | `HMAC-SHA256` with domain separation; `verify_access_code()` accepts and upgrades legacy `sha256$` rows |
| D12 | **Medium** | DRF default permission was `AllowAny`; safety depended on every view remembering to opt in | settings | Default is now `IsAuthenticated`; `CourseViewSet`, `LessonViewSet`, `QuizViewSet`, `api_root`, login and refresh opt in explicitly |
| D13 | **Low** | Login validated the serializer twice (two password-hash computations per login) | code reading | Single validation; the audit event uses the same serializer instance |

### Secondary fixes made alongside

- `redeem_access_code` now runs under `IsAuthenticated` + `RedeemThrottle` (20/hour), locks the code row,
  re-verifies the hash in constant time, and resolves a lost race to the existing grant instead of a 500.
- Access code rows can no longer be created with `max_uses < 1` (DB `CheckConstraint` + `clean()`).
- `AFTER_CLOSE` results are released at read time once `closes_at` passes (previously they were never
  released without manual intervention).
- `QuizViewSet` gains `question_count` and `has_access`; the question count is computed with an annotation,
  removing a per-row `COUNT(*)`.
- Duplicate `NoteViewSet` and `QuizViewSet` definitions (dead code shadowed by later definitions) removed.
- `SECURE_PROXY_SSL_HEADER`, `SECURE_CROSS_ORIGIN_OPENER_POLICY`, HttpOnly/SameSite cookies and a `LOGGING`
  block added.
- `verify_otp` is transactional, locks the OTP row, and increments attempts with an `F()` expression so a
  double-submit cannot exceed `max_attempts`.

---

## 4. File-by-file review

Legend: **P0/P1/P2** = severity of anything outstanding. ✅ = reviewed, no outstanding issue.

### 4.1 Configuration

| File | Lines | Finding |
|---|---|---|
| `config/settings.py` | 261 | **Changed.** Permission default, proxy header, COOP, cookie flags, logging. Remaining **P2:** no `CONN_MAX_AGE` tuning for the free-tier Postgres pool; no `CACHES` backend (throttling falls back to locmem, which is per-process and therefore ineffective with >1 gunicorn worker). |
| `config/urls.py` | 11 | ✅ Unversioned `/api/` prefix retained for compatibility. **P2:** no `/api/v1/` alias, so a future breaking change has no migration path. |
| `config/health.py` | 8 | ✅ Liveness only. **P2:** does not check the database; a pod with a dead DB still reports healthy. |
| `config/wsgi.py`, `asgi.py`, `__init__.py` | 4 / 4 / 0 | ✅ |
| `manage.py` | 8 | ✅ |
| `requirements.txt` | 8 | ✅ DRF pinned `>=3.17.2` (CVE-2026-73228 fixed). **P2:** no lockfile, so builds are not reproducible. |
| `Procfile` | 1 | ✅ Single `web` process. **P2:** no `release` phase for `migrate`. |

### 4.2 Accounts

| File | Lines | Finding |
|---|---|---|
| `accounts/models.py` | 116 | ✅ `Profile` is the role source of truth; OTP stores only a keyed hash. **P2:** custom user model not adopted; `is_staff` and `role` can still diverge (e.g. a role-promoted user without `is_staff` cannot reach admin). |
| `accounts/serializers.py` | 201 | ✅ Password validators applied; registration is case-insensitively unique. **P2:** `CustomTokenObtainPairSerializer.validate` performs two `User.objects.get` lookups plus `check_password` plus `authenticate` (a third hash) — correct, but ~3× the necessary work per login. |
| `accounts/views.py` | 397 | **Changed.** Single validation on login; OTP verification locked and transactional. **P1:** `logout` swallows every exception and returns success even when the refresh token is absent or invalid — a revoked session can look revoked while the token stays valid. |
| `accounts/urls.py` | 18 | ✅ |
| `accounts/admin.py` | 62 | ✅ Reviewed; no self-promotion path for non-main-admins. |
| `accounts/tests.py` | 969 | ✅ Strong coverage of registration, login, OTP, throttling and isolation. **P1:** no test asserts that logout actually blacklists. |
| `accounts/migrations/0001_initial.py` | 61 | ✅ |

### 4.3 Courses — models

| File | Lines | Finding |
|---|---|---|
| `models/catalog.py` | 142 | ✅ `Course`, `CourseFolder`, `Lesson`, `PdfResource`. **P1:** invariants live in `clean()` only, so `objects.create()` and bulk operations bypass them (e.g. a paid course with `price=0`). **P2:** `PdfResource.is_protected` defaults to `True` but nothing forces it for paid courses. |
| `models/access.py` | 182 | **Changed.** HMAC hashing, legacy verification, `max_uses` constraint. ✅ |
| `models/test_engine.py` | 265 | ✅ Snapshot columns are correct. **P1:** no database constraint enforcing one `IN_PROGRESS` attempt per (user, quiz); the API guards it with a lock, but a direct write can still create duplicates. **P2:** `Quiz.clean()` requires a duration for timed modes but nothing requires `closes_at` for `AFTER_CLOSE`. |
| `models/personal.py` | 177 | ✅ Unique constraints on progress/bookmark/revision. **P2:** `Bookmark`/`RevisionItem` use a generic FK with no orphan protection. |
| `models/community.py` | 32 | ✅ |
| `models/common.py`, `models/__init__.py` | 9 / 34 | ✅ |
| `migrations/0001_initial.py` | 433 | ✅ Generated, not hand-edited. |
| `migrations/0002_…access_code_max_uses…` | 19 | **New** in this pass. |

### 4.4 Courses — logic

| File | Lines | Finding |
|---|---|---|
| `courses/policy.py` | 123 | **New.** Single access-decision module. Ordering is deliberate: cheap checks first, so free courses never touch `course.owner` and list views stay at a constant query count. |
| `courses/grading.py` | 141 | **New.** One grading implementation used by both the submit endpoint and the result serializer, so counts and scores cannot disagree. |
| `courses/serializers.py` | 538 | **Changed.** Media gating, question gating, attempt read-only, progress validation, correct-answer fix, section breakdown by topic. **P2:** `BookmarkSerializer.validate` still permits bookmarking a draft lesson owned by someone else (it checks `is_published` then looks for an `owner` attribute that lessons do not have). |
| `courses/views.py` | 1,178 | **Changed.** 13 endpoints hardened; 2 duplicate classes removed. **P1:** `CsvImportJobViewSet.validate` / `confirm_import` are still stubs that flip status without parsing a CSV — they must not ship as "CSV import". **P2:** `StaffQuestionViewSet` / `StaffChoiceViewSet` define serializers inline inside `get_serializer_class`, which defeats introspection and DRF schema generation. |
| `courses/urls.py` | 43 | ✅ Routes match the view layer; attempts no longer resolve to write routes. **P2:** staff routers are not nested under a course, so `course_pk` in `perform_create` is never populated by routing. |
| `courses/admin.py` | 411 | ✅ Reviewed: owner-scoped querysets, FK limiter, ownership immutability on edit, `has_add_permission` for grants disabled. |
| `courses/tests/test_models.py` | 328 | ✅ |
| `courses/tests/test_admin.py` | 228 | ✅ Updated for the new hash prefix. |
| `courses/tests/test_api_security.py` | 583 | **New.** 46 tests covering D1–D13 plus query budgets. |

### 4.5 Frontend

| File | Lines | Finding |
|---|---|---|
| `api.js` | 371 | **P1:** access **and refresh** tokens are stored in `localStorage`. Any XSS — including one introduced by a dependency or a bad template — yields a long-lived refresh token. Recommended: keep the refresh token in an `HttpOnly; Secure; SameSite=Lax` cookie and the access token in memory. **P2:** retry logic does not distinguish a network failure from a 5xx. |
| `app.js` | 383 | ✅ Manual escaping helper used consistently in the reviewed paths. **P2:** `esc()` is hand-rolled; one missed call is an XSS. Prefer `textContent` for all user data. |
| `sw.js` | 113 | ✅ Correctly excludes `/api/`, `/token/`, `/auth/` from the cache. **P2:** no cache-size cap and no background-sync queue for offline progress. |
| `index.html` | 2 (minified) | ✅ No inline scripts. **P2:** single minified line is not reviewable; needs a build step or formatting. |
| `styles.css` | 37 | **P2:** no visible focus styles verified, no `prefers-reduced-motion` handling; WCAG 2.2 AA (target size 24×24, focus not obscured) is unverified. |
| `manifest.webmanifest`, `assets/icon.svg` | 22 / — | ✅ |

### 4.6 Repository

| File | Finding |
|---|---|
| `.github/workflows/backend-checks.yml` | **P0 for process:** the workflow is valid YAML but **has never executed** — every run fails in 2–5 s with no runner allocated, consistent with a billing/plan restriction on the private repository. Treat CI as "not present" until a run is green. |
| `DEPLOYMENT.md`, `README.md` | Reviewed; no secrets committed, instructions match the code. **P2:** deployment steps are untested from this environment. |
| `.gitignore` | ✅ `db.sqlite3`, `.venv`, `staticfiles` excluded. |

---

## 5. Behavioural contracts now enforced

These are the invariants the tests in `courses/tests/test_api_security.py` pin down:

1. **Media requires access.** A `video_url` or protected `file_url` appears in a response only when
   `policy.can_access_course()` is true for the requester. Unauthorised payloads carry `null` plus
   `is_locked: true`, so the UI can show a lock instead of a broken player.
2. **Question papers require access.** Questions and choices are omitted from quiz payloads without access;
   `question_count` and `has_access` remain so the catalogue still renders.
3. **Attempts are server-owned.** No HTTP route can change `status`, `score`, `question_order`,
   `rules_snapshot` or `result_released_at`. Only `submit` and `autosave` write answers.
4. **Grading is database-driven.** The score is computed from persisted answers over the frozen snapshot, so
   autosaved answers count and unanswered questions stay in the denominator.
5. **Progress is an upsert.** Re-posting a lesson returns 200 and updates the row; the lesson is immutable
   after creation and must be published and accessible.
6. **Access codes are MAC-protected.** Codes are matched by HMAC, verified in constant time, upgraded from
   the legacy digest on first use, and can never be created with `max_uses < 1`.
7. **Deny by default.** New DRF views require authentication unless they explicitly opt out.

---

## 6. Open findings

| # | Sev | Area | Issue | Recommended fix | Est. |
|---|-----|------|-------|-----------------|------|
| O1 | **P0 (process)** | CI | Workflow has never run; no automated gate exists | Move to a plan that allows Actions, or run the checks in an external runner; until then require a pasted local test run on every PR | 0.5 d + billing |
| O2 | **P1** | Auth | Logout reports success even when the refresh token is missing/invalid | Return 400 when `refresh` is absent; only report success after `blacklist()` succeeds | 2 h |
| O3 | **P1** | Auth | Refresh token in `localStorage` | Move to `HttpOnly` cookie + in-memory access token; add a `/auth/token/refresh/` that reads the cookie | 1–2 d |
| O4 | **P1** | Data | `clean()`-only invariants bypassed by `objects.create()` / bulk ops | Add DB `CheckConstraint`s for price-vs-mode and quiz duration; add `full_clean()` in admin/serializers | 0.5 d |
| O5 | **P1** | Data | No DB constraint for one `IN_PROGRESS` attempt per (user, quiz) | Partial unique constraint; catch `IntegrityError` and return the existing attempt | 4 h |
| O6 | **P1** | Features | `CsvImportJobViewSet` validate/confirm are stubs | Either implement per `FEATURE_SPEC_TEST_SERIES` (SSRF-safe fetch, size cap, dry run) or remove the endpoints | 2–3 d or 1 h |
| O7 | **P2** | Caching | No shared cache → DRF throttles are per-process | Add Redis (`django-redis`), point `CACHES` at it | 2 h + infra |
| O8 | **P2** | Health | `/healthz/` ignores the database | Add `SELECT 1` and return 503 on failure | 1 h |
| O9 | **P2** | API | Unversioned `/api/` | Add `/api/v1/` and keep `/api/` as an alias | 0.5 d |
| O10 | **P2** | Frontend | Hand-rolled HTML escaping | Render user data with `textContent`; add a CSP | 1 d |
| O11 | **P2** | Accessibility | WCAG 2.2 AA unverified (focus visibility, 24×24 targets, reduced motion) | Audit with axe, fix focus rings and target sizes | 1–2 d |
| O12 | **P2** | Ops | No lockfile; no `release` migrate step in `Procfile` | Pin hashes (`pip-compile`); add `release: python manage.py migrate` | 2 h |

---

## 7. What is still not production-ready

Stated plainly so nobody mistakes this pass for a launch:

- **No CI.** The workflow has never executed. Nothing here is protected against regression by an automated
  gate, only by the local suite.
- **No deployment has ever been performed** from this repository, and no load, backup-restore or failover
  test exists.
- **The frontend is a demo**, not a product: 928 lines across seven static files, no build step, no
  component structure, no accessibility verification, and tokens are held in `localStorage`.
- **No observability backend.** Logging is configured, but nothing ships the logs anywhere and there are no
  metrics or traces.
- **Test-prep features are absent by design.** Rank/percentile, time-per-question analytics, streaks,
  mastery levels, the exam-day simulator, certificates and the AI doubt solver are **not implemented**. They
  are scheduled work, not oversights.
- **The v1 cut line is unchanged:** planner, community feed, admin analytics and R2 media remain later
  milestones.

---

## 8. Verification evidence

All commands were run from `backend/` with the project virtualenv (Python 3.11.2, Django 5.2.18,
DRF 3.17.2).

```
$ python manage.py check
System check identified no issues (0 silenced).

$ python manage.py makemigrations --check --dry-run
No changes detected

$ python manage.py test
Found 142 test(s).
Ran 142 tests in 56.201s
OK

$ ENVIRONMENT=production DEBUG=false SECRET_KEY=<64-char> ALLOWED_HOSTS=app.example.com \
    python manage.py check --deploy
System check identified some issues:
WARNINGS:
?: (security.W021) You have not set the SECURE_HSTS_PRELOAD setting to True.
System check identified 1 issue (0 silenced).
```

`SECURE_HSTS_PRELOAD` is intentionally left off: preloading is effectively irreversible for the domain and
should be a deliberate decision once the production hostname is stable.

### Defects reproduced before the fix

Probe output, captured against `main` @ `fd75b2c` before any change:

```
P1 course-detail status=200 video=True pdf=True lesson=True
P2 quiz-list     status=200 prompt=True choices=True exp=False
P3 anon-start    status=500
P4 patch-attempt status=200 db_status=submitted
P6 dup-progress  first=201 second=500
P7 progress->draft status=200 leak=True
P14 autosave-then-submit status=200 score=0.00 max=0.00
P16 paid-quiz-anon=True
```

Every one of those behaviours is now asserted in the opposite direction by
`courses/tests/test_api_security.py`.

---

## 9. Recommended order of work

1. **O1 — get CI running.** Everything else is unverifiable at the process level until this exists.
2. **O2, O4, O5** — close the remaining integrity gaps; together under two days.
3. **O3** — move the refresh token out of `localStorage` before any public launch.
4. **O6** — decide CSV import: implement it or delete the endpoints. Shipping a stub that reports success is
   worse than not having the feature.
5. **O7, O8, O12** — production hygiene, half a day combined once infrastructure exists.
6. Then resume feature milestones (M-series) in the order already agreed.
