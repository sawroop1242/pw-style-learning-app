# StudySpace Build Status

**Current stage:** Milestone 3 - Authentication API complete  
**Status:** Milestones 1, 2, and 3 verified locally with recorded evidence (96 backend tests green); CI blocked by a platform/billing restriction on the private repository (documented below). Next: Milestone 4 (courses API).  
**Branch:** main  
**Repository:** https://github.com/sawroop1242/pw-style-learning-app

## Environment

- Python 3.13.15, virtualenv at `backend/.venv` (not committed).
- `python -m pip install -r requirements.txt` - exit 0, no errors.
- Versions resolved: Django 5.2.18, djangorestframework 3.16.1, djangorestframework-simplejwt 5.5.1, django-cors-headers 4.9.0, whitenoise 6.12.0, gunicorn 23.0.0, psycopg 3.3.6, dj-database-url 2.3.0.
- Node v24.21.0 (frontend syntax check only).

## Milestone 1 result - verified

Commands run from `backend/` with the venv interpreter:

| Check | Command | Result |
|---|---|---|
| Dependency install | `python -m pip install -r requirements.txt` | Exit 0 |
| Django system check | `python manage.py check` | Exit 0 - "System check identified no issues (0 silenced)" |
| Migration consistency | `python manage.py makemigrations --check --dry-run` | Exit 0 - "No changes detected" |
| Django tests | `python manage.py test` | Exit 0 - "Ran 3 tests ... OK" |
| Python compilation | `python -m compileall -q config courses` | Exit 0 |
| Frontend syntax (separate check) | `node --check frontend/app.js` (repo root) | Exit 0 |

Environment-guard verification in separate clean subprocesses (`import config.settings`):

| Case | Expected | Result |
|---|---|---|
| `ENVIRONMENT=production`, `SECRET_KEY` unset | fail clearly | PASS - ImproperlyConfigured |
| `ENVIRONMENT=production`, `DEBUG=True` | fail clearly | PASS - ImproperlyConfigured |
| `ENVIRONMENT=production`, `ALLOWED_HOSTS` empty | fail clearly | PASS - ImproperlyConfigured |
| `ENVIRONMENT=production`, valid config | start | PASS - starts |
| `ENVIRONMENT=development`, defaults | start | PASS - starts |
| `ENVIRONMENT=staging`, short secret | fail clearly | PASS - ImproperlyConfigured |
| `DEBUG=banana` | fail clearly | PASS - ImproperlyConfigured |

Live runtime smoke test (`manage.py runserver`, ENVIRONMENT=development):
- `GET /healthz/` returns 200 `{"status": "ok"}`; `POST /healthz/` returns 403 (CSRF-protected in dev) - method restricted, GET-only.
- `GET /api/` returns 200 with course/lesson/quiz/notes/progress/token links.
- `GET /admin/login/` returns 200.
- With `ENVIRONMENT=test` (non-debug), HTTP requests correctly 301-redirect to HTTPS.

## CI blocker - documented platform restriction

`.github/workflows/backend-checks.yml` parses as valid YAML (verified with PyYAML). Job steps: checkout, setup Python 3.12, install deps, `manage.py check`, `makemigrations --check --dry-run`, `manage.py test`, `compileall`.

GitHub Actions runs (e.g. run 39002909995, job 117309394255) fail **within ~2 seconds** with:

- `steps: []` - no step ever executed;
- `runner_id: 0`, empty `runner_name` - no runner was ever assigned;
- `started_at` 04:31:51, `completed_at` 04:31:53.

The repository is **private** (`visibility: private`). A job that fails before checkout with no assigned runner on a private repo indicates an Actions billing/spending-limit or Actions-disabled condition on the GitHub account - not a defect in the workflow or the code. Every command the workflow runs passes locally with exit code 0 (table above).

**Action needed from the repository owner:** enable GitHub Actions billing / raise the spending limit (GitHub Settings - Billing) or run CI on a public fork/another runner. This is outside the coding agent's control. The local evidence above stands as the Milestone 1 verification record.

## Milestone 2 changes (in progress)

Extending `backend/courses` models per `docs/FEATURE_SPEC_COURSES_AND_ACCESS_CODES.md`, `docs/FEATURE_SPEC_TEST_SERIES.md`, `docs/FEATURE_SPEC_NOTES_BOOKMARKS_REVISION.md`, `docs/FEATURE_SPEC_STUDY_PLANNER.md`, `docs/FEATURE_SPEC_COMMUNITY_POSTS.md`, and the admin-analytics/audit requirements, with reversible migrations, ownership-scoped admin, and model/admin tests.

## Milestone 2 result - verified

Commands run from `backend/` with the venv interpreter:

| Check | Command | Result |
|---|---|---|
| Django system check | `python manage.py check` | Exit 0 - "System check identified no issues (0 silenced)" |
| Migration consistency | `python manage.py makemigrations --check --dry-run` | Exit 0 - "No changes detected" |
| Django tests | `python manage.py test` | Exit 0 - "Ran 53 tests ... OK" (0 failures, 0 errors) |
| Python compilation | `python -m compileall -q config courses accounts` | Exit 0 |
| Fresh-DB migration | `python manage.py migrate` on empty `db.sqlite3` | Exit 0 - all accounts + courses migrations applied |

Test coverage added (53 total: 33 model tests, 20 admin tests):

- `accounts`: Profile role helpers, signal-cached profile, admin display.
- Model tests: AccessCode hashing/redemption/expiry/max-uses, Lesson folder/course invariant via `clean()`, unique constraints (folder title per course, user-lesson progress, user-course grant, active OTP per user+purpose), role defaults.
- Admin tests: ownership-scoped changelists for sub-admins vs. main admin visibility, owner auto-assignment on create, ownership-reassignment denial, `PrivateDataAdminBase` read-only main-admin-only behavior, admin index access by role, and **cross-owner FK injection denial** - a sub-admin POSTing a foreign course/series ID gets form-validation failure and no object is created (Lesson, AccessCode, TestSeries covered).

Security-relevant admin hardening shipped in this milestone:

- `owner_scoped_fk_querysets()`: every FK on sub-admin forms is restricted to owner-visible rows, so `ModelChoiceField` validation enforces ownership on submit (defense in depth alongside `save_model` checks).
- Sub-admins no longer see or set the `owner` field on Course/TestSeries forms (`get_exclude`); `save_model` still assigns the creator as owner on create and denies reassignment on change.
- `AccessCodeAdmin.fields` drops `uses_count` (redemption counter is server-managed, never hand-edited).
- Static storage: manifest hashing (needed only for far-future cache headers) now applies only when `ENVIRONMENT == "production"`; dev/test use `CompressedStaticFilesStorage`, which fixes admin page rendering without a `collectstatic` manifest.

Live runtime smoke test (`manage.py runserver`, ENVIRONMENT=development): `GET /healthz/` 200, `GET /admin/login/` 200, `GET /api/` 200. Logged-in admin session verified: course changelist 200, access-code add form 200, and a full course creation through the admin (200, persisted with owner set).

## Milestone 3 - Authentication API (complete)

Implements the M3 scope from `IMPLEMENTATION_PLAN.md`: registration with unique normalized username/email and Django password validators, JWT login/logout/refresh with token blacklisting, authenticated password change, email OTP password reset with rate limiting, and audit logging for auth events.

### Endpoints (all under `/api/`)

| Endpoint | Method | Auth | Throttle | Purpose |
|---|---|---|---|---|
| `/api/auth/register/` | POST | anon | 5/min | Create user + profile (role defaults to student) |
| `/api/token/` | POST | anon | 10/min | Login with `username_or_email` + password |
| `/api/token/refresh/` | POST | anon | anon default | Refresh access token |
| `/api/auth/logout/` | POST | JWT | user default | Blacklist refresh token |
| `/api/auth/me/` | GET | JWT | user default | Current user profile (username, email, role, timestamps) |
| `/api/auth/change_password/` | POST | JWT | user default | Authenticated password change, blacklists outstanding refresh tokens |
| `/api/auth/forgot_password/` | POST | anon | 3/hour | Issue 6-digit OTP email (generic response, no user enumeration) |
| `/api/auth/verify_otp/` | POST | anon | 10/min | Verify OTP + set new password (single-use, attempt-limited, atomic) |
| `/api/auth/resend_otp/` | POST | anon | 3/hour | Re-issue OTP, invalidating prior unconsumed codes |

### Security behaviors

- Registration/login accept username or email case-insensitively; emails normalized (lowercase, `EmailValidator`).
- Passwords run through `validate_password` (Django validators incl. `UserAttributeSimilarityValidator` config); weak/new==old/mismatch rejected with field-level errors.
- OTPs are 6-digit, stored only as HMAC-SHA256 hashes keyed on `SECRET_KEY`, expire in 10 minutes, max 5 verify attempts, and only one active OTP per user+purpose (previous codes consumed on reissue).
- Forgot/verify/resend return the same generic response whether or not the account exists - no user enumeration. Email delivery failure is logged (audit `email_failed`) without leaking state.
- JWT config: 30-minute access, 7-day refresh, blacklist app enabled, rotation + blacklist on change-password/logout.
- Every auth event writes an `AuditEvent` row (register, login, logout, password change, OTP issue/verify/fail/resend, email failure) with actor, action, target, outcome, and metadata.

## Milestone 3 result - verified

Commands run from `backend/` with the venv interpreter:

| Check | Command | Result |
|---|---|---|
| Django system check | `python manage.py check` | Exit 0 - "System check identified no issues (0 silenced)" |
| Migration consistency | `python manage.py makemigrations --check --dry-run` | Exit 0 - "No changes detected" |
| Django tests (full suite) | `python manage.py test` | Exit 0 - "Ran 96 tests ... OK" (0 failures, 0 errors) |
| Accounts tests only | `python manage.py test accounts` | Exit 0 - "Ran 43 tests ... OK" |
| Python compilation | `python -m compileall -q config courses accounts` | Exit 0 |

Test coverage added in M3 (43 accounts tests):

- Registration: success, duplicate username/email (case-insensitive), normalization (`TestUser` -> `testuser`), weak/missing-field rejection, profile auto-created with student role.
- Login: username or email, wrong password, unknown user, inactive account, profile data returned.
- Token refresh: valid, invalid; logout blacklists refresh (subsequent refresh 401), logout requires auth.
- `me`: authenticated success, 401 without token.
- Password change: success (old password no longer valid), wrong current password, weak new password, mismatched confirm, old refresh token rejected after change.
- OTP flow: issue on existing email, generic 200 for unknown email, case-insensitive email, prior OTP invalidated on reissue, consumed/expired/wrong-user/max-attempts rejected, resend yields a different code, password actually reset.
- Throttling: register 5/min, login 10/min, forgot 3/hour, OTP verify 10/min all return 429 past their limits.
- Email delivery failure still returns generic 200 and records `email_failed` audit event.
- Tests isolate the shared throttle cache via per-class `@override_settings(CACHES=...)` with distinct `LOCATION`s plus `cache.clear()` in `setUp`, so no cross-test 429s.

## Next step

Milestones 4-6 for the backend in order (courses API, community/study planner, deployment), recording exact command evidence here after each milestone.
