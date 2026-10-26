#!/bin/sh
# Deployment build steps, kept in a file because the host caps the inline
# build command at 256 characters.
#
# The management commands run from the repository root wrapper, so they behave
# exactly like `cd backend && python manage.py ...`.
#
# `collectstatic` is deliberately absent: the host's Django integration runs it
# itself and writes straight into the CDN output, which is where /static/ is
# served from. Running it a second time only produced a duplicate copy inside
# the function bundle.
set -e

python manage.py check
python manage.py migrate --noinput

if [ "$SEED_DEMO" = "1" ]; then
    python manage.py seed_demo
fi

python manage.py ensure_admin
