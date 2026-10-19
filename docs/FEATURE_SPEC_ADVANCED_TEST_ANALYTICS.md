# Advanced Test Analytics — Product and Engineering Specification

## Goal
Extend the existing quiz/test engine with trustworthy student performance insights and permission-safe staff analytics. This is an extension of `docs/FEATURE_SPEC_TEST_SERIES.md`, not a separate test system.

## Student insights
- Show each released attempt's score, percentage, correct/incorrect/unanswered counts, duration, and section breakdown when supported by the test's result policy.
- Show progress over time across released attempts for the same test/series, clearly distinguishing practice from formal exam attempts.
- Show topic-wise strengths and areas for revision only when questions have validated topic tags and there is enough data to avoid misleading conclusions.
- Compare a student's attempts only with their own prior attempts. Do not show other students' identities, answers, or individual scores.
- Explain each metric and display an empty state when data is insufficient. Never invent or infer missing scores.

## Staff analytics
Authorized main admins may view platform-wide aggregates. A sub-admin may view only courses/tests they own or are explicitly assigned to. Provide:
- Starts, completed attempts, completion rate, and abandonment/in-progress counts.
- Score distribution, median/average where sample sizes are adequate, and pass rate only when a pass threshold exists.
- Section- and topic-level aggregates when metadata supports them.
- Question-level correctness/difficulty signals based on observed responses, with sample size displayed.
- Date range and test/series filters, pagination for detailed lists, and CSV export only for authorized staff.
- A safe individual-attempt detail view only where the role and ownership rules permit it.

## Definitions and correctness
- Document formulas for completion rate, score percentages, time used, and pass rate.
- Use server-persisted attempt and scoring snapshots; do not accept client-supplied analytics values.
- Count each attempt once and handle duplicate submissions/idempotency.
- Respect result-release policies: unreleased scores and answer keys must not leak through charts, summary endpoints, exports, or aggregate queries.
- Clearly label the denominator and date range. Exclude incomplete attempts from score statistics unless a metric explicitly includes them.
- Do not imply causation or make unsupported student rankings. Rankings/leaderboards are out of scope unless separately approved.

## Privacy, performance and security
- Enforce authorization in every API query, not only in UI filters.
- Minimize personally identifiable data in aggregates; never expose email or username in aggregate endpoints.
- Apply pagination, date-range limits, indexes, and query-count checks for large result sets.
- CSV exports must escape spreadsheet-formula prefixes and must not be stored as persistent raw upload files.
- Audit exports and staff access to sensitive attempt details without logging answers or secrets unnecessarily.

## Required tests
Test formulas and edge cases; empty/small samples; unreleased results; duplicate submissions; cross-student isolation; sub-admin ownership boundaries; unauthorized export/detail access; date filters; pagination; CSV formula injection; and performance/query behavior on representative data.

## Definition of done
Integrate with the existing test engine and milestone sequence. Add migrations only when justified, tests for all calculations/permissions, frontend loading/empty/error states, and docs. Do not claim analytics are live until backed by real API data and verified tests.
