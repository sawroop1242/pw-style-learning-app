# Course Discovery — Product and Engineering Specification

## Goal
Make the existing published course catalogue easy to search and browse on low-cost Android phones. This extends the catalogue/search requirement in the master prompt; it must not create a parallel catalogue.

## Learner experience
- Search published course title, description, subject/category, and provider/teacher display name only where those fields are intended to be public.
- Filters: exam, subject/category, level, and free versus paid. `Course.exam`
  and `Course.level` exist for this (`0012`); both are blank-able, and a blank
  is *not* a filter value — the batch stays listed but never claims an exam or
  a stage nobody chose. A group is multi-select (repeated query parameters,
  e.g. `?exam=JEE&exam=NEET`), and `GET /api/courses/facets/` returns the count
  behind every value with the rules that make counts trustworthy:
  each group is counted with the **other** groups applied and **its own left
  out**, so ticking one value never hides its siblings and every number answers
  "what would this add?"; values no batch carries are omitted rather than shown
  as `0`; unpublished batches appear in no count.
- Sorting: relevance for search, recently published, and a popularity metric only if it is based on a defined, privacy-safe server metric. Do not fabricate popularity.
- Course cards show only available fields: title, thumbnail/image URL, subject, price/free label, and access/lock status. Use a safe placeholder for missing or invalid images.
- Course detail shows description, authorized provider contact information, folders/chapters, and access requirements. It also shows the batch **contents as a tree**: subject → section → the classes and PDFs inside that section, with a search box, two buttons that open or close the whole tree, and a count on every folder line. A learner looking for "the DPP for this chapter" should not have to open a second tab to find it. It shows the batch **timetable** too — the air time of every class that has one — because "when does this batch run" is how a learner decides to join. Air times are public metadata; the recordings behind them are not, and each one is listed with its lock state rather than hidden.
- Pagination or bounded cursor pagination; preserve filters when navigating back.
- Provide loading, no-results, offline, and recoverable error states. Debounce search on the client without treating debounce as a security control.

## Access control and correctness
- Public catalogue results include published courses only.
- Draft, archived, paid-course protected content and private provider details must not leak through search, autocomplete, filters, counts, ordering, or detail endpoints.
- Search results may indicate a paid course exists, but must not return protected PDFs, video secrets, access codes, or content URLs until server-side access checks pass.
- A batch timetable may be read without enrolling (`GET /api/schedule/?course=`), but it carries no `video_url`: the payload says *when* a class airs, never *where* its media lives. A lesson with no air time is on demand and is deliberately absent from the timetable rather than assigned an invented hour. The live state is computed from `starts_at` + `duration_minutes` at request time, so it cannot go stale.
- Validate and allowlist sort/filter fields; limit query length, page size and expensive filters.
- Escape search text and render course content safely. Do not construct raw SQL from user input.
- If search uses a database-specific full-text feature, provide a documented fallback appropriate to the existing database; avoid adding a paid search service without approval.

## Performance and accessibility
- Add indexes only based on query patterns and migration review.
- Avoid N+1 queries and unbounded responses.
- Make filters usable at 320px width, keyboard accessible, clearly labelled, and compatible with screen readers.
- Do not require high-resolution imagery or heavy client libraries for core browsing.

## Required tests
Cover published/draft visibility, free/paid filters, query matching and escaping, invalid filters/sorts, pagination, ownership/private-field leakage, performance/query counts where practical, and responsive/empty/error UI states.

## Definition of done
Reuse the existing course API and UI. Document any unsupported filter rather than faking it; tests must prove access restrictions remain intact.
