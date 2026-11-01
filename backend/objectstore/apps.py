from django.apps import AppConfig


class ObjectStoreConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "objectstore"
    verbose_name = "Storage (Cloudflare R2)"

    def ready(self):
        # Imported for its side effect: registering the credential-key check.
        from . import checks  # noqa: F401
