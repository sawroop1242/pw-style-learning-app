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

## Tests
Cover correct/incorrect/unanswered answers, malformed payloads, invalid or foreign question/choice IDs, duplicate entries, client score tampering, answer-key secrecy, explanation timing, publication rules, retakes/limits, anonymous access, and cross-user attempt isolation.

## Acceptance
Document request/response examples and rules, run full backend tests and migration checks, update status, and stop before Milestone 6.
