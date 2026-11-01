# Password-reset email: what actually happens

Audit of the "forgot password" path, done by running it rather than reading it.
Date: 2026-11-01.

## The short version

The code, the storage and the verification logic are correct. **The deployment
could not send the email**, and nothing anywhere said so: every reset request
answered "a password reset code has been sent" while the message stayed inside
the web process and the row sat in the table as a live reset.

Fixing the transport is a configuration change only the owner can make (a real
SMTP account). Everything that can be fixed in code now fails loudly instead of
quietly.

## What was verified working

Run against a local server (`runserver` on port 8011) using a real SMTP
transport pointed at a local debugging server, with a seeded demo account.

| Step | Request | Result |
| --- | --- | --- |
| Request a code | `POST /api/auth/forgot-password/ {"email": "demo@studyspace.example"}` | `200` `{"message": "If an account with that email exists, a password reset code has been sent."}` |
| Same, unknown address | `POST` with `nobody@example.com` | `200`, identical body — no account enumeration |
| Message actually sent | SMTP debugging server log | `From: StudySpace <no-reply@studyspace.test>`, `Subject: Your StudySpace Password Reset Code`, body contains the six-digit code, "expires in 10 minutes", "can only be used once" |
| Two requests in a row | two `POST`s | different codes; the first row is stamped `consumed_at`, only one active row remains |
| Wrong code | `POST /api/auth/verify-otp/` with `000000` | `400` `{"detail": "Invalid reset code."}` |
| Correct code | `POST /api/auth/verify-otp/` with the mailed code | `200` `{"message": "Password has been reset successfully."}` |
| Replay the same code | same request again | `400` `{"detail": "Invalid or expired reset code."}` |

What the code store does, read from `accounts/models.py` and confirmed in the
run: the six digits are generated with `secrets.randbelow`, stored only as an
HMAC-SHA256 over `SECRET_KEY`, compared with `hmac.compare_digest`, capped at
`OTP_MAX_ATTEMPTS` tries, expired at `OTP_EXPIRY_MINUTES`, consumed inside an
atomic block together with `set_password`, and limited by a partial unique
constraint to one active row per user.

The frontend payload matches the backend contract exactly
(`frontend/assets/js/auth.js`).

## What was broken

### 1. No mail transport in the deployment — the reset mail could not be sent at all

`ENVIRONMENT=production` and `DEBUG=false` resolve `EMAIL_BACKEND` to the SMTP
backend. The Vercel project has no `EMAIL_HOST`, `EMAIL_PORT`,
`EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD` or `DEFAULT_FROM_EMAIL`. Settings fall
back to `localhost:587`, and a Vercel function has no SMTP server next to it.

Reproduced locally by loading the same settings (`ENVIRONMENT=production`,
`DEBUG=false`, a 60-character `SECRET_KEY`):

```
EMAIL_BACKEND = django.core.mail.backends.smtp.EmailBackend
EMAIL_HOST    = ''
EMAIL_PORT    = 587
EMAIL_TIMEOUT = None
send_mail(...) -> SMTPServerDisconnected: please run connect() first
```

Because `forgot_password` deliberately swallows the exception (it must not tell
a stranger that the mailbox is dead), the API answered `200`, the frontend
showed "code sent", and the user waited for a mail that was never generated
outside the process.

### 2. The failed code stayed in the table as an active reset

The OTP row was created before the send. When the send raised, the row stayed,
`consumed_at` empty, so the app believed an active reset existed for that user.
Nobody held the code, so the row could never be used — but it still blocked a
clean retry and told the console a reset was in flight.

### 3. The letter promised a fixed expiry

The body said "This code expires in 10 minutes" as a literal, while the row used
`OTP_EXPIRY_MINUTES`. Changing the setting would have made the letter lie.

### 4. No timeout on the SMTP connection

`EMAIL_TIMEOUT` was unset. The code is generated and mailed inside the request,
so an unresponsive provider holds the HTTP request open until the platform kills
it.

### 5. An address shared by two accounts produced a 500

`User.email` is not unique (registration checks it in the serializer, not in the
database), so `User.objects.get(email__iexact=...)` could raise
`MultipleObjectsReturned`. Same in `verify_otp`, where only `DoesNotExist` was
caught.

### 6. Users with a blank email address got a dead row

A user whose `email` is empty still matched and got an OTP row, and the send
targeted an empty address.

## What changed

- `accounts/checks.py` — `accounts.W001` (SMTP backend with an empty
  `EMAIL_HOST`) and `accounts.W002` (sender is still
  `noreply@studyspace.local`). `tools/vercel-build.sh` runs `manage.py check`,
  so both appear in the deploy log; the admin console home shows the same
  sentence as a banner.
- `manage.py check_email [--to you@example.com]` — prints backend, host, port,
  encryption, timeout and sender; opens the connection; with `--to` sends a real
  message; exits non-zero on failure. Verified both ways: `127.0.0.1:1025` →
  "connected in 1 ms / message handed to the server in 44 ms", exit `0`; port
  `1999` → `CommandError: could not open the mail connection
  (ConnectionRefusedError: [Errno 111] Connection refused)`, exit `1`.
- A failed send now deletes the OTP row. The attempt remains as
  `AuditEvent(action="password_reset_requested", outcome="email_failed")` and a
  log line carrying the user id and the exception type — never the address, the
  code or the credentials.
- The letter's expiry text comes from `OTP_EXPIRY_MINUTES`.
- `EMAIL_TIMEOUT` (default 10s, env `EMAIL_TIMEOUT`).
- Addresses shared by two accounts: generic `200`, `AuditEvent` outcome
  `ambiguous_email`, no message sent; `verify-otp` returns `400` rather than
  raising.
- Blank-address accounts: generic `200`, `AuditEvent` outcome
  `no_email_address`, no row, no message.

Verified after the change by driving the endpoint with the SMTP transport
pointed at a closed port:

```
ERROR accounts.views password reset email could not be sent for user 1 (ConnectionRefusedError): [Errno 111] Connection refused
status: 200 {"message":"If an account with that email exists, a password reset code has been sent."}
active OTP rows before/after: 0 0
last audit: email_failed {'email_sent': False}
```

## What the owner still has to do

Email cannot be *delivered* from the deployment until real SMTP credentials
exist in Vercel. In **Project → Settings → Environment Variables** (Production):

| Variable | Value |
| --- | --- |
| `EMAIL_BACKEND` | `django.core.mail.backends.smtp.EmailBackend` |
| `EMAIL_HOST` | your provider's host, e.g. `smtp.gmail.com` |
| `EMAIL_PORT` | `587` for STARTTLS, `465` for SSL |
| `EMAIL_USE_TLS` | `true` for 587, **`false`** for 465 |
| `EMAIL_USE_SSL` | `false` for 587, **`true`** for 465 |
| `EMAIL_HOST_USER` | the sending account |
| `EMAIL_HOST_PASSWORD` | an app password — never the normal account password |
| `DEFAULT_FROM_EMAIL` | `StudySpace <your-address>` |
| `EMAIL_TIMEOUT` | `10` |

For Gmail this needs 2-Step Verification and an App Password; Google does not
accept the account password over SMTP. Any provider with SMTP works — the code
is provider-neutral.

Then redeploy and prove it from the deployment:

```
python manage.py check_email --to your-own-address@example.com
```

Until that prints "message handed to the server", the app deploys with
`accounts.W001` in the log and a banner on the admin home, and password reset
answers 200 without sending anything.

## Not changed, on purpose

`forgot_password` still returns the same generic message whether the address
exists, is shared, is blank or fails to send. That is required by
`docs/FEATURE_SPEC_AUTHENTICATION.md` §4 and it is the behaviour the frontend
copy ("If that email has an account, a code is on its way") is written against.
