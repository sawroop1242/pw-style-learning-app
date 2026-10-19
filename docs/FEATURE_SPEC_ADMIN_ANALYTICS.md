# Admin and Sub-Admin Analytics — Product and Engineering Specification

## Goal
Provide operational visibility into course engagement, access-code usage, and learning activity while protecting student privacy and enforcing staff ownership. Test-specific metrics are additionally defined in `docs/FEATURE_SPEC_ADVANCED_TEST_ANALYTICS.md`.

## Dashboards
Main admin may see platform-wide aggregates. A sub-admin may see only courses/tests they own or are explicitly assigned to. Depending on available persisted data, show:
- Published/draft course counts and recent content updates.
- Enrolment/access-grant counts and access-code redemption totals, failures, expiry and remaining-use counts where recorded.
- Lesson completion and course-progress summaries.
- Test starts, completed attempts and score summaries via the advanced test analytics spec.
- Activity trends over selectable, bounded date ranges.
- Recent administrative events relevant to the staff member's scope.

Do not invent metrics when event/history data does not exist. Identify unavailable historical data and begin collecting it only through a documented, privacy-conscious event design.

## Privacy and authorization
- Enforce role and ownership restrictions on every backend query and export.
- Aggregate views should omit direct identifiers by default. Individual student records require a separate authorized workflow and documented purpose.
- Do not expose passwords, OTPs, access codes in plaintext, answer keys, private notes, tokens, or protected media URLs.
- Define retention and access rules for audit events. Avoid logging unnecessary personal data.
- Record staff actions that affect access, course publication, codes, and sensitive exports.

## UX and reporting
- Date filters, course/test filters and clear metric definitions.
- Accessible summary cards and lightweight charts/tables that work on small phones.
- CSV export only for authorized roles, with bounded rows, formula-injection protection, and an audit event.
- Loading, empty, partial-data, and API-error states. Show sample size and date range where meaningful.

## Technical requirements
- Use database-backed aggregates, bounded query parameters, pagination and suitable indexes.
- Prevent N+1 queries and add query-count/performance tests where practical.
- Do not add a paid analytics vendor or third-party tracking by default.
- Keep API responses free of cross-tenant data and ensure cache headers do not make private dashboards public.

## Required tests
Role scoping; sub-admin cross-owner denial; date filters; empty datasets; formula-safe exports; sensitive-field exclusion; audit events; pagination; and aggregate correctness.

## Definition of done
Metrics must be traceable to real persisted records and documented formulas. Update tests and operational documentation in milestone order; do not label unimplemented metrics as available.
