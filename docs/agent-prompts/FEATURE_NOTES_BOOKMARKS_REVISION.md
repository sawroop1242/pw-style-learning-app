# Coding-Agent Prompt — Notes, Bookmarks, and Revision

Read `docs/FEATURE_SPEC_NOTES_BOOKMARKS_REVISION.md`, current notes/progress implementation, the master prompt, and the authorized milestone file before editing.

## Rules
- Inspect current models/API/frontend first and reuse sound notes and progress structures.
- Milestone 1 is foundation verification only. Do not skip milestone order or mark work complete without actual checks.
- Scope every private record to the authenticated user in the queryset and object permissions.
- Store resource references, not copied protected media or documents. Safely handle deleted/unpublished resources.
- Never render arbitrary note HTML. Do not use localStorage as the source of truth for private account data.
- Implement only what belongs to the authorized milestone; defer dependent UI until its milestone.

## Tasks when authorized
1. Document the existing model/API gap and migration plan.
2. Add private notes, bookmarks, and revision state using existing models where suitable.
3. Add authenticated CRUD/list APIs with filtering, pagination, validation, and ownership enforcement.
4. Build the learner revision interface with working API integration and accessible states.
5. Add regression tests for ownership, duplicate resources, deletion/unpublishing, safe rendering, and API failures.
6. Update docs/build status based on real test output.

## Report
List code/docs changed, migration/API decisions, tests and exact results, remaining gaps, and next milestone. Stop after the authorized milestone.
