# Coding-Agent Prompt — Milestone 1: Verify and Stabilize the Django Foundation

## Objective
Finish Milestone 1 of StudySpace. This milestone is **not complete** until real checks pass. Diagnose why the current GitHub Actions job reports failure before visible steps, and validate the existing Django foundation. Do not start models/admin work.

## Required first actions
1. Read `docs/BUILD_MASTER_PROMPT.md`, `docs/IMPLEMENTATION_PLAN.md`, and `docs/BUILD_STATUS.md`.
2. Inspect `git status`, repository files, workflow configuration, dependency constraints, settings, URL routes, current models/migrations, and tests. Preserve uncommitted user changes.
3. Inspect the actual Actions run details and runner/job logs. Determine whether the issue is workflow syntax, GitHub Actions availability/permissions, runner startup, or a real command failure. Do not infer the cause from a red badge alone.
4. Use the Python version supported by the repository and dependencies; document it.

## Implementation and verification tasks
- Create a clean virtual environment and install `backend/requirements.txt`.
- Run Django system checks, migration consistency, Django tests, and Python compilation.
- Check the health endpoint, API root, and admin URL using Django's test client or local server.
- Verify environment behavior in separate processes: development defaults work; staging/production refuse missing secret/hosts or `DEBUG=True`; malformed boolean values fail clearly.
- Review current settings for security issues introduced by this foundation change. Avoid silently weakening production checks.
- Fix actual defects discovered by the commands, add focused regression tests, and rerun the relevant checks.
- Inspect the CI workflow syntax and job output. Fix workflow problems if the evidence points to the workflow. Do not add secrets to CI.
- Keep test configuration explicit and isolated from production settings.

## Required commands
Run from `backend/` where applicable:
```bash
python --version
python -m pip install -r requirements.txt
python manage.py check
python manage.py makemigrations --check --dry-run
python manage.py test
python -m compileall -q config courses
```
Also run `node --check frontend/app.js` from repository root if Node is available, but report it as a separate frontend check.

## Acceptance criteria
- Dependencies install successfully in a clean environment.
- Django system check, migration consistency, tests, and compile checks pass.
- Environment guard tests demonstrate safe failures for invalid production configuration.
- CI runs actual steps and provides actionable results, or a reproducible platform/permission blocker is documented.
- Exact commands, exit statuses, and failures are recorded in `docs/BUILD_STATUS.md`.
- `docs/IMPLEMENTATION_PLAN.md` accurately reflects evidence.
- Stop before Milestone 2. If a check cannot run, do not mark the milestone complete; state what is needed to unblock it.
