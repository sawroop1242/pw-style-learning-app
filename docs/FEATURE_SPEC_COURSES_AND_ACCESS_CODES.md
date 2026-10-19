# StudySpace Feature Specification — Course Management and Code-Based Access

## Purpose and scope

Implement a course platform where the main administrator can create sub-admin accounts, authorized sub-admins can manage their own courses, and students can access free courses immediately or unlock paid courses using a code issued by an authorized administrator. A student obtains a paid-course code by contacting the provider through the Telegram contact shown on that course's details page.

**There is no online checkout or in-app payment method.** Do not add Stripe, Razorpay, UPI collection, payment gateway, payment links, or an alternative payment flow. The app records course access after code redemption; it does not verify that money changed hands.

This is a product requirements document. The coding agent must inspect the current repository and integrate these requirements into its existing Django/API/frontend architecture rather than blindly creating duplicate models.

## Roles and permissions

### Main admin
- Full platform control.
- Create, edit, deactivate, and reactivate sub-admin accounts.
- Assign/revoke course-management permissions.
- View and manage all courses, folders, lessons, access codes, course grants, and audit events.
- Generate, revoke, and inspect codes for any course.
- Cannot view a code's stored hash as though it were the original code; reveal newly generated codes only at creation time.

### Sub-admin / course provider
- Can create and manage courses they own, subject folders, chapter PDFs, and video lessons.
- Can configure the course's Telegram contact and free/paid price.
- Can generate and revoke access codes only for courses they own and are authorized to manage.
- Cannot create or promote other admins/sub-admins, alter global settings, or manage another provider's course or codes.
- Deactivation must immediately prevent further management and code generation; define whether existing course content remains published under main-admin control.

### Student
- Can browse published courses and course details.
- Can open free courses without a code.
- Can submit a code to unlock a paid course.
- Can access paid-course resources only after a valid course grant exists.
- Cannot create courses, generate codes, or access staff/admin endpoints.

Implement authorization on the server for every action. Hiding controls in the frontend is not authorization.

## Course data and details page

Each course should support, using appropriate existing models/fields:
- Title, stable slug/ID, description, subject/category, cover image URL, creator/owner, publication status, ordering, and timestamps.
- Pricing mode: **free** or **paid**. Free courses must have a zero price; paid courses must have a positive configured price and currency. Validate this invariant server-side.
- Provider Telegram contact, such as a normalized Telegram username (for example, `@provider_name`) and/or a validated `https://t.me/...` URL. Display a clear “Contact provider on Telegram to get an access code” action on paid-course details. Do not imply the app can verify Telegram conversations or payments.
- Course detail view must show title, image, description, subject, free/paid label, price where paid, provider Telegram contact, and access status.
- A draft/unpublished course is visible only to its owner and authorized staff. Students see published courses only.

Do not copy third-party branding or use unauthorized course media.

## Course content hierarchy

Support the following content structure:

- Course
  - Subject folder (one course can contain multiple folders)
    - Chapter PDF resource(s)
    - Video lesson(s)

A folder has a title, optional description, stable ordering, and belongs to one course. Prevent cross-course resource associations. Support editing, reordering, and deleting content with deliberate deletion behavior.

### Video lessons
- Fields: title, optional description, embed URL, folder/course relationship, ordering, publication status, timestamps.
- Accept only HTTP(S) URLs from supported/approved video providers or explicitly approved embed domains.
- Do not accept arbitrary iframe HTML, `javascript:` or `data:` URLs; do not bypass DRM, login requirements, paywalls, or provider restrictions.
- Frontend should show the video embed when permitted by the provider and a clear external-open fallback when embedding is blocked.
- Never claim every URL can be embedded. Validate URL and test the supported-provider policy.

### Chapter PDFs
- Fields: title, optional description, PDF download resource, folder/course relationship, ordering, publication status.
- Validate that the resource is an allowed HTTPS URL or use private file storage as appropriate. A URL string alone does not prove that the remote file is a PDF.
- **Paid content must be protected.** Do not expose a permanent public PDF URL that bypasses course access. Prefer private storage plus an authenticated download endpoint or short-lived signed URL issued only after checking the student's grant. If the product owner insists on an externally hosted public link, document that access cannot be enforced once the link is public and do not label it protected.
- Never fetch arbitrary user-supplied URLs from the server without SSRF-safe validation.

## Paid-course access code lifecycle

Authorized main admins and authorized course-owning sub-admins can create one or more access codes for a specific paid course. The intended operational flow is:
1. Provider creates codes in the admin interface.
2. Provider shares a code with a learner outside the app after arranging access directly (typically via the Telegram contact displayed on the course).
3. Learner signs in, opens the paid course, enters the code, and submits it.
4. The server validates and redeems the code atomically.
5. A successful redemption creates a durable course-access grant; the learner can then open that course's protected lessons and PDFs.

### Code requirements
- Generate cryptographically secure, high-entropy, non-sequential codes. Do not use guessable integers or course IDs.
- Bind each code to exactly one course. Codes must never unlock a different course.
- Default to **one redemption per code**. If bulk issuance is implemented, generate a distinct code for each intended learner. Do not make codes unlimited-use by default.
- Store only a hash of each code after generation; show the raw code once at creation and tell the staff member to copy/save it securely. Never log raw codes or include them in analytics.
- Support status (unused/redeemed/revoked/expired), created-by, created-at, optional expiry, redemption user/time, and revocation metadata as justified by the schema.
- Allow authorized staff to revoke unused codes and, under a documented policy, revoke a learner's access grant. Code revocation must not silently or ambiguously change an already-created grant; define and test the behavior.
- Enforce rate limits on code submissions and use generic failure messages that do not reveal whether a code exists, belongs to another course, expired, or was already redeemed.
- Validate course pricing and code state on the server; never trust a frontend "unlocked" flag.
- Use a database transaction/row lock or equivalent concurrency-safe operation so simultaneous requests cannot redeem a one-use code twice.
- Add an audit trail for code creation, redemption, revocation, grant creation/revocation, and staff actor. Do not store the raw code in audit records.
- Prevent enumeration, replay, race conditions, cross-user grants, and cross-course redemption.

### Free courses
- A free course requires no access code.
- Do not permit paid codes to be redeemed for a free course unless a future explicit requirement defines a separate purpose.
- If a course changes from free to paid or paid to free, define how existing grants are handled; do not unexpectedly lock out existing enrolled learners or expose paid content. Document and test the selected migration policy.

## API and frontend expectations

Design API routes that fit the existing project; names below are conceptual, not mandatory:
- Staff course CRUD and publish/unpublish.
- Course folders and ordered content CRUD.
- Staff code generation (single and optional batch), list metadata, revoke.
- Student code redemption for a selected course.
- Student access-status / granted-course endpoint.
- Protected lesson/PDF delivery that checks access on every request.
- Telegram contact link in course detail.
- Course catalogue and detail responses must not leak draft content, code hashes, internal audit data, or answer keys.

Frontend states must cover loading, empty, validation error, expired/invalid/already-used code, success, network failure, locked content, and unlocked content. Do not show success until the server confirms redemption. Provide accessible labels and mobile-friendly controls.

## Required test matrix

At minimum test:
- Main admin can create/deactivate a sub-admin; a student cannot.
- Sub-admin can manage own course/folders/content/codes but cannot manage another provider's course.
- Student cannot call staff endpoints even if the UI is manipulated.
- Free course opens without code; paid course remains locked without a grant.
- Valid code grants access to the correct course and only the authenticated redeemer.
- Wrong-course, invalid, expired, revoked, and already-used codes fail safely.
- Two concurrent redemptions of the same one-use code produce at most one success.
- Repeated guessing is throttled.
- Code values/hashes are never exposed through student APIs or logs.
- Draft courses/content remain hidden from students.
- Protected PDF and lesson requests reject users without a grant and allow users with a grant.
- Public direct PDF URLs are not mistakenly treated as protected.
- Telegram handles/URLs are validated and rendered safely.
- Pricing invariants and free-to-paid/paid-to-free transition rules are tested.
- Migrations work on a clean database and existing data is preserved.

## Definition of done

- Update models/migrations, serializers, views/permissions, admin, frontend, API docs, tests, and status docs as appropriate.
- Use existing architecture and naming conventions after inspection.
- Run the relevant tests and full suite available in the repository; record exact commands and results.
- Do not claim a test passed unless it was actually run successfully.
- Implement one existing milestone per run. Fold the relevant subset of this specification into that milestone; do not bypass the ordered milestone process or attempt a giant rewrite.
- Do not deploy or provision paid services without explicit user authorization.
