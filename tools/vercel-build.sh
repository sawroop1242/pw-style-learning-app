#!/bin/sh
# Deployment build steps, kept in a file because the host caps the inline
# build command at 256 characters.
#
# The first step imports the serverless handler exactly the way the platform
# will. It is deliberately first: an import error then fails the build with a
# readable traceback instead of turning every request into a blank 500.
set -e

python -c "import api.index as m; print('wsgi handler:', type(m.app).__name__)"

python manage.py collectstatic --noinput
python manage.py migrate --noinput

if [ "$SEED_DEMO" = "1" ]; then
    python manage.py seed_demo
fi

python manage.py ensure_admin
