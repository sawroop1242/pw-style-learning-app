"""Make username and email unique case-insensitively *in the database*.

Two registrations racing each other both passed the serializer's `.exists()`
check and created `Alice` and `alice`; from then on `email__iexact` lookups in
the login and password-reset paths could raise `MultipleObjectsReturned`.

Django's `User` lives in `auth`, so the constraint is added as a raw index
rather than an `AddConstraint` on a model this migration does not own:

    CREATE UNIQUE INDEX ... ON auth_user (LOWER(username))
    CREATE UNIQUE INDEX ... ON auth_user (LOWER(email)) WHERE email <> ''

Both statements are valid on SQLite and PostgreSQL; the email index is partial
because Django allows several accounts with a blank email (superusers created
from the command line).

Existing duplicates are renamed first, deterministically: the oldest row keeps
its name, and each later one gets a suffix derived from its primary key. Leaving
them would make the migration fail on the very deployment that needs it, and
leaving them *and* letting the index fail silently is worse — an ambiguous
email means the reset flow refuses to send anything to that address.
"""

from django.db import migrations

CREATE_USERNAME_INDEX = """
CREATE UNIQUE INDEX IF NOT EXISTS accounts_user_username_lower_uniq
    ON auth_user (LOWER(username))
"""

CREATE_EMAIL_INDEX = """
CREATE UNIQUE INDEX IF NOT EXISTS accounts_user_email_lower_uniq
    ON auth_user (LOWER(email))
    WHERE email <> ''
"""

DROP_USERNAME_INDEX = "DROP INDEX IF EXISTS accounts_user_username_lower_uniq"
DROP_EMAIL_INDEX = "DROP INDEX IF EXISTS accounts_user_email_lower_uniq"


def deduplicate(apps, schema_editor):
    """Give every case-collision a distinct name and address.

    The lowest id keeps the original; later rows get ``-<id>`` appended to the
    username and ``+dup<id>`` inserted into the email's local part, both of
    which stay valid for their fields and unique by construction.
    """
    User = apps.get_model("auth", "User")
    seen_names = {}
    seen_emails = {}
    for user in User.objects.all().order_by("id"):
        lowered = (user.username or "").lower()
        if lowered in seen_names:
            user.username = f"{user.username}-{user.id}"
        else:
            seen_names[lowered] = user.id

        email = (user.email or "").strip()
        if email:
            lowered_email = email.lower()
            if lowered_email in seen_emails:
                local, _, domain = email.partition("@")
                user.email = f"{local}+dup{user.id}@{domain}"
            else:
                seen_emails[lowered_email] = user.id

        user.save(update_fields=["username", "email"])


def reverse(apps, schema_editor):
    """Dropping the indexes is the reverse; renames are not undone.

    Restoring the old colliding names would re-create the ambiguity this
    migration exists to remove.
    """


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0001_initial"),
        ("auth", "0012_alter_user_first_name_max_length"),
    ]

    operations = [
        migrations.RunPython(deduplicate, reverse),
        migrations.RunSQL(CREATE_USERNAME_INDEX, DROP_USERNAME_INDEX),
        migrations.RunSQL(CREATE_EMAIL_INDEX, DROP_EMAIL_INDEX),
    ]
