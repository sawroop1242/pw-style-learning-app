# Coding-Agent Prompt — Authentication, Password Changes, and Email OTP Reset

## Read first
Read docs/FEATURE_SPEC_AUTHENTICATION.md and inspect the existing Django user model, registration/login/JWT endpoints, serializers, settings, email configuration, frontend auth forms, migrations, and tests. Reuse the existing authentication architecture if sound; do not create a parallel user system.

## Milestone discipline
- Follow docs/agent-prompts/README.md and execute only the authorized milestone.
- Milestone 1 is foundation verification only; do not implement auth features there.
- Milestone 3 implements backend identity, registration, change-password, forgot-password OTP, SMTP configuration, throttling, and security tests.
- Milestone 7 wires the frontend API client/auth flows; Milestone 8 completes and verifies learner-facing screens.
- Do not skip ahead. Stop after the current milestone report.

## Required implementation
1. Registration requires a unique username, unique normalized email, and password. Enforce case-insensitive uniqueness at the database/application layers where possible and handle concurrent duplicate submissions.
2. Use Django password hashing and configured password validators. Public registration must not set role, staff, superuser, active, permissions, or sub-admin fields.
3. Preserve/document existing JWT login, refresh, logout, and revocation behavior. Throttle registration/login and never log credentials or tokens.
4. Authenticated password change requires the current password and validated new password/confirmation. Invalidate sessions/refresh tokens according to the documented architecture.
5. Forgot-password must respond generically to avoid revealing whether an email exists. Generate a secure, short-lived, single-use OTP, store only its secure hash/HMAC, bind it to the account and purpose, enforce expiry and attempt limits, throttle requests/resends, and consume it atomically with the password update.
6. Send the OTP to the user's registered email using Django's provider-neutral SMTP settings. Support the application owner's Gmail SMTP account or another SMTP provider using environment variables only. For Gmail, document supported SMTP settings and use an App Password when eligible; never use a normal Google account password or hardcode credentials. Do not ask the user to paste credentials into chat.
7. Add placeholder-only environment documentation (.env.example), production configuration checks, safe email content, and mocked email tests. No SMTP credentials or OTPs in git, logs, frontend bundles, or API responses.
8. Build registration, login, forgot-password, OTP/reset, and authenticated change-password UI in the relevant frontend milestone. Show validation, expiry, cooldown, loading and error states; do not store OTPs in browser storage or service-worker caches.
9. Document endpoint contracts, OTP lifetime/attempt limits, resend policy, email backend configuration, token invalidation behavior, and known limitations.
10. Add functional, permission, abuse/rate-limit, concurrency/replay, and email-delivery failure tests. Report only tests actually run.

## Acceptance report
List files changed, migrations, API contracts, environment variable names (never their secret values), chosen OTP lifetime/attempt/resend limits, token revocation strategy, exact tests/results, remaining risks, and updated docs/BUILD_STATUS.md and docs/IMPLEMENTATION_PLAN.md. Stop after the authorized milestone.
