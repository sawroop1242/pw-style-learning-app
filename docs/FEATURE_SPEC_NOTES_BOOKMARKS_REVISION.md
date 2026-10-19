# Notes, Bookmarks, and Revision — Product and Engineering Specification

## Goal
Build a connected revision workspace around existing lesson notes, learning progress, and test questions. Reuse existing notes/progress models where sound.

## Student features
- Create, edit, and delete private notes; optionally link a note to a course, lesson, or question.
- Bookmark courses, lessons, PDFs/resources, and supported questions. A bookmark stores a stable resource reference and creation timestamp, not a copy of protected content.
- Organize saved items into a revision list and optionally add a short personal note or tag.
- Filter by course, subject, resource type, tag, and recently added.
- Mark a lesson or question as needing revision and mark it reviewed; do not overwrite formal test attempt records.
- Provide a unified “My Revision” screen and useful empty states.
- Sync account-owned data through authenticated APIs. If offline editing is later supported, show pending sync state and resolve conflicts explicitly.

## Permissions and data lifecycle
- Private notes, bookmarks, tags and revision states are visible only to their owner and authorized staff only where a documented support need exists.
- Validate that referenced resources exist and are accessible to the user. Removing/unpublishing a resource must not leak it through an old bookmark; show a safe unavailable state.
- Use server-side ownership checks for read/update/delete; never trust user IDs supplied by the client.
- Add uniqueness constraints where appropriate to prevent duplicate bookmarks for the same user/resource.
- Define deletion behavior and avoid cascading deletion of unrelated user data.
- Sanitize note text and render it as text/Markdown only if a safe renderer is deliberately selected; never inject arbitrary HTML.

## UX and accessibility
- Mobile-first UI with search/filter, visible save status, keyboard/touch support, readable text and 320px-width layout.
- Confirmation for destructive actions; recoverable error states and retry where safe.
- Never show fake success if the API fails.

## Required tests
Cover CRUD, cross-user isolation, duplicate bookmarks, invalid/inaccessible resource IDs, deleted/unpublished resources, safe rendering, pagination/filtering, and migrations. If offline queueing is implemented later, test duplicate retries and conflict behavior.

## Definition of done
Integrate with existing notes/progress and learner milestones. Update APIs, frontend, tests, and docs in the authorized milestone sequence; do not build a parallel notes system.
