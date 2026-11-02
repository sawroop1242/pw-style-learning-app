# StudySpace / PW-Style Learning App — Engineering Audit Report

**Repository:** [sawroop1242/pw-style-learning-app](https://github.com/sawroop1242/pw-style-learning-app)  
**Branch reviewed:** `main`  
**Reviewed commit:** `adb6ba6d9336f3129fcbd89dd326c35ef21f5d6f`  
**Commit date:** 2 November 2026  
**Repository snapshot:** 254 files  
**Review type:** Read-only source-code, architecture, feature, security, CI and documentation review

---

## 1. Executive summary

StudySpace is no longer just a static learning-app mock-up. The repository contains a meaningful full-stack product foundation:

- A mobile-first, installable PWA built with HTML, CSS and vanilla JavaScript.
- A Django and Django REST Framework backend.
- JWT sign-in, registration, password changes and email OTP password recovery.
- Public course discovery, free-course enrolment and paid-course access-code redemption.
- Provider-owned course content, lessons, folders, PDF resources, faculty and test management.
- A server-scored quiz/test engine with autosave, resumable attempts, guest attempts and result-release rules.
- Notes, progress, bookmarks, revision items, study tasks, community announcements and notifications.
- A multi-account Cloudflare R2 configuration area with encrypted credentials and bucket-purpose selection.
- Backend regression tests and a GitHub Actions workflow.

**Overall assessment:** the project has a useful and increasingly complete feature foundation, but it should not be treated as production-ready for multiple independent course providers yet. The most important risk is inconsistent tenant ownership enforcement in staff write endpoints. A provider may be able to attach or move content to another provider's course/test because some serializers accept related object IDs without rechecking the parent object's owner on create or update.

There are also test-integrity problems: the frontend does not correctly support multiple-choice questions, section-specific timing is not implemented end-to-end, pause behavior can disagree with the server deadline, and historical attempts are not fully immutable even though the model describes them as snapshots.

### Priority verdict

| Priority | Finding | Recommended action |
|---|---|---|
| **P0 — Release blocker** | Staff API does not consistently enforce parent-resource ownership on writes and reassignment | Fix before onboarding independent providers or exposing staff APIs publicly |
| **P1 — Assessment integrity** | Attempt data is not a complete immutable snapshot; CSV replacement can delete old answer rows when explicitly allowed | Fix before using tests for consequential assessment |
| **P1 — Feature correctness** | Multiple-choice questions are presented and submitted as single-choice radio answers | Fix before advertising multiple-answer question support |
| **P1 — Timer correctness** | Section timing is incomplete and client pause can extend only the local timer | Make the server authoritative and define pause rules explicitly |
| **P1/P2 — Identity integrity** | Case-insensitive username/email uniqueness is enforced at serializer level rather than by matching database constraints | Add database constraints and race-condition tests |
| **P2 — Production hardening** | JWTs are stored in `localStorage`; throttling uses the default per-process cache; no CSP is configured | Harden before broad public launch |
| **P2 — Quality gates** | CI does not run frontend checks or a real PostgreSQL test job | Extend CI to cover the whole product |
| **P2 — Storage integration** | R2 account/bucket management exists, but a complete learner-content upload workflow is not established by the inspected paths | Decide and implement the upload/publish pipeline |

---

## 2. Scope and evidence

The review inspected the current `main` tree, README, deployment instructions, feature specifications, ADRs, backend settings, account code, course/test models, serializers, API viewsets, CSV import pipeline, R2 integration, frontend API client, player/test-player code, service worker, tests and workflow configuration.

The branch was refreshed after PR #23 merged. The latest commit is `adb6ba6d`, titled **“A paid batch has a Get code button that opens the teacher's Telegram DM”**. Recent merged work also includes the multi-account R2 panel, explicit free-course enrolment, PDF reader improvements, and course-section administration.

### CI evidence

The newest observed GitHub Actions run for the reviewed commit was **run `41479628365`**, and it was successful. Its job completed:

- Dependency installation.
- Django system check.
- `makemigrations --check --dry-run`.
- Django test suite.
- Python module compilation.

This is positive evidence that the backend test suite and migration checks passed in that CI run. The README advertises 155 tests, while the workflow result exposed only the test-step success status—not a separately verified count. The workflow does **not** currently execute the frontend check suite, a browser test, a PostgreSQL service test, a dependency vulnerability audit, or a security scan.

### Important limitations

This was a read-only GitHub source review. I did not modify the repository, run the Django server locally, execute a live exploit against a deployed environment, test real Cloudflare credentials, send email through a real provider, or test the app on physical Android/iOS devices. The authorization findings below are grounded in the current permission classes, viewsets and serializers; they should be turned into regression tests and verified in a controlled test environment before being marked fixed.

---

## 3. Current architecture

### 3.1 Frontend

`frontend/` contains a framework-free PWA. It uses:

- HTML pages for the landing page, course catalogue, course detail, class player, PDF reader, tests, test player, dashboard, login, community, profile and legal pages.
- Shared CSS tokens, base styles, components and page/screen styles.
- ES modules under `frontend/assets/js/` for the API client and page-specific behaviors.
- A web app manifest and service worker.

The frontend does not use a React/Vue framework or a production bundler. This keeps the app lightweight and simple to host, but increases the importance of consistent DOM escaping, browser testing and reliable API contracts.

### 3.2 Backend

`backend/` is a Django project with three product apps and a configuration package:

| Module | Responsibility |
|---|---|
| `accounts` | Profiles, roles, authentication, OTP password reset, mail delivery and audit events |
| `courses` | Courses, folders, lessons, PDFs, access grants/codes, quizzes, attempts, notes, progress, tasks, notifications and CSV import |
| `objectstore` | Cloudflare R2 accounts, buckets, encrypted credentials, signing and storage checks |
| `config` | Django settings, URLs, health endpoints, pagination and deployment configuration |

The API uses Django REST Framework and SimpleJWT. SQLite is used for local development by default; `DATABASE_URL` allows PostgreSQL deployment. The frontend calls the API through a shared client in `frontend/assets/js/core.js`.

### 3.3 Security model

The intended product is multi-provider:

- Students consume published courses and tests.
- Sub-admins manage their own provider content.
- Main admins manage the whole platform.
- Paid batches are unlocked through course-bound access codes.
- Student data such as notes, progress and tasks is private to the student.

This architecture is appropriate for the product, but it relies on every staff endpoint applying the same ownership rules. The current implementation does not do that consistently; see Finding 1.

---

## 4. Feature inventory — what is implemented

The statuses below distinguish code that is visibly present from functionality that remains incomplete or needs deployment verification.

| Feature area | Current implementation | Assessment |
|---|---|---|
| PWA shell | Manifest, icons, responsive pages, service worker and offline fallback | Implemented |
| Offline behavior | Static shell and assets can be cached; API requests are network-only | Implemented as shell-only offline support, not full offline learning |
| Account registration | Username/email/password registration and profile creation | Implemented |
| Login | JWT login accepts username or email | Implemented; database uniqueness needs hardening |
| Password reset | OTP generation, keyed hash storage, expiry, attempt limits, resend throttling and email-provider support | Implemented; real provider delivery still needs deployment verification |
| Password change/logout | Authenticated password change and refresh-token invalidation paths | Implemented, with logout error-handling caveat |
| Provider roles | Student, sub-admin and main-admin profile roles | Implemented, but API superuser handling differs from admin-console helpers |
| Course catalogue | Published courses, search/filter/order, course details, price, subject and artwork | Implemented |
| Course sections | Course folders/sections and lessons grouped under them | Implemented |
| Video player | Native video path and approved embed-host iframe path | Implemented for supported hosts and valid links |
| PDF resources | PDF metadata, reader URL and protected URL withholding | Implemented; relies on the source host's embed permissions or an accessible URL |
| Free enrolment | Explicit student enrolment with idempotent response for repeat taps | Implemented; concurrent first-enrolment race should be tested |
| Paid access | One-time or limited-use course access codes, revocation, expiry and grants | Implemented |
| Telegram contact | Paid-course “Get code” flow opening a prefilled teacher DM | Added in merged PR #23 |
| Test series | Test series, quiz, question and choice data models and staff APIs | Implemented, with staff-ownership issues below |
| CSV import/export | HTTPS URL fetch, file-size/row limits, schema validation, digest verification, all-or-nothing import | Implemented; harden SSRF DNS-rebinding and boolean parsing |
| Quiz attempts | Server-created attempts, guest tokens, autosave, submit, result release and answer review | Implemented, but test integrity gaps remain |
| Notes/progress | User-owned notes and lesson progress | Implemented |
| Bookmarks/revision | User-owned generic resource references | Implemented |
| Study planner | User-owned study tasks with complete/reopen actions | Implemented |
| Community | Read-only published announcement feed | Implemented as an announcements feed; not a full social network |
| Notifications | Derived notifications and per-user read receipts | Implemented |
| R2 management | Multiple accounts/buckets, purpose flags/defaults, encrypted credentials and connection checks | Management layer implemented; end-to-end content upload path not established by this audit |
| Admin interface | Customized staff console and owner-scoped admin operations | Implemented; ensure admin and API permission rules remain consistent |

### Product decisions that appear intentional

- The product is not affiliated with Physics Wallah; it is PW-inspired only.
- Paid batches do not currently have a native payment checkout. A teacher/provider supplies an access code, and Telegram contact helps a student request one.
- The service worker caches the application shell, not private API responses or student data.
- The CSV importer downloads a URL supplied by staff rather than accepting a file upload through the API.

These are valid product choices, provided the UI and documentation describe them accurately.

---

## 5. Verified and suspected defects

### Finding 1 — Staff API tenant ownership is inconsistent

**Severity: P0 — release blocker for multi-provider operation**  
**Confidence: high from source inspection; runtime regression proof still required**

The repository has owner-scoped querysets and object permission classes, but several create/update paths accept writable parent IDs without checking that the referenced parent belongs to the current sub-admin.

#### Affected paths

| Endpoint / resource | Source-level problem |
|---|---|
| `POST/PATCH /api/staff/quizzes/` | `StaffQuizViewSet` uses `QuizSerializer`, whose `course` and `series` fields are writable. The viewset scopes its queryset for reads but does not validate course/series ownership on create or reparenting updates. |
| `POST /api/staff/questions/` | The create serializer accepts a writable `quiz` relationship. There is no `perform_create` ownership check for the submitted quiz. |
| `POST /api/staff/choices/` | The create serializer accepts a writable `question` relationship. There is no `perform_create` check that the question's quiz belongs to the provider. |
| `PATCH /api/staff/folders/{id}/` | `CourseFolderSerializer.course` is writable. Creation checks ownership, but the update path does not repeat the ownership check for a new course. |
| `PATCH /api/staff/lessons/{id}/` | The update path checks that the folder belongs to the selected course, but does not verify that the new course belongs to the current provider. |
| `PATCH /api/staff/pdfs/{id}/` | `StaffPdfResourceSerializer.folder` is writable. Creation checks ownership, but there is no equivalent update check for a new folder. |
| `PATCH /api/staff/access-codes/{id}/` | `AccessCodeSerializer.course` is writable. Creation checks course ownership, but an update can reassign an existing code to another course without a second ownership check. |
| `PATCH /api/staff/faculty/{id}/` | `StaffCourseFacultySerializer.course` is writable. Creation checks course ownership, but update does not repeat it. |

A provider could therefore potentially inject or move content into another provider's course/test, or reassign an access code. That violates the platform's most important multi-tenant security boundary.

There is a second defect in the same area: `IsOwnerOrMainAdmin` checks `obj.owner` or `obj.course`, but does not traverse `Question.quiz.owner` or `Choice.question.quiz.owner`. Sub-admins can therefore be denied detail/update operations on their own question/choice records even though the list querysets include those records.

#### Required fix

1. Centralize ownership checks in a reusable service/helper that resolves the real parent chain for every resource type.
2. Validate ownership on **every create and update**, not only when a record is first created.
3. Make parent fields read-only on update where reassignment is not a real product requirement.
4. If reassignment is permitted, require that both the old and new parents are authorized and that the move is transactionally safe.
5. Make object permission checks understand `Question → Quiz → Course/Series` and `Choice → Question → Quiz → Course/Series`.
6. Add tests for foreign-parent create, foreign-parent update, same-owner update, main-admin access and sub-admin detail/edit access for every affected resource.

**Acceptance criteria:** a sub-admin cannot create, update, reparent, publish or revoke a resource under another provider's course or test, even when the request submits a valid foreign database ID. A sub-admin can still read and edit their own questions and choices.

Relevant source: [staff parent/resource viewsets](https://github.com/sawroop1242/pw-style-learning-app/blob/main/backend/courses/views.py#L130-L430), [quiz/question/choice viewsets](https://github.com/sawroop1242/pw-style-learning-app/blob/main/backend/courses/views.py#L1090-L1205), [staff serializers](https://github.com/sawroop1242/pw-style-learning-app/blob/main/backend/courses/serializers.py#L90-L180).

### Finding 2 — Quiz attempts are not fully immutable snapshots

**Severity: P1 — assessment integrity**  
**Confidence: high from source inspection**

The `QuizAttempt` model stores `question_order` and `rules_snapshot`, which is a good start. However, the snapshot does not freeze the complete paper:

- Question IDs are saved, but prompt text and option text are not copied into an attempt-specific snapshot.
- The answer rows refer to live `Question` and `Choice` objects.
- `grading.grade_attempt()` reads current question marks, negative marks, topic and current correct choices.
- Quiz-level scoring defaults and pass threshold are read from the current `Quiz` during result serialization.
- Result review reads the current question explanation and choices.
- `rules_snapshot` is written at attempt start but is not used as the complete source of truth for grading.

The CSV importer also has a `replace` mode. The importer correctly protects tests with attempts by default, but it exposes `allow_replace_with_attempts`. When enabled, replacing questions deletes the old Question rows; related `AttemptAnswer` rows use cascading deletion. Historical result data can therefore be lost or changed.

There is an additional parsing hazard in `confirm_import`: `bool(request.data.get("allow_replace_with_attempts"))` treats any non-empty string—including the text `"false"`—as `True`.

#### Required fix

- Store an immutable per-attempt paper snapshot containing question prompt, question type, choices, answer key, explanation, section/topic, marks, negative marks, order and scoring policy.
- Grade from that immutable snapshot, never from subsequently edited question-bank records.
- Keep attempts and answer details independent of question-bank deletion; use stable snapshot IDs or versioned question records.
- Remove `allow_replace_with_attempts` as a way to delete historical assessment data. Prefer creating a new quiz version.
- Parse booleans strictly with a serializer field rather than Python truthiness.

**Acceptance criteria:** editing or deleting a question after a student starts a test cannot change that student's paper, score, answer sheet or explanations. A previously submitted attempt remains reviewable after the question bank is revised.

Relevant source: [attempt model](https://github.com/sawroop1242/pw-style-learning-app/blob/main/backend/courses/models/test_engine.py#L173-L246), [attempt start](https://github.com/sawroop1242/pw-style-learning-app/blob/main/backend/courses/views.py#L1479-L1590), [grading](https://github.com/sawroop1242/pw-style-learning-app/blob/main/backend/courses/grading.py#L1-L145), [CSV replacement/import](https://github.com/sawroop1242/pw-style-learning-app/blob/main/backend/courses/csv_import.py#L600-L668), [CSV confirmation](https://github.com/sawroop1242/pw-style-learning-app/blob/main/backend/courses/views.py#L1358-L1425).

### Finding 3 — Multiple-choice questions cannot be answered correctly in the frontend

**Severity: P1 — visible feature correctness bug**  
**Confidence: high**

The backend and CSV schema support `multiple_choice`; the grading engine expects a set of selected choice IDs. The frontend, however:

- Stores one choice ID per question in a `Map`.
- Renders every option as `<input type="radio">`.
- Replaces the previous selection when a new option is selected.
- Sends either one selected choice ID or an empty array on autosave and submission.

A learner therefore cannot select two or more answers, even for a multiple-choice question. The backend support is not enough; the user-facing implementation is functionally single-choice.

#### Required fix

- Use a `Set` or array of choice IDs per question.
- Render checkboxes for `multiple_choice`, radio buttons for `single_choice` and `true_false`.
- Update clear-answer, keyboard selection, palette status, autosave, local persistence and final submit logic to handle arrays.
- Add frontend interaction tests for one selected answer, several selected answers, deselection, clearing and reload/resume.

Relevant source: [question type and options rendering](https://github.com/sawroop1242/pw-style-learning-app/blob/main/frontend/assets/js/test-player.js#L600-L710), [autosave and submit payloads](https://github.com/sawroop1242/pw-style-learning-app/blob/main/frontend/assets/js/test-player.js#L850-L890), [backend grading rules](https://github.com/sawroop1242/pw-style-learning-app/blob/main/backend/courses/grading.py#L25-L100).

### Finding 4 — Section-specific timing is not implemented end-to-end

**Severity: P1 if section timing is a promised exam feature**  
**Confidence: high from model and attempt-start code**

The `Quiz.TimingMode` enum includes `SECTION_TIMED` and `TOTAL_AND_SECTION`, but the current data model has no dedicated `Section` entity or per-section duration/ordering settings. A question's `topic` is used as a display and result-breakdown group; it is not a full section-timing configuration.

At attempt creation, a server deadline is created for `TIMED` and `TOTAL_AND_SECTION` when a total duration exists. `SECTION_TIMED` is not included in that deadline condition. `TOTAL_AND_SECTION` currently has a total deadline only; no per-section server deadlines are stored or enforced.

#### Required fix

Either remove/disable section-timed modes until they work, or implement:

- A real section model or explicit section configuration.
- Section order, duration and navigation rules.
- Server-side section start/end timestamps and enforcement.
- Resume behavior that reconstructs the active section and remaining time.
- Attempt snapshots of section configuration.
- Tests for changing sections, returning to a section, expiry, pause policy and refresh.

Relevant source: [Quiz timing modes](https://github.com/sawroop1242/pw-style-learning-app/blob/main/backend/courses/models/test_engine.py#L33-L119), [attempt creation/deadline logic](https://github.com/sawroop1242/pw-style-learning-app/blob/main/backend/courses/views.py#L1479-L1590).

### Finding 5 — Pause extends the browser clock but not the server deadline

**Severity: P1 — risk of rejected autosave/submission**  
**Confidence: high**

The test player pauses its local timer and, when resumed, adds the pause duration to `state.deadline`. The comment in the frontend acknowledges that a scheduled/server-scored test still expires on the original server deadline. The API checks the original `QuizAttempt.deadline` when autosaving and submitting.

A learner can therefore see time remaining in the browser while the API rejects a save or final submission because the server considers the attempt expired. This is especially confusing if the user expects pause to stop the timer.

#### Required fix

Choose one explicit policy:

- **Exam mode:** pause is visual-only and does not extend the server deadline; label it accordingly and keep the browser clock aligned to the server.
- **Practice mode:** support server-authorized pause/resume and persist pause intervals or an adjusted server deadline.

Never allow the client alone to modify its authoritative deadline. Add tests for autosave immediately before/after expiry and pause/resume around the expiry boundary.

Relevant source: [frontend pause/resume logic](https://github.com/sawroop1242/pw-style-learning-app/blob/main/frontend/assets/js/test-player.js#L930-L1010), [server autosave/submit deadline checks](https://github.com/sawroop1242/pw-style-learning-app/blob/main/backend/courses/views.py#L998-L1098).

### Finding 6 — Username/email uniqueness is not protected at the database layer

**Severity: P1/P2 — account consistency and recovery risk**  
**Confidence: high from model/serializer design**

Registration normalizes email and checks case-insensitive uniqueness in the serializer. The ADR explicitly keeps Django's default User model and acknowledges that email uniqueness is enforced at application level. There is no database uniqueness constraint for case-insensitive email (and the same general race applies to the case-insensitive username check).

Two concurrent registration requests can both pass the `.exists()` check and create accounts with case-variant duplicates. The login serializer uses `.get(email__iexact=...)`; duplicate rows can lead to `MultipleObjectsReturned`. The password-reset flow detects an ambiguous email and refuses to send a reset code, which prevents an account-reset ambiguity but does not solve the duplicate-account problem.

#### Required fix

- Audit and deduplicate existing accounts first.
- Add database-level unique constraints for normalized email and username (for PostgreSQL, a unique expression/index such as `Lower(email)` and `Lower(username)`, or dedicated normalized columns).
- Catch `IntegrityError` and return a clean validation response.
- Add concurrent registration and case-variant login/reset tests.

Relevant source: [registration/login serializers](https://github.com/sawroop1242/pw-style-learning-app/blob/main/backend/accounts/serializers.py#L1-L135), [user model and profile](https://github.com/sawroop1242/pw-style-learning-app/blob/main/backend/accounts/models.py#L1-L50), [user identity ADR](https://github.com/sawroop1242/pw-style-learning-app/blob/main/docs/adr/0001-user-model-email-uniqueness.md).

### Finding 7 — Django superuser handling differs between the admin console and API

**Severity: P2 — administrator access inconsistency**  
**Confidence: high**

The account-role helper functions in `accounts/roles.py` explicitly treat `is_superuser` as main-admin/staff. The staff API permission and course policy helpers rely on `Profile.role`; a Django superuser whose auto-created profile still has the student role may be able to open the Django admin console but fail staff API authorization or be treated as a normal user by course policy.

#### Required fix

Use one central role/authorization service in both the Django admin and API. Add a test for a superuser with a student-role profile, a main-admin profile, a sub-admin profile and a normal student.

Relevant source: [admin role helpers](https://github.com/sawroop1242/pw-style-learning-app/blob/main/backend/accounts/roles.py), [API role policy](https://github.com/sawroop1242/pw-style-learning-app/blob/main/backend/courses/policy.py#L30-L60), [staff permission classes](https://github.com/sawroop1242/pw-style-learning-app/blob/main/backend/courses/views.py#L130-L160).

### Finding 8 — Throttling is not distributed across application instances

**Severity: P2 — production abuse resistance**  
**Confidence: high from settings**

The settings define per-IP/per-user DRF throttles and additional authentication/OTP throttle classes. However, no shared cache backend is configured in `backend/config/settings.py`, so Django uses its local-memory default unless the deployment overrides it elsewhere.

With multiple serverless instances or multiple web workers, each instance can maintain a separate throttle counter. A client can therefore receive more attempts than the configured global limit by reaching different instances. The current throttles should not be treated as a strong distributed abuse-control boundary.

#### Required fix

Configure Redis or another shared cache in production, verify the selected cache is shared by all instances, and add edge/WAF rate limits for login, OTP, registration and public attempt creation. Keep the application-level checks too.

Relevant source: [DRF permissions and throttle configuration](https://github.com/sawroop1242/pw-style-learning-app/blob/main/backend/config/settings.py#L180-L225), [auth throttles](https://github.com/sawroop1242/pw-style-learning-app/blob/main/backend/accounts/views.py#L30-L100).

### Finding 9 — JWT and guest-attempt tokens are held in browser storage

**Severity: P2 — browser-side credential exposure**  
**Confidence: high**

The frontend stores the access token, refresh token and guest attempt token in `localStorage`. Any successful script injection running in the app origin can read them. The inspected code uses an escaping helper in many dynamic HTML templates, which is good, but the architecture still means an XSS flaw can expose long-lived authentication material.

#### Required fix

Prefer an HttpOnly, Secure, appropriately SameSite cookie/BFF arrangement where practical. If the SPA token arrangement is retained, implement a strict Content Security Policy, avoid unsafe HTML sinks, audit all template interpolation and third-party scripts, keep access-token lifetimes short and rotate/revoke refresh tokens as intended by the ADR. Confirm the SimpleJWT runtime settings match the accepted token-storage ADR; the ADR's explicit lifetime/rotation values were not present in the inspected `settings.py`.

Relevant source: [browser token storage](https://github.com/sawroop1242/pw-style-learning-app/blob/main/frontend/assets/js/core.js#L1-L65), [token-storage ADR](https://github.com/sawroop1242/pw-style-learning-app/blob/main/docs/adr/0004-token-storage.md), [Django security settings](https://github.com/sawroop1242/pw-style-learning-app/blob/main/backend/config/settings.py#L230-L285).

### Finding 10 — Content Security Policy is not configured

**Severity: P2 — defense in depth**  
**Confidence: high from settings/deployment review**

The backend configures several useful security headers, but no CSP middleware/header is present in the inspected settings. The deployment guide describes CSP as an optional nginx header, but the inspected Django settings and `vercel.json` do not configure an enforced CSP. A hosting layer could add one separately; verify the deployed response headers rather than assuming it is present.

#### Required fix

Define and test a CSP suitable for the app's own scripts, API origin, video embed providers, PDF hosts and images. Start with report-only mode, collect violations, then enforce. Do not blindly block the legitimate video/PDF providers the app supports.

Relevant source: [Django security settings](https://github.com/sawroop1242/pw-style-learning-app/blob/main/backend/config/settings.py#L230-L285), [deployment security checklist](https://github.com/sawroop1242/pw-style-learning-app/blob/main/DEPLOYMENT.md#https--security).

### Finding 11 — CSV URL import has good SSRF controls, but DNS rebinding deserves hardening

**Severity: P2 — controlled server-side fetch risk**  
**Confidence: medium; residual risk, not a demonstrated exploit**

The importer has several correct defenses: HTTPS-only URLs, public-IP DNS checks, rejection of private/loopback/link-local/multicast addresses, redirects disabled, a bounded timeout and a 2 MiB response cap. That is a strong baseline.

The remaining concern is a DNS time-of-check/time-of-use gap: the app resolves the hostname for validation and then `urllib` may resolve it again when opening the connection. A deliberately rebinding DNS name could theoretically return a public IP during validation and a private IP at connection time.

#### Required fix

Pin the actual validated address for the connection while preserving TLS hostname verification, or route the fetch through a trusted egress proxy/allowlist. Revalidate every resolved address and keep redirects disabled. Add tests for mixed public/private DNS answers, rebinding behavior and unusual URL forms.

Relevant source: [CSV SSRF guard and fetcher](https://github.com/sawroop1242/pw-style-learning-app/blob/main/backend/courses/csv_import.py#L292-L350).

### Finding 12 — R2 configuration exists, but the end-to-end content pipeline is not proven

**Severity: P2 — product completeness / operational gap**  
**Confidence: medium; source-review limitation**

The `objectstore` app includes encrypted credentials, account/bucket administration, purpose flags, default bucket selection, connection checks, SigV4 signing and URL generation. This is meaningful implementation, not just a placeholder.

The course models still expose URL fields for images, videos and PDFs. The code paths inspected do not establish a complete learner-content upload pipeline that takes an admin-selected file, writes it to the resolved purpose bucket, persists a stable object key and delivers a protected or public learner URL. The R2 management subsystem should not yet be presented as proof that all course assets are automatically uploaded and served through R2.

#### Required fix

Define a single upload service for image/video/PDF assets. It should enforce file type and size, generate collision-resistant object keys, resolve the correct owner/purpose bucket, upload and verify the object, store an object key rather than a long-lived credential-bearing URL, and deliver either a controlled public URL or short-lived signed URL based on course access.

Relevant source: [R2 credential encryption](https://github.com/sawroop1242/pw-style-learning-app/blob/main/backend/objectstore/crypto.py), [R2 account/bucket models](https://github.com/sawroop1242/pw-style-learning-app/blob/main/backend/objectstore/models.py#L58-L302), [R2 storage service](https://github.com/sawroop1242/pw-style-learning-app/blob/main/backend/objectstore/services.py).

---

## 6. Additional engineering and product gaps

These are not all immediate defects, but they should be considered before describing the application as a mature production learning platform.

### 6.1 Frontend CI is missing

The current GitHub Actions workflow is a backend workflow. Its trigger paths cover backend files and the workflow file. The repository has a committed frontend check suite (`check.js`, `a11y.js`, `interact.js`, `css.js`, and `live.js`), but those checks are not part of the current workflow.

As a result, a frontend-only PR can change the test player, player, navigation, CSS or PWA behavior without triggering the backend checks. This is a major regression-risk gap for a product whose primary experience is the frontend.

**Recommendation:** add a Node CI job that installs the lockfile and runs all deterministic frontend checks on frontend, tools/checks and shared API-contract changes. Run the live API contract job against a test server as a separate integration step.

### 6.2 CI does not exercise PostgreSQL behavior

The workflow installs Python dependencies and runs Django tests, but it does not provision a PostgreSQL service. The test environment therefore does not validate production PostgreSQL behavior, constraints, indexes or row-lock semantics.

This matters because the app uses `select_for_update()` for OTP consumption, access-code redemption and attempt submission. SQLite does not provide the same row-level locking behavior as PostgreSQL. Add a PostgreSQL CI job for migrations and high-risk transactional tests.

### 6.3 Dependencies are range-constrained, not reproducibly locked

The root requirements use version ranges. This allows compatible updates, but a future clean install can resolve to different versions within those ranges. Use a lockfile or a compiled requirements file with hashes and schedule dependency audits.

The current Django REST Framework range is `>=3.17.2,<3.18`, so the earlier documentation concern about resolving to an older 3.16 release is no longer applicable to this snapshot.

### 6.4 Full offline learning is not implemented

The service worker correctly avoids caching API responses. This protects private student data, but it also means offline learners cannot depend on live API functions such as notes, progress synchronization, test start, autosave or course access. The current feature should be called **offline shell support**, not a full offline learning mode.

If full offline study is a future goal, design a deliberate per-user encrypted local queue, conflict resolution and server synchronization. Do not simply cache authenticated API responses in a shared service-worker cache.

### 6.5 Community is an announcement feed, not a social community

The public community viewset is read-only and lists published posts. This is enough for announcements, but not a student discussion product with member posts, replies, moderation queues, reports, reactions and abuse controls. Keep the product description precise or build those capabilities as a separate milestone.

### 6.6 Admin analytics need a clearly defined scope

The student dashboard includes test/progress/task-related information, and staff can manage content and question reports. A complete provider analytics subsystem—enrolment trends, access-code redemption history, revenue/payment records, learner retention, batch completion and CSV exports—should be treated as a separate feature set unless those metrics are explicitly implemented and tested.

### 6.7 API documentation and versioning

The repository contains API routes but no evidence in the inspected configuration of a generated OpenAPI schema, browsable API contract export or a versioned `/api/v1/` namespace. Add an API schema and contract tests before third-party clients or mobile native apps depend on the API.

### 6.8 Observability and operations

Django logging is configured, but a production service also needs structured request IDs, exception monitoring, alerting, background-job visibility and operational dashboards. Email and R2 have checks, but database backups/restore drills, migration rollback procedure and error-budget monitoring should be explicitly documented and exercised.

---

## 7. Recommended implementation roadmap

Do not start by adding more visible UI. First make the tenant and assessment foundations reliable.

### Sprint 0 — Security hotfix: tenant isolation

**Goal:** make every provider write safe.

1. Audit every staff viewset with a writable foreign key or parent object.
2. Centralize parent ownership validation.
3. Make fields read-only where parent reassignment is not required.
4. Fix object-level checks for Question and Choice parent chains.
5. Add negative tests for foreign IDs and cross-provider reparenting.
6. Add tests for superuser/main-admin/sub-admin/student parity.

**Exit criteria:** cross-provider create/update/reparent operations all return 403 or 404; providers retain full CRUD for their own resources; main admins retain intended global access.

### Sprint 1 — Assessment correctness

**Goal:** ensure the test UI and server agree.

1. Implement multiple-choice selection in the frontend.
2. Implement complete attempt snapshots and grade exclusively from them.
3. Prevent replacement/deletion from destroying old attempt data.
4. Implement section timing or disable the section-timed options until complete.
5. Resolve client/server pause deadline mismatch.
6. Add concurrency and expiry tests on PostgreSQL.

**Exit criteria:** multi-answer tests can be attempted, saved, resumed and graded correctly; old attempts remain unchanged after edits; server is the only authority for timer and result state.

### Sprint 2 — Identity and production security

**Goal:** harden account and browser security.

1. Add normalized database uniqueness for email and username.
2. Handle integrity races cleanly in registration.
3. Verify SimpleJWT settings against ADR 0004 and explicitly configure lifetimes, rotation and blacklist behavior.
4. Evaluate HttpOnly cookie/BFF token handling.
5. Add a tested CSP.
6. Configure Redis/shared cache and edge rate limits.
7. Add audit-log retention/redaction rules and test secret redaction.

**Exit criteria:** duplicate case-variant accounts cannot be created, rate limits are shared across instances, and tokens/secrets are not exposed through browser storage or logs beyond the accepted threat model.

### Sprint 3 — CI and release quality

**Goal:** make every important code change testable before merge.

1. Add frontend CI for accessibility, CSS, interaction and page boot checks.
2. Add a PostgreSQL-backed migration and test job.
3. Add dependency audit, static analysis and coverage reporting.
4. Add API schema generation and contract validation.
5. Add staging smoke tests for registration, login, password reset, course access, PDF/video authorization and test submission.
6. Add backup/restore and deployment rollback exercises.

**Exit criteria:** backend and frontend checks run on relevant PRs, critical flows pass in CI, and production readiness is measured against an explicit checklist.

### Sprint 4 — Finish content delivery and learner experience

**Goal:** make the product usable at scale.

1. Finish the R2 upload/publish/read pipeline.
2. Add media type/size validation, signed URL lifecycle and access revocation tests.
3. Define whether offline support remains shell-only or becomes an explicit offline-learning feature.
4. Define the scope of provider analytics and community interactions.
5. Add API versioning and public API documentation.
6. Add performance budgets for catalog pages, course details, quiz payload size and test autosave latency.

---

## 8. Minimum regression test matrix

The following tests should be mandatory before the next production release.

| Area | Test | Expected result |
|---|---|---|
| Tenant security | Sub-admin creates quiz on another provider's course | Rejected |
| Tenant security | Sub-admin creates question on another provider's quiz | Rejected |
| Tenant security | Sub-admin creates choice on another provider's question | Rejected |
| Tenant security | Sub-admin moves an owned lesson to a foreign course | Rejected |
| Tenant security | Sub-admin moves PDF/access code/faculty/folder to foreign parent | Rejected |
| Tenant security | Sub-admin edits own question/choice detail | Allowed |
| Tenant security | Main admin accesses all tenant resources | Allowed according to policy |
| Identity | Concurrent signups using case variants of one email | Exactly one account created |
| Identity | Login for a duplicate legacy email | No unhandled 500; safe remediation response |
| Quiz | Multiple-choice question selects two correct answers | Both saved and graded correctly |
| Quiz | Multiple-choice question with one missing correct option | Graded incorrect according to exact-set rules |
| Quiz | Edit question after an attempt starts | Existing attempt remains unchanged |
| Quiz | Replace a paper with existing attempts | Old attempts remain reviewable; no destructive cascade |
| Timing | Section-timed quiz crosses section deadline | Server enforces configured section behavior |
| Timing | Client pauses past original deadline | Behavior matches the declared pause policy |
| Access | Anonymous learner requests paid video/PDF URL | URL withheld |
| Access | Enrolled learner requests protected media | URL or authorized access granted |
| Access | Revoked grant requests protected media | Access denied |
| CSV | URL resolves to private/loopback address | Rejected |
| CSV | URL redirects to a private host | Redirect rejected |
| CSV | DNS rebinding/mixed DNS answers | Private address cannot be reached |
| CSV | `allow_replace_with_attempts="false"` | Interpreted as false, never truthy by string conversion |
| R2 | Invalid credentials/key rotation | Safe error; secrets never shown |
| R2 | Upload/verify/private signed read | Correct owner/purpose bucket and access policy used |
| PWA | API unavailable/offline | No private API response is served from cache |
| CI | Frontend-only PR | Frontend checks run |
| CI | PostgreSQL migration/transaction tests | Pass on real PostgreSQL service |

---

## 9. Documentation that needs reconciliation

Some existing audit documents describe an earlier state of the repository and should not be treated as the current implementation baseline.

The README also appears to lag behind the frontend: it describes a `data.js` fixture fallback through a `live(path, fixture)` helper, while the current `core.js` describes an API client with no invented fixture fallback and the current shared editorial copy is in `content.js`. Update the README's frontend/API behavior and project tree so a new developer is not given an incorrect mental model.

- `docs/ARCHITECTURE_AND_FEATURE_REVIEW.md` is dated 20 October 2026 and describes a much earlier milestone-2 skeleton. It says that registration, access-code redemption, quiz submission, and connected frontend behavior are missing. Those statements are no longer accurate for the current `main` branch.
- `docs/PRODUCTION_READINESS_AUDIT.md` includes older findings that the CSV importer was a stub. The current code has a real CSV URL fetch, parser, validation report, digest check and transactional importer.
- `README.md` still contains a feature/milestone summary that should be checked against the current source and current roadmap.

Recommended documentation structure:

1. Keep one current `docs/ARCHITECTURE.md` for architecture and trust boundaries.
2. Keep one current `docs/PRODUCTION_READINESS.md` for open risks and release criteria.
3. Keep feature specifications for work that has not been implemented or that still requires acceptance tests.
4. Mark old audits as historical snapshots and link to the current audit rather than allowing them to look authoritative.
5. Add a feature-status field to every spec: `planned`, `in progress`, `implemented`, `verified in CI`, `verified in staging`.

---

## 10. Final recommendation

The codebase has made meaningful progress. The course/catalogue flow, authentication and password recovery, test engine foundation, CSV question import, PWA shell and R2 administration are real implementations—not just documentation or mock UI. The latest observed backend CI run is green, which is a good baseline.

However, **do not prioritize new product features ahead of the tenant-ownership fix and assessment-integrity work**. Those two areas protect the platform's core data and the credibility of its test results.

Recommended release sequence:

1. Fix and test all cross-provider staff writes and parent reassignment paths.
2. Correct multiple-choice handling, authoritative timers and immutable attempt snapshots.
3. Add database identity constraints and align superuser authorization.
4. Expand CI to include frontend checks and PostgreSQL-backed tests.
5. Harden token storage, CSP and distributed throttling.
6. Finish and verify the R2 asset pipeline and then expand analytics/offline/community features.

**Release stance:** suitable for continued development and controlled staging after the P0 tenant authorization work is fixed and verified. Not yet recommended for an unrestricted multi-provider production launch based on this source review.

---

## 11. Source index

- [Current repository](https://github.com/sawroop1242/pw-style-learning-app)
- [Backend settings](https://github.com/sawroop1242/pw-style-learning-app/blob/main/backend/config/settings.py)
- [Account views and OTP flow](https://github.com/sawroop1242/pw-style-learning-app/blob/main/backend/accounts/views.py)
- [Account serializers](https://github.com/sawroop1242/pw-style-learning-app/blob/main/backend/accounts/serializers.py)
- [Course policy](https://github.com/sawroop1242/pw-style-learning-app/blob/main/backend/courses/policy.py)
- [Course and staff API viewsets](https://github.com/sawroop1242/pw-style-learning-app/blob/main/backend/courses/views.py)
- [Course/test serializers](https://github.com/sawroop1242/pw-style-learning-app/blob/main/backend/courses/serializers.py)
- [Test models](https://github.com/sawroop1242/pw-style-learning-app/blob/main/backend/courses/models/test_engine.py)
- [Grading engine](https://github.com/sawroop1242/pw-style-learning-app/blob/main/backend/courses/grading.py)
- [CSV import implementation](https://github.com/sawroop1242/pw-style-learning-app/blob/main/backend/courses/csv_import.py)
- [R2 credential crypto](https://github.com/sawroop1242/pw-style-learning-app/blob/main/backend/objectstore/crypto.py)
- [R2 storage services](https://github.com/sawroop1242/pw-style-learning-app/blob/main/backend/objectstore/services.py)
- [Frontend API client](https://github.com/sawroop1242/pw-style-learning-app/blob/main/frontend/assets/js/core.js)
- [Frontend class player](https://github.com/sawroop1242/pw-style-learning-app/blob/main/frontend/assets/js/player.js)
- [Frontend test player](https://github.com/sawroop1242/pw-style-learning-app/blob/main/frontend/assets/js/test-player.js)
- [Service worker](https://github.com/sawroop1242/pw-style-learning-app/blob/main/frontend/sw.js)
- [Backend GitHub Actions workflow](https://github.com/sawroop1242/pw-style-learning-app/blob/main/.github/workflows/backend-checks.yml)

*Prepared from the repository snapshot listed at the top of this report. Findings should be rechecked against the branch head immediately before implementation or release.*
