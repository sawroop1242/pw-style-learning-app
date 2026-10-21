# Project memory

## Automation troubleshooting: KeyError 'AUTOMATION_AGENT_PROFILE_ID'
- This error means the automation has NO `agent_profile_id` bound; the dispatcher
  (`skills/github/scripts/agent_conversation.py:180`) reads it via `os.environ[]` (hard requirement).
- The automation service injects the var only when `automation.agent_profile_id` is set
  (`openhands/automation/dispatcher.py:633-634`).
- Fix flow that worked (2026-10-20, automation 58d8f960 "GitHub code review - sawroop1242/pw-style-learning-app"):
  1. `POST /api/agent-profiles/<name>` on `https://app.all-hands.dev` with `{"llm_profile_ref": "Default"}`
     (cloud LLM profile name is case-sensitive `Default`, NOT `default`).
  2. Validate with `POST /api/agent-profiles/<name>/materialize` → must report `"valid": true`.
  3. `PATCH /api/automation/v1/<id>` with `{"agent_profile_id": "<uuid>"}` (creator only).
  4. Dispatch a test run; the KeyError disappears and the run reaches COMPLETED.
- An agent profile owns the model: binding one clears the automation's `model` field.
- Retrying the failed run cannot fix this error — it is a config problem, not transient.

## StudySpace repo conventions (learned in M3, 2026-10-20)
- Repo: github.com/sawroop1242/pw-style-learning-app; backend at `backend/` (Django 5.2, DRF, simplejwt);
  verify evidence goes into `docs/BUILD_STATUS.md` per milestone, then commit+push to main.
- CI on GitHub Actions is blocked (private repo billing) - local runs of `manage.py check`,
  `makemigrations --check --dry-run`, `manage.py test`, `compileall -q config courses accounts`
  are the CI-equivalent checks; record exact commands + results in BUILD_STATUS.md.
- DRF throttling tests: SQLite test DB uses `cache=shared` so the default locmem throttle cache
  LEAKS between tests. Fix pattern used in accounts/tests.py: per-test-class
  `@override_settings(CACHES={"default": {"BACKEND": LocMemCache, "LOCATION": "<unique-per-class>"}})`
  PLUS `django.core.cache.cache.clear()` in `setUp()` of every class that hits throttled endpoints.
  Symptom of leakage: unrelated tests failing with 429 (e.g. weak-password test gets 429 not 400).
- M3 auth URLs (registered under `config/urls.py` -> `accounts.urls`): /api/token/, /api/token/refresh/,
  /api/auth/register|logout|me|change_password|forgot_password|verify_otp|resend_otp/ (ViewSet w/ router).
  /api/ root comes from `courses.urls` api_root - accounts.urls must be included AFTER courses.urls
  or /api/ returns {} and config.tests.test_api_root_is_reachable fails.
- Token endpoints live in accounts (CustomTokenObtainPairView accepts `username_or_email`);
  tests use locmem email backend and parse the OTP from `mail.outbox[0].body`.
