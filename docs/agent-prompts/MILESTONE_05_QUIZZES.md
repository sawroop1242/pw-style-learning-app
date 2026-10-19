# Coding-Agent Prompt — Milestone 5: Quiz Engine and Server-Side Scoring

## Objective
Deliver a safe quiz attempt flow. The server—not the browser—owns the answer key, scoring, and attempt record.

## Required workflow
1. Student fetches a published quiz and receives question/choice IDs and display text, without correct-answer flags, answer keys, explanations, or other fields that reveal the solution before submission.
2. Student submits a structured answer payload referencing valid question and choice IDs.
3. Backend validates quiz publication, user authentication, question membership, choice membership, duplicates, missing/optional answers, attempt limits, and submission state.
4. Backend calculates score from stored correct-answer data. Ignore or reject any client-supplied score, correctness, or answer-key field.
5. Response returns the score and only the post-submission explanations/results allowed by the product policy.
6. Student can list and inspect only their own attempt history.

## Decide and document
Define whether unanswered questions count as wrong, whether multiple answers are supported, retake rules, attempt limits, score representation, and whether attempts are immutable after submission. Enforce the selected rules server-side.

## Security and integrity
- Do not leak correct flags through serializers, nested serializers, detail endpoints, errors, or alternate routes.
- Do not trust client-provided totals or percentages.
- Use database transactions for attempt creation/scoring where appropriate.
- Prevent tampering with another user's attempt IDs.
- Ensure unpublished quizzes cannot be attempted by students.
- Avoid duplicate submissions creating inconsistent attempts; define idempotency or a clear rejection behavior.

## Test series and CSV import requirements

Follow `docs/FEATURE_SPEC_TEST_SERIES.md`. Implement the test-taking engine with timed, untimed, total and section-level timing modes, server-authoritative deadlines, stable attempt snapshots, configurable question/option shuffling, autosave/resume, mark-for-review, navigation rules, early submit, timeout auto-submit, idempotent submission, attempt/retake limits, and result-release rules. Apply marks, negative marks, unanswered-question rules, and optional multiple-answer partial credit only when configured and fully tested.

Provide a documented UTF-8 CSV template with section, question type/text, options, correct option key(s), explanation, marks, negative marks, difficulty and topic as supported. Staff supplies a CSV HTTPS URL hosted externally; do not add a CSV upload endpoint or persist the CSV file/blob/raw body in backend storage or database fields. Persist only the source URL and minimal import metadata, while storing successfully imported questions/options/answer keys as structured records. Fetch and parse in memory with strict byte/row limits, timeouts, allowed-host/HTTPS checks, redirect and resolved-IP validation to prevent SSRF, and a row-level preview before confirmation. Prevent cross-owner imports and unsafe exports, and define atomic/partial-failure and re-import behavior. Never accept a correct answer key that does not map to the row's options.

The backend clock is authoritative. Persist deadlines and do not reset them on refresh. Untimed tests must not expire based only on elapsed time. Correct answers/explanations remain hidden until the test's release policy allows them. Use an immutable question/rule snapshot so edits cannot alter already-started or completed attempts.

## Tests
Cover correct/incorrect/unanswered answers, malformed payloads, invalid or foreign question/choice IDs, duplicate entries, client score tampering, answer-key secrecy, explanation timing, publication rules, retakes/limits, anonymous access, and cross-user attempt isolation.

## Acceptance
Document request/response examples and rules, run full backend tests and migration checks, update status, and stop before Milestone 6.
