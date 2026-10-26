# Deploying StudySpace to Vercel (Django + Supabase Postgres)

One Vercel project serves the site, the API and the admin from the same origin.
No separate front-end host, no proxy middleware, no client-side base URL — the
front end calls the API with relative `/api/...` paths.

| Piece | Value |
|---|---|
| Vercel project | `studyspace` (`prj_700XAxzRHI6PtLBpJEKCt6jXXd91`), framework `django`, region `iad1` |
| Production branch | `main` → `https://studyspace-eta-tan.vercel.app` (public) |
| Database | Supabase project `studyspace` (`hcidfvqszalkggurfriw`), Postgres 17, `ap-south-1` |
| Entry point | `config/wsgi.py` at the repository root, named by `WSGI_APPLICATION` |
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

## How the function is found, and why the first deploys answered 500

Vercel's Django integration does **not** import `WSGI_APPLICATION` as a dotted
module. It splits the setting into a file path and loads that file, relative to
the directory that holds `manage.py`:

| Setting | File the host loads |
|---|---|
| `WSGI_APPLICATION = "config.wsgi.application"` | `config/wsgi.py` |
| `ASGI_APPLICATION = "config.asgi.application"` | `config/asgi.py` (wins when both are set) |

This project's Django package lives in `backend/config/`, so both settings
pointed at files that do not exist at the repository root. The lambda died at
start-up, before a single line of app code, which is why *every* URL answered
`500 FUNCTION_INVOCATION_FAILED` — even `/healthz/`, which needs no database —
while pre-built static files kept returning `200`.

The repair keeps one project, not a copy:

- `config/wsgi.py` and `config/asgi.py` exist at the root as thin entry points;
- `config/__init__.py` appends `backend/config` to the package search path and
  puts `backend/` on `sys.path`, so `config.settings`, `config.urls` and the
  `courses` / `accounts` apps are the same modules `manage.py` uses;
- only `WSGI_APPLICATION` is set — with both set, the host picks ASGI and the
  WSGI server refuses to start.

If the project is ever moved so that `manage.py` sits beside `settings.py`,
these two files become one-line `get_wsgi_application()` calls and the indirection
can go.

## Build pipeline

`vercel.json` runs `sh tools/vercel-build.sh`, which is:

```
manage.py check  →  migrate  →  seed_demo (SEED_DEMO=1)  →  ensure_admin
```

`collectstatic` is **not** in that script: the host's Django integration runs it
itself and writes straight into the CDN output that serves `/static/`. Running it
twice only duplicated the files inside the function bundle. The build command is
a file because the host caps an inline build command at 256 characters.

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
(`ssoProtection: all_except_custom_domains`). The `all_except_custom_domains`
part is what matters: the **production alias is a custom domain and is
therefore public**, while a per-deployment URL
(`studyspace-<hash>-<team>.vercel.app`) and the branch alias are not — those
redirect an anonymous browser to a Vercel login before Django is reached.

In practice: smoke-test and share `https://studyspace-eta-tan.vercel.app`
(the production alias). A link copied from the dashboard's "Visit" button
points at a deployment URL and will show the Vercel login instead.

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
BASE=https://studyspace-eta-tan.vercel.app
curl -s -o /dev/null -w '%{http_code}\n' $BASE/                 # 200, home page
curl -s -o /dev/null -w '%{http_code}\n' $BASE/tests.html       # 200
curl -s $BASE/healthz/ready/                                    # {"status": "ok", ...}
curl -s $BASE/api/quizzes/ | head -c 200                        # catalogue JSON
curl -s -o /dev/null -w '%{http_code}\n' $BASE/admin/login/     # 200, styled
```

Then sign in at `/admin/` with `ADMIN_USERNAME` / `ADMIN_PASSWORD` and confirm
the CSV import flow: **CSV import jobs → Add** → *Validate the selected files* →
*Import the selected files*.
