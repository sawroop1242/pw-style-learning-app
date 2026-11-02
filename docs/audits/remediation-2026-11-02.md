# Remediation log — audit of 2026-11-02

This file tracks what was done about
[`pw-style-learning-app-audit-2026-11-02.md`](./pw-style-learning-app-audit-2026-11-02.md).
It exists so a finding can be checked against a commit, a test and a pull
request instead of being taken on trust — the audit's own rule.

**Update this table when a finding closes.** A row without a test name is a
claim, not a fix.

## Status

| # | Finding | Severity | Status | Pinned by | PR |
|---|---|---|---|---|---|
| 1 | Cross-tenant writes at every staff endpoint | **P0** | **Fixed** | `courses/tests/test_tenant_isolation.py` (34) | #26 |
| 2 | Attempts are not immutable paper snapshots; CSV `replace` can delete history | P1 | **Fixed** | `courses/tests/test_attempt_snapshot.py` (14), `test_csv_import.py` | #27 |
| 3 | Multiple-choice questions answerable only as single choice | P1 | **Fixed** | `interact.js` — *multiple choice* block (12 checks) | #28 |
| 4 | Section timing selectable but not implemented | P1 | **Fixed by removal** | `courses/tests/test_quiz_timing.py` (7) | #28 |
| 5 | Pause extends the browser clock, not the server deadline | P1 | **Fixed** | `test_attempt_snapshot.py::DeadlineTests`, `interact.js` — *frozen paper* block | #28 |
| 6 | Username/email uniqueness not enforced by the database | P1/P2 | **Fixed** | `accounts/tests.py::CaseInsensitiveIdentityTests`, `RegistrationTests` | #29 |
| 7 | Superuser role diverges between admin and API | P2 | **Fixed** | `test_tenant_isolation.py::SuperuserParityTests` (4) | #26 |
| 8 | Throttles counted per process | P2 | **Configured + warned** | `accounts/tests.py::SharedCacheCheckTests` (4) | #30 |
| 9 | Token settings diverge from ADR 0004 | P2 | **Fixed** | `config/tests.py::TokenLifetimeTests` | #30 |
| 10 | No Content-Security-Policy | P2 | **Fixed** | `config/tests.py::ContentSecurityPolicyTests` (6) | #30 |
| 11 | CSV fetch has a DNS rebinding window | P2 | **Fixed** | `test_csv_import.py::FetchGuardTests` (8) | #31 |
| 12 | R2 upload pipeline unproven | P2 | **Open** | — | — |

### §6 engineering gaps

| Item | Status | Notes |
|---|---|---|
| 6.1 Frontend CI missing | **Fixed** | `.github/workflows/frontend-checks.yml`; a frontend-only PR now runs `check`, `a11y`, `interact`, `css` |
| 6.2 CI does not exercise PostgreSQL | **Fixed** | `postgres` job in `backend-checks.yml`; migrations + full suite. It caught a real defect in its first run |
| 6.3 Dependencies not reproducibly locked | **Open** | Ranges only; a `pip-compile` lock with hashes is the next step |
| 6.4 "Offline learning" is offline shell support | **Open — wording** | The PWA caches the shell, not API data, deliberately; product copy should say so |
| 6.5 Community is an announcement feed | **Open — scope** | Read-only by design; discussions are a separate milestone |
| 6.6 Admin analytics scope | **Open — scope** | No enrolment/revenue/retention analytics exist; do not advertise them |
| 6.7 No API schema or versioning | **Open** | `/api/v1/` + OpenAPI schema before third-party clients |
| 6.8 Observability gaps | **Open — partial** | Health probes and `manage.py check` exist; request ids, error tracking and alerts do not |

## What each fix actually did

### 1. Tenant isolation (P0)

One resolver — `policy.owner_of` walks `course/series/quiz/question/folder` — and
`TenantParentMixin` checks every writable parent on **create and update** for
folders, lessons, PDFs, access codes, quizzes, questions, choices and faculty.
`IsOwnerOrMainAdmin` now uses the same resolver, so a sub-admin can read and edit
their own question and choice (it used to answer 403 on detail while the list
showed the row). The access-code "paid only" rule moved before `save()`; it used
to run after, so a refused move still moved the row.

### 2. Immutable attempts

`QuizAttempt.paper_snapshot` freezes prompts, options, the key, explanations,
marks and the scoring policy at start; grading and review read only that.
`AttemptAnswer.question` is `SET NULL` with `question_snapshot_id` and
`selected_choice_ids`, so an answer outlives its question.
`allow_replace_with_attempts` is gone — `replace` is refused once a test has
attempts, and a request that still sends the flag is answered `400`
(`bool("false")` is `True`, which is how it deleted results before).

### 3–5. Exam window

Answers are lists; `multiple_choice` renders checkboxes. Pause hides the paper
and lets the clock run (the server's deadline is the only one), and says so.
Section timing is refused by the model and the serializer until sections have a
duration, order and navigation policy — before this, an attempt in that mode had
no deadline at all.

### 6. Identity uniqueness

Functional unique indexes on `LOWER(username)` and `LOWER(email) WHERE email <> ''`,
with a dedupe step for existing rows (`-<id>` / `+dup<id>`), and `IntegrityError`
translated to the field message a form shows.

### 8–10. Production security

Shared Redis cache when `REDIS_URL` is set (`accounts.W005` warns when it is
not), `SIMPLE_JWT` matching ADR 0004, and a CSP with `script-src 'self'` — the
inline scripts and handlers were removed so that directive is true.

### 11. CSV fetch

The validated address is the connected address (`_PinnedHTTPSConnection`),
with `server_hostname` keeping TLS verification on the hostname. Every DNS
answer must be public; one private answer refuses the name.

## How this was verified

- Backend suite on SQLite **and** PostgreSQL 16: `504 tests OK` on both.
- Frontend gates: `check.js` all pages, `a11y.js` clean, `interact.js` 173/173,
  `css.js` clean — now also run in CI.
- Nothing in this table is claimed from source reading alone; every row names a
  test that fails if the behaviour regresses.

Not verified here, and therefore not claimed: the production CSP header and the
R2 pipeline. Production responses could not be inspected from the build sandbox
(TLS to the deployment is blocked), and Cloudflare R2 is unreachable from it — the
same limitation the audit itself had.
