# StudySpace Build Status

**Current stage:** Milestone 2 - data model and Django admin  
**Status:** Milestones 1 and 2 verified locally with recorded evidence (53 backend tests green); CI blocked by a platform/billing restriction on the private repository (documented below). Next: Milestone 3 (auth API).  
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

## Next step

Complete Milestone 2 (models, admin, migrations, tests), then Milestones 3-6 for the backend in order, recording exact command evidence here after each milestone.
