# Deploying StudySpace to Vercel (Django + Supabase Postgres)

One Vercel project serves the site, the API and the admin from the same origin.
No separate front-end host, no proxy middleware, no client-side base URL — the
front end calls the API with relative `/api/...` paths.

| Piece | Value |
|---|---|
| Vercel project | `studyspace` (`prj_700XAxzRHI6PtLBpJEKCt6jXXd91`), framework `django`, region `iad1` |
| Production branch | `main` → `https://studyspace-swroopss487-4609.vercel.app` |
| Database | Supabase project `studyspace` (`hcidfvqszalkggurfriw`), Postgres 17, `ap-south-1` |
| Entry point | `manage.py` at the repository root (Vercel's Django detection needs it there) |
| Pins | `requirements.txt` at the repository root — Vercel does **not** follow `-r` includes |

## Environment variables

Names and shapes only; values live in the Vercel project settings, never in Git.

| Variable | Notes |
|---|---|
| `SECRET_KEY` | ≥ 50 random characters, encrypted |
| `ENVIRONMENT` | `production` |
| `DEBUG` | `false` |
| `ALLOWED_HOSTS` | `.vercel.app` (leading dot matches every sub-domain) |
| `CSRF_TRUSTED_ORIGINS` | `https://*.vercel.app` — add a custom domain here before using it |
| `SECURE_SSL_REDIRECT` | `false`; Vercel terminates TLS and forwards `X-Forwarded-Proto` |
| `DATABASE_URL` | Supavisor **session-mode** pooler, `sslmode=require`, user `postgres.<project-ref>` |
| `DB_CONN_MAX_AGE` | `0` on serverless — a connection held between invocations is a leak |
| `ADMIN_USERNAME` / `ADMIN_EMAIL` | administrator identity created by `ensure_admin` |
| `ADMIN_PASSWORD` | encrypted; only used when the account is first created |
| `SEED_DEMO` | `1` to load the demo catalogue on every build (idempotent) |

The Supabase **direct** host (`db.<ref>.supabase.co`) is IPv6-only and a Vercel
function cannot reach it. Use the pooler on port 5432 (session mode). If session
mode is unavailable, port 6543 with `?pgbouncer=true` (transaction mode) also
works, at the cost of real prepared statements.

## Build pipeline (`vercel.json`)

```
collectstatic  →  migrate  →  seed_demo (SEED_DEMO=1)  →  ensure_admin
```

A deploy therefore cannot come up with an unmigrated database, an empty
catalogue or a missing administrator. Every step is idempotent:

- `migrate` is a no-op once the schema is current.
- `seed_demo` uses `update_or_create` throughout.
- `ensure_admin` creates the account once, and afterwards only promotes it —
  a password changed in the UI survives redeploys. `--set-password` forces it.

`.vercelignore` must not list `backend/staticfiles`: `collectstatic` generates it
during the build and the admin needs it.

## Health probes

| URL | Meaning |
|---|---|
| `/healthz/` | liveness, no database access |
| `/healthz/ready/` | `SELECT 1`; `200` when the database answers, `503` with the exception **class name** only |

## Deployment protection (one-time, and it is not a code setting)

A new Vercel project is created with **Vercel Authentication** enabled
(`ssoProtection: all_except_custom_domains`). That protects every `*.vercel.app`
URL — preview *and* production — so an anonymous browser is redirected to a
Vercel login page before Django is ever reached.

To make the site public:

1. Vercel dashboard → project **studyspace** → **Settings** → **Deployment Protection**.
2. Set **Vercel Authentication** to **Disabled** (or scope it to "Standard
   Protection" off) and save.
3. Reload the production URL in a private window — it should now render the
   StudySpace home page and `GET /api/quizzes/` should return the catalogue.

Attaching a custom domain also lifts the wall for that domain
(`all_except_custom_domains`), but the `*.vercel.app` aliases stay protected.

## Smoke test after a deploy

```bash
BASE=https://studyspace-swroopss487-4609.vercel.app
curl -s -o /dev/null -w '%{http_code}\n' $BASE/                 # 200, home page
curl -s -o /dev/null -w '%{http_code}\n' $BASE/tests.html       # 200
curl -s $BASE/healthz/ready/                                    # {"status": "ok", ...}
curl -s $BASE/api/quizzes/ | head -c 200                        # catalogue JSON
curl -s -o /dev/null -w '%{http_code}\n' $BASE/admin/login/     # 200, styled
```

Then sign in at `/admin/` with `ADMIN_USERNAME` / `ADMIN_PASSWORD` and confirm
the CSV import flow: **CSV import jobs → Add** → *Validate the selected files* →
*Import the selected files*.
