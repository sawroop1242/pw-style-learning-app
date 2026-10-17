# Coding-Agent Prompt — Milestone 2: Data Model and Django Admin

## Objective
Inspect and complete the persistence layer and admin workflows for StudySpace without breaking existing records or introducing unnecessary model duplication.

## Inspect first
Read existing models, migrations, serializers, viewsets, admin registrations, and current tests. Map each existing model to the product needs before editing. Identify the user model strategy and relationships. Do not assume the model names or fields without reading them.

## Required domain coverage
Ensure the model layer can represent:
- Course: title, slug or stable identifier, description, subject/category, publication status, ordering, timestamps, and optional thumbnail metadata.
- Lesson: course relationship, title, description, ordering, duration where known, authorized video URL/embed metadata, publication status, and completion identity per user.
- Quiz: relationship to a course and/or lesson as justified, title, publication status, ordering, and attempt policy.
- Question and Choice: stable ordering, question text, choice text, and server-side correct-answer representation.
- QuizAttempt and submitted answers: user, quiz, timestamps, submitted answers, score/result, and attempt state.
- Note: owner, optional course/lesson association, title/body, timestamps, and appropriate constraints.
- Progress: owner, lesson, completion state/timestamp, and uniqueness rules.
- Profile fields only where product requirements justify them; use Django's supported user extension pattern.

Do not add duplicate models if the existing schema already meets these needs. Do not store unnecessary sensitive data. Decide deletion behavior deliberately.

## Database quality
- Add appropriate foreign keys, uniqueness constraints, indexes, ordering, validation, and timestamps.
- Use migrations for all schema changes; never edit migration history destructively without a clear migration plan.
- Ensure migrations apply to an empty database and do not silently discard user data.
- Avoid storing calculated values that can be derived unless there is a documented performance or historical reason.
- Keep SQLite development and PostgreSQL deployment behavior compatible.

## Django admin
- Register all content models with useful list displays, search, filters, ordering, and inline editing where safe.
- Make publication state clear and avoid accidentally publishing drafts.
- Keep answer-key fields visible only to authorized staff in admin, never student API payloads.
- Avoid N+1 admin queries when using related objects.

## Tests and acceptance
Add tests for required fields, constraints, ordering, relations, cascade/protect behavior, publication defaults, and admin registrations/permissions. Run migrations on a fresh test database, `makemigrations --check --dry-run`, and the complete Django test suite.

Update plan/status with exact results. Do not begin Milestone 3 until migration and model/admin acceptance criteria pass.
