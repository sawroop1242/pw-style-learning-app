# Course Discovery — Product and Engineering Specification

## Goal
Make the existing published course catalogue easy to search and browse on low-cost Android phones. This extends the catalogue/search requirement in the master prompt; it must not create a parallel catalogue.

## Learner experience
- Search published course title, description, subject/category, and provider/teacher display name only where those fields are intended to be public.
- Filters: subject/category, free versus paid, and supported course level/exam tags if the current model has them.
- Sorting: relevance for search, recently published, and a popularity metric only if it is based on a defined, privacy-safe server metric. Do not fabricate popularity.
- Course cards show only available fields: title, thumbnail/image URL, subject, price/free label, and access/lock status. Use a safe placeholder for missing or invalid images.
- Course detail shows description, authorized provider contact information, folders/chapters, and access requirements.
- Pagination or bounded cursor pagination; preserve filters when navigating back.
- Provide loading, no-results, offline, and recoverable error states. Debounce search on the client without treating debounce as a security control.

## Access control and correctness
- Public catalogue results include published courses only.
- Draft, archived, paid-course protected content and private provider details must not leak through search, autocomplete, filters, counts, ordering, or detail endpoints.
- Search results may indicate a paid course exists, but must not return protected PDFs, video secrets, access codes, or content URLs until server-side access checks pass.
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
