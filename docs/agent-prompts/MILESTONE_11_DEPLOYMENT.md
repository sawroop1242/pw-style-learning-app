# Coding-Agent Prompt — Milestone 11: Reproducible Deployment and Operations

## Objective
Prepare and verify a real deployment path for the frontend, Django API, and persistent database. Prefer the simplest maintainable hosting architecture compatible with the repository and available user budget; do not assume a paid plan or secret access.

## Required deliverables
- Production start command and process configuration for Django/WSGI.
- PostgreSQL database configuration and safe migration procedure.
- Static asset collection and serving configuration appropriate to the chosen host.
- Environment variable reference with placeholders only: environment, secret key, debug, hosts, database URL, frontend origins, CSRF trusted origins, HTTPS/security settings, and any other required runtime settings.
- Frontend hosting instructions and explicit API base URL configuration.
- HTTPS, allowed hosts, CORS/CSRF, persistent storage, health endpoint, logs, backups/restore, migration ordering, and rollback guidance.
- Safe deployment smoke-test checklist and release procedure.
- No real credentials in repo, screenshots, CI logs, or documentation.

## Execution rules
1. Inspect current deployment files and the user's actual hosting target before selecting a provider.
2. If credentials/target access are unavailable, create a reproducible deploy guide and configuration but clearly mark deployment unverified.
3. Never deploy to a new paid resource or incur charges without explicit authorization.
4. Do not use SQLite as a production database for a multi-user hosted service unless a documented, justified single-instance limitation is explicitly accepted.
5. Do not run destructive migrations or reset production data.
6. Verify static assets, API health, login, course listing, private API protection, HTTPS, and database persistence in the target environment when access exists.

## Acceptance
A fresh maintainer can deploy without guessing; target-environment smoke tests pass or deployment is honestly marked unverified with a concrete blocker. Update README and build status with exact evidence. Stop before Milestone 12.
