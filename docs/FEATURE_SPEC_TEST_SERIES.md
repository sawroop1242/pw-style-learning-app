# StudySpace Test Series — Product and Engineering Specification

## 1. Goal

Add a production-minded test-series system to StudySpace. The main admin and authorized sub-admins can create test series, organize tests into sections, import questions from CSV, and configure timing and scoring rules. Students can take tests, submit answers, and review results according to the test's configured policy.

This document extends the existing quiz engine. Inspect the current models and implementation first; reuse and evolve them rather than creating a parallel quiz/test system without a clear reason. Apply the work through the existing milestone order.

## 2. Roles and ownership

### Main admin
- Create, edit, publish, unpublish, archive, and delete test series across the platform.
- Create and manage sub-admin accounts and assign course/test management permissions.
- Manage any test series, tests, sections, questions, CSV imports, timer rules, attempts, results, and moderation settings.
- Review import jobs and audit events.

### Sub-admin / provider
- Create and manage test series and tests they own or are explicitly assigned to.
- Import CSV question sets, configure sections/timing/scoring, preview, publish, and unpublish their own tests.
- Cannot manage another provider's test series, change global settings, or grant themselves additional privileges.
- Must not change question sets or scoring rules for an in-progress attempt in a way that changes that attempt's outcome. Use versioning/snapshots or block edits while attempts are active.

### Student
- Browse and take published test series they are authorized to access.
- Save answers during an attempt, submit, and see results only according to the test's result-release policy.
- Access only their own attempts, saved responses, and history.

All ownership, publication, access, and scoring rules must be enforced by the backend. Frontend controls alone do not provide security.

## 3. Content hierarchy

Support a hierarchy similar to:

- Test Series
  - Test / Mock Exam
    - Section (optional; one or more)
      - Questions
        - Options / choices
        - Correct answer(s), explanation, marks and negative marks

A test series includes title, slug/ID, description, image URL (optional), subject/category, exam label, owner, publication status, ordering, optional start/end availability, and timestamps.

Each test has title/instructions, total duration or untimed mode, section rules, total marks, pass threshold if configured, attempt limit, shuffle policy, result policy, and publication state. A series may contain multiple tests, practice tests, mock exams, and topic-wise tests.

## 4. CSV import and export

Admin and authorized sub-admins must provide a CSV HTTPS URL (a link to a CSV file in approved external storage) containing questions, options, and correct answers, using a documented template. **The backend must not accept or persist a CSV file upload and must not store the CSV file/blob or raw CSV contents.** Persist only the validated source URL and minimal import metadata (target test, uploader, status, timestamps, row counts, and safe error summary). Provide a downloadable sample CSV/template for staff to prepare and host externally. The imported question/option/answer records are persisted as normal structured database records so the test engine can query and score them; this does not mean the CSV file or its raw contents are stored.

### Recommended columns

Support a documented versioned schema such as:

- `section` — optional section name
- `question_type` — `single_choice`, `multiple_choice`, `true_false`, or `short_answer` only if the current engine supports it
- `question_text` — required question text
- `option_a`, `option_b`, `option_c`, `option_d` — option text for choice questions; permit more options only if schema supports them
- `correct_option` — for single choice, a key such as `A`; for multiple choice, documented delimited keys such as `A|C`
- `explanation` — optional post-submission explanation
- `marks` — optional positive/non-negative marks with a documented default
- `negative_marks` — optional non-negative penalty with a documented default
- `difficulty` — optional `easy`, `medium`, `hard`
- `topic` — optional topic/tag
- `question_image_url` — optional validated image URL if supported

Keep this schema versioned and documented. The template and importer must agree exactly. If the existing data model cannot support a type, reject it clearly rather than silently downgrading or mis-scoring it.

### Import workflow
1. Authorized staff downloads the template and uploads a UTF-8 CSV.
2. Server validates file size, row count, headers, encoding, question text, option counts, correct-option keys, marks, section names, URL fields, and supported question types.
3. Parse and validate the complete file before writing. Show a preview with row numbers, errors, warnings, and the number of valid questions.
4. On confirmation, import atomically where practical, or use an explicit import-job model with documented partial-failure behavior. Never leave an unexplained half-imported set.
5. Return row-level errors with safe, useful messages; do not echo unsafe HTML or expose server paths.
6. Record uploader, target test, timestamp, status, counts, and error report metadata. Never log full private question content unnecessarily.
7. Support re-import behavior intentionally: default to creating a new import or replacing a draft test only after explicit confirmation. Do not silently duplicate all questions or overwrite a published test.
8. Provide CSV export for authorized staff where useful. Export must not include student attempt data unless explicitly authorized; protect against spreadsheet formula injection by escaping cells beginning with `=`, `+`, `-`, or `@`.

CSV URLs and fetched content are untrusted input. Prevent SSRF, unsafe redirects, DNS rebinding, oversized responses, parser abuse, formula injection in exports, cross-owner imports, and incorrect answer mapping. A correct answer must be validated against options present on that exact row. The backend stores the source URL and structured imported records only—not the CSV file or raw CSV contents.

## 5. Timer modes and section timing

Each test supports a clearly selected timing mode:

- **Timed test:** total duration in minutes; server records start and deadline.
- **Untimed practice:** no timer and no automatic time expiry.
- **Section-based timing:** each section has its own duration and deadline. Define whether sections are sequential and locked after expiry, and whether users may navigate back.
- **Total + section limits:** if enabled, both limits apply and the earliest applicable deadline wins.

Do not show a misleading timer. The backend clock and stored deadline are authoritative; the browser timer is only a display. Persist start time, deadline, current section, and server-side state so refresh/reconnect does not reset the clock. Define what happens when a learner closes the browser, loses network, changes device, or returns after the deadline.

For each section, support:
- Section name and ordering
- Optional time limit (minutes)
- Optional question count or selected question set
- Marks and negative marks override only if clearly specified
- Navigation policy: freely revisit, sequential-only, or lock after submit/expiry
- Section submission and expiry policy
- Whether section timer is independent or also constrained by total test deadline

Use server timestamps and timezone-aware datetimes. Prevent clients from extending a deadline by changing local time or manipulating requests. A timeout must be handled consistently by the backend and tested.

## 6. Test-taking behavior

Support these features where compatible with the current architecture and explicitly configurable per test:
- Autosave answers with visible saved/pending/error status.
- Manual save and final submit confirmation.
- Question palette/status: unanswered, answered, marked for review, and visited.
- Mark/unmark for review.
- Previous/next navigation and section navigation according to policy.
- Randomize question order and/or option order while preserving answer mapping; store the attempt-specific order so refreshes do not reshuffle.
- Optional random question selection from a configured question bank, with reproducible attempt snapshots.
- Single-choice and multiple-choice questions, with true/false where appropriate. Add descriptive question types only if scoring semantics are defined and tested.
- Negative marking, per-question marks, partial credit for multiple-choice only when explicitly configured, and unanswered-question rules.
- Attempt limits, retake rules, availability window, optional scheduled opening/closing, and late-entry policy.
- Resume an in-progress attempt without resetting its deadline.
- Submit early, auto-submit on deadline, and handle network failure/retry safely.
- Prevent duplicate submissions and inconsistent double-scoring.
- Display score, percentage, correct/incorrect/unanswered counts, time used, and section-wise breakdown when result policy allows.
- Explanations and correct answers are released only according to the configured result-release policy (immediately after submission, after the test closes, or staff-controlled release).
- Practice mode may provide immediate feedback if enabled; exam mode should not leak answers before submission.
- Accessible keyboard/touch navigation, mobile-first layout, readable question/options, and clear timer warnings.

Do not implement proctoring, webcam capture, microphone recording, invasive device surveillance, or AI-based cheating accusations by default. Such features require separate explicit product approval and privacy/security design.

## 7. Integrity, fairness, and security

- Score only on the server using a versioned snapshot of the questions/options/answer key/rules at attempt start or another documented immutable version.
- Never send correct-answer keys or pre-submission explanations to the student client.
- Validate every answer against the question and option set in the attempt snapshot.
- Use idempotency or a strict state transition so duplicate submits cannot create inconsistent scores.
- Store attempt start/deadline, submission time, status, score, and result release status server-side.
- Enforce access to the test series and ownership of all staff operations.
- Use transactions for submission and timeout processing.
- Rate-limit login and sensitive import/submission endpoints appropriately.
- Do not trust client-provided time, score, total marks, question order, or completion status.
- Keep an audit trail for test publication, question imports, scoring-rule changes, result release, and administrative actions without logging secrets.
- Define behavior for deleted/updated questions: existing attempts must retain the version they were taken against.

## 8. Result and analytics views

Student result view may include:
- Total score and maximum score
- Percentage and pass/fail if a threshold is configured
- Correct, incorrect, unanswered and marked-for-review counts
- Section-wise score and time spent where supported
- Attempt number, start/submission time, time used, and result release status
- Answer review with correct answers and explanations only when permitted

Staff dashboard may include aggregate participation, completion, score distribution, section performance, and question-level statistics. Restrict detailed individual data to authorized staff; do not leak one student's attempt to another. Do not display fabricated analytics or expose correct answers through analytics endpoints.

## 9. Required tests

At minimum:
- Main admin can manage any test series; sub-admin can manage own but not another owner's tests.
- Student cannot create/import/edit/publish tests or access staff APIs.
- CSV valid import, invalid headers, missing options, invalid correct key, malformed row, UTF-8 content, oversized upload, formula-injection export, duplicate import policy, and atomic/partial failure behavior.
- Correct answers and explanations are absent from pre-submission student API payloads.
- Correct, incorrect, unanswered, multiple-choice, negative-marking and partial-credit scoring according to configured rules.
- Timed test deadline survives refresh and cannot be extended by client clock manipulation.
- Untimed test never expires solely due to elapsed time.
- Section timer expiry and navigation/locking rules work as configured.
- Total and section deadlines interact correctly when both are enabled.
- Autosave, reconnect, resume, early submit, auto-submit, duplicate submit and retry behavior.
- Retake/attempt limits and open/close windows.
- Randomized question/option order remains stable during an attempt and scoring remains correct.
- Results are hidden until release policy permits; cross-user attempt isolation.
- Clean database migrations, existing quiz compatibility, and full suite.

## 10. Definition of done

- Update models/migrations, admin, serializers, permissions, API endpoints, frontend screens, CSV template, documentation, and tests as appropriate.
- Integrate with the existing quiz engine; do not create duplicate concepts without a justified migration plan.
- Implement one existing milestone per agent run, in order. Do not bypass foundation verification.
- Run actual checks and report exact commands/results. No fabricated test success.
- Update `docs/BUILD_STATUS.md` and `docs/IMPLEMENTATION_PLAN.md` with evidence.
- Do not deploy or purchase paid services without explicit authorization.
