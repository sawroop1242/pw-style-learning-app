from django.apps import AppConfig


class AccountsConfig(AppConfig):
    name = "accounts"
    default_auto_field = "django.db.models.BigAutoField"

    def ready(self):
        # Imported for its side effect: registering the email-delivery checks.
        from . import checks  # noqa: F401
