# StudySpace Authentication and Email OTP — Feature Specification

## Goal
Implement a secure account lifecycle using the existing Django REST Framework and authentication architecture. Students register with a unique username, email address, and password; can sign in; can change their password while authenticated; and can reset a forgotten password using a one-time code sent to their registered email address.

Inspect the current source and integrate with existing models, endpoints, serializers, frontend, and JWT setup. Do not create a duplicate user system or replace the authentication stack without evidence and a documented decision.

## 1. Registration and identity
- Registration requires username, email, and password.
- Username must be unique case-insensitively after normalization (trim whitespace; define and test the allowed character set and length).
- Email must be normalized and unique case-insensitively. Enforce uniqueness at application and database levels where supported; handle race conditions with database constraints.
- Password is required and must pass Django's configured password validators. Never store plaintext passwords or reversible password encryption; use Django's password hashing.
- Return field-specific, safe validation errors. Never return password hashes, reset codes, or internal user flags.
- Public registration must not set staff, superuser, sub-admin, role, permissions, active status, or other privileged fields.
- Prevent account enumeration where practical. Public responses should not expose sensitive details about whether another user's username/email exists.
- If email verification is implemented, keep it separate from password-reset OTP.

## 2. Sign in, tokens, and logout
- Preserve the existing JWT/Simple JWT implementation if sound.
- Document whether sign-in accepts username, email, or both.
- Provide refresh and logout/token invalidation behavior. If refresh-token blacklisting is selected, configure the required app and migrations; otherwise document the stateless JWT limitation and revocation strategy.
- Apply throttling to registration and authentication endpoints. Never log passwords, JWTs, OTPs, or reset tokens.

## 3. Change password (authenticated user)
- Require a valid authenticated session/token.
- Require current password and new password plus confirmation (or an equivalent documented contract).
- Verify the current password with Django's password verification; run configured validators against the new password.
- On success, invalidate outstanding refresh tokens/sessions where supported, or document the selected token strategy.
- Never log passwords. A user can change only their own password; staff cannot use this endpoint to change another user's password.

## 4. Forgot password and email OTP reset
### User flow
1. User submits their registered email address to the forgot-password endpoint.
2. The server returns a generic response regardless of whether the email is registered, to reduce account enumeration.
3. For a matching eligible account, generate a cryptographically secure, unpredictable OTP and email it to that address.
4. User submits email, OTP, and a new password (with confirmation) to the reset endpoint.
5. The server validates expiry and attempt state, changes the password atomically, and invalidates the OTP and relevant outstanding sessions/tokens.
6. A successful OTP cannot be reused; replaying or racing reset requests must not produce two successful resets.

### OTP requirements
- Use a cryptographically secure generator; never use a predictable random generator, sequential values, timestamps, or user IDs.
- Prefer a short numeric OTP (for example, 6 digits) with a short configurable lifetime (default 10 minutes).
- Store only a keyed hash/HMAC or otherwise securely hashed representation of the OTP, never plaintext in the database or logs.
- Bind OTP to a specific user and purpose (password reset), and track creation/expiry, attempts, consumption, and issuance throttling.
- Invalidate previous outstanding reset OTPs for the same user when issuing a new one, or define another explicit bounded policy.
- Limit verification attempts (for example, 5 per OTP), resend frequency, and requests per email/IP. Apply DRF throttles and appropriate abuse controls.
- Use constant-time comparison where applicable. Expired, consumed, malformed, wrong-purpose, or over-attempt OTPs must fail safely.
- Make OTP consumption and password update transactional/atomic to prevent replay and race conditions.
- Send only to the account's registered email. Never allow an unauthenticated reset request to change the account email.
- Do not reveal whether a user exists in the forgot-password response.

## 5. Email delivery: owner-configured Gmail or another provider
The application owner wants reset OTP messages sent using their own Gmail account or another email account they control. Implement provider-neutral, environment-configured SMTP delivery, with Gmail SMTP supported as one option.

Configure using environment variables such as:
- EMAIL_BACKEND (SMTP backend in production)
- EMAIL_HOST
- EMAIL_PORT (commonly 587 for STARTTLS)
- EMAIL_USE_TLS
- EMAIL_USE_SSL
- EMAIL_HOST_USER (owner's sender email)
- EMAIL_HOST_PASSWORD (SMTP/app password stored only in deployment secrets)
- DEFAULT_FROM_EMAIL
- optional SERVER_EMAIL

Requirements:
- Validate mutually incompatible TLS/SSL settings and document provider-specific configuration.
- For Gmail, use Google's supported SMTP configuration and an App Password when eligible (usually requires 2-Step Verification). Never ask for or store the owner's normal Google account password. If App Passwords are unavailable, use another supported SMTP/email provider.
- The sender is controlled by the application owner; the recipient is the user's registered email. Never hardcode sender email, app password, SMTP credential, or OTP in source code, committed .env files, tests, or logs.
- Add placeholder-only .env.example entries and document deployment-secret setup. Never expose mail credentials through frontend JavaScript, API responses, or admin screens.
- Use a clear password-reset email containing the OTP, expiry, and a warning not to share it. Do not include the user's password or private data.
- Log delivery failures safely without OTPs or credentials. Define a safe retry/queue strategy if delivery fails.
- Use console/locmem email backends only in development/tests, not as an accidental production fallback. Production configuration should fail clearly if required email settings are absent when password-reset email is enabled.
- Respect provider sending limits and anti-abuse policies; do not rotate arbitrary third-party accounts to evade limits.

## 6. API and frontend expectations
Adapt endpoint names to existing conventions, but document equivalent operations for:
- Registration (username, email, password, confirmation).
- Login, token refresh, logout.
- Authenticated change password (current_password, new_password, confirmation).
- Forgot-password request (email).
- Verify OTP/reset password (email, otp, new_password, confirmation), either atomically in one endpoint or with a clearly defined two-step contract.
- Optional resend OTP endpoint with strict throttling.

Frontend must provide registration, sign-in, forgot-password, OTP entry, reset-password, and authenticated change-password forms with loading, success, invalid/expired OTP, password-policy, network-failure, and resend-cooldown states. Never claim a reset email was delivered unless the API contract confirms delivery; generic forgot-password responses may intentionally avoid confirming account existence. Keep OTPs out of browser storage and analytics. Do not cache authentication responses in the service worker.

## 7. Required security and functional tests
- Duplicate usernames/emails are rejected case-insensitively, including concurrent registration attempts.
- Invalid and weak passwords are rejected; password hashes use Django's password hasher.
- Public registration cannot assign privileged roles or flags.
- Login, refresh, logout, and ownership checks follow documented token behavior.
- Authenticated password change requires the correct current password and invalidates tokens/sessions according to policy.
- Forgot-password responses do not reveal whether an account exists.
- OTP delivery is tested with a mocked/test email backend.
- Correct, incorrect, expired, consumed, malformed, wrong-purpose, and over-attempt OTP cases are covered.
- OTP cannot be replayed; concurrent reset attempts result in at most one successful reset.
- Reset cannot target a different email or change account identity.
- Rate limits cover reset requests, resends, and OTP guesses.
- SMTP credentials and OTPs never appear in responses, logs, source control, or frontend bundles.
- Missing production mail configuration fails safely; test/development backends are explicit.
- Email sending failure, transaction rollback, and retry behavior are tested.

## 8. Definition of done
- Integrate with the existing user model and auth stack after inspection.
- Add migrations only when justified, update API docs and .env.example, and implement tests.
- Run relevant tests and report exact commands/results; do not claim unrun checks passed.
- Apply through the existing ordered milestones. Milestone 3 owns backend identity, OTP, email delivery, authorization, and security tests; Milestone 7/8 own frontend auth UX as appropriate.
- Do not deploy, configure a real Gmail account, or request secrets in chat. The owner supplies SMTP credentials directly in deployment secret configuration.
