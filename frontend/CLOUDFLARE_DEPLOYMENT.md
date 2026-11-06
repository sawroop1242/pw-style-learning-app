# Cloudflare Pages deployment

## Project settings

Create a Cloudflare Pages project from the GitHub repository
`sawroop1242/pw-style-learning-app`.

- Production branch: `main`
- Root directory: `frontend`
- Framework preset: None
- Build command: leave empty
- Build output directory: `.`
- Deploy command: managed by Cloudflare Pages

The frontend is static HTML/CSS/JavaScript. The Pages Functions in
`functions/` proxy Django routes to the existing Vercel backend so browser
requests remain same-origin.

## Environment variable

Set this Pages variable for Production and Preview:

`BACKEND_ORIGIN=https://studyspace-swroopss487-4609.vercel.app`

This is a public backend origin, not a secret. Update it if the backend's
stable production domain changes.

## Routes proxied to Django

- `/api/*`
- `/auth/*`
- `/token/*`
- `/admin/*`
- `/healthz/*`
- `/static/*` — Django's own admin CSS, JavaScript and images

The last one is not optional. `/admin/` returns HTML that links its stylesheet at
`/static/admin/css/base.css`; without that route the admin console loads and
paints unstyled, which looks like a front-end defect and is not one.

The app's own assets live under `/assets/`, so they never collide with Django's
`/static/`. Static frontend assets are served directly by Cloudflare Pages. Do
not add a catch-all function because that would intercept those files.

## Supabase

Keep the existing Supabase PostgreSQL database and its current connection
settings in the Django backend. Do not add Supabase service-role or database
secrets to Cloudflare Pages frontend variables.

## After first deployment

1. Test `/healthz/` and one read-only API endpoint.
2. Test login, logout, OTP, quiz submission, progress saving, admin, PDFs
   and video playback.
3. Confirm Django CSRF and allowed-host settings for the Pages domain.
4. Confirm cookies are Secure and HttpOnly where appropriate.
5. Verify the PWA manifest, service worker scope and offline fallback.
6. Only after tests pass, point the public app domain to Cloudflare Pages.

Keep the existing Vercel frontend deployment available as rollback until
Cloudflare production is verified.
