"""The admin screen for Cloudflare R2 storage.

Two pages, because a person thinks in two things: an account (the Cloudflare
login that owns buckets) and a bucket (the thing files go into). The account
page carries its buckets inline, so setting up storage is one screen — paste
the token, add a bucket, press "Test connection" — not a hunt through six model
lists.

What a sub-admin can reach is limited by ownership: their own accounts, and the
buckets under them. A main admin sees every account but never a secret; the
form is write-only and the stored value is ciphertext.
"""

from __future__ import annotations

from django.contrib import admin, messages
from django.core.exceptions import PermissionDenied
from django.db.models import Count
from django.http import HttpResponseRedirect
from django.urls import path, reverse
from django.utils.html import format_html

from config.admin_ui import pill

from accounts.models import AuditEvent
from accounts.roles import is_main_admin, is_staff_role

from .forms import R2AccountAdminForm, R2BucketForm
from .models import Purpose, R2Account, R2Bucket
from .services import test_account, test_bucket


def _badge(ok, label: str) -> str:
    """The console's status chip: one shape and one palette for every answer."""
    kind = "muted" if ok is None else ("ok" if ok else "bad")
    return pill(label, kind)


def _audit(actor, action: str, obj, outcome: str = "success", **metadata) -> None:
    AuditEvent.objects.create(
        actor=actor if getattr(actor, "is_authenticated", False) else None,
        action=action,
        target_type=type(obj).__name__,
        target_id=str(getattr(obj, "pk", "")),
        outcome=outcome,
        metadata={
            key: value
            for key, value in metadata.items()
            if isinstance(value, (str, int, float, bool)) or value is None
        },
    )


class StaffConsoleMixin:
    """Only staff roles use this app; the role decides, not model permissions."""

    def has_module_permission(self, request):
        return is_staff_role(request.user)

    def has_view_permission(self, request, obj=None):
        if not is_staff_role(request.user):
            return False
        if obj is None or is_main_admin(request.user):
            return True
        return self.get_queryset(request).filter(pk=obj.pk).exists()

    def has_add_permission(self, request):
        return is_staff_role(request.user)

    def has_change_permission(self, request, obj=None):
        return self.has_view_permission(request, obj)

    def has_delete_permission(self, request, obj=None):
        return self.has_view_permission(request, obj)

    def changelist_view(self, request, extra_context=None):
        extra_context = dict(extra_context or {})
        extra_context.setdefault(
            "title", str(self.model._meta.verbose_name_plural).capitalize()
        )
        return super().changelist_view(request, extra_context)


class R2BucketInline(admin.TabularInline):
    """Buckets, edited on the account that owns them."""

    model = R2Bucket
    form = R2BucketForm
    extra = 1
    fields = (
        "name",
        "public_base_url",
        "enabled",
        "allow_community_images",
        "allow_course_images",
        "allow_pdfs",
        "is_default_community",
        "is_default_course_images",
        "is_default_pdfs",
        "status_column",
    )
    readonly_fields = ("status_column",)
    verbose_name = "bucket"
    verbose_name_plural = "Buckets in this account"

    def has_add_permission(self, request, obj):
        return is_staff_role(request.user)

    def has_view_permission(self, request, obj):
        return is_staff_role(request.user)

    def has_change_permission(self, request, obj):
        return is_staff_role(request.user)

    def has_delete_permission(self, request, obj):
        return is_staff_role(request.user)

    @admin.display(description="Last test")
    def status_column(self, obj):
        if obj is None or not obj.pk:
            return "—"
        if obj.last_check_ok is None:
            return _badge(None, "Not tested")
        label = "Connected" if obj.last_check_ok else "Failed"
        return _badge(obj.last_check_ok, f"{label} · {obj.last_check_detail}")


@admin.register(R2Account)
class R2AccountAdmin(StaffConsoleMixin, admin.ModelAdmin):
    form = R2AccountAdminForm
    inlines = [R2BucketInline]
    list_display = (
        "name",
        "owner",
        "account_column",
        "bucket_summary",
        "credential_column",
        "status_column",
        "last_checked_at",
    )
    list_filter = ("is_active", "last_check_ok")
    search_fields = ("name", "account_id", "owner__username", "owner__email")
    ordering = ("name",)
    save_on_top = True
    actions = ("test_all_buckets",)
    readonly_fields = (
        "endpoint_column",
        "credential_state",
        "status_column",
        "last_checked_at",
        "access_key_hint",
    )
    # A field named in a fieldset may be made read-only but not excluded, or
    # Django raises KeyError while rendering the change page. Sub-admins keep
    # their own account as owner and see the value greyed out.
    always_readonly = ("owner",)
    fieldsets = (
        (
            "The Cloudflare account",
            {
                "fields": ("name", "account_id", "owner", "is_active"),
                "description": (
                    "An account id names the Cloudflare account, not a bucket. "
                    "Add one entry per Cloudflare login; each may hold several buckets."
                ),
            },
        ),
        (
            "API token",
            {
                "fields": ("access_key_id", "secret_access_key", "credential_state"),
                "description": (
                    "Cloudflare dashboard → R2 → Manage R2 API Tokens → Create API "
                    "token, with Object Read &amp; Write on the bucket. The pair is "
                    "encrypted before it is stored and is never shown again. Leaving "
                    "both boxes empty on an existing account keeps the stored token."
                ),
            },
        ),
        (
            "Connection",
            {
                "fields": ("endpoint_column", "status_column", "last_checked_at"),
                "description": (
                    "Use “Test connection” on a bucket (or the action in the list) "
                    "after adding one. The test lists a single object — it never "
                    "changes anything in the bucket."
                ),
            },
        ),
    )

    # -- queryset and ownership -------------------------------------------

    def get_queryset(self, request):
        queryset = (
            super()
            .get_queryset(request)
            .select_related("owner")
            .annotate(bucket_total=Count("buckets", distinct=True))
        )
        if is_main_admin(request.user):
            return queryset
        return queryset.filter(owner=request.user)

    def get_readonly_fields(self, request, obj=None):
        fields = list(super().get_readonly_fields(request, obj))
        if not is_main_admin(request.user):
            fields.extend(self.always_readonly)
        return fields

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "owner" and not is_main_admin(request.user):
            kwargs["queryset"] = type(request.user).objects.filter(pk=request.user.pk)
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    def get_changeform_initial_data(self, request):
        initial = super().get_changeform_initial_data(request)
        initial.setdefault("owner", request.user.pk)
        return initial

    def save_model(self, request, obj, form, change):
        if not change and not getattr(obj, "owner_id", None):
            obj.owner = request.user
        if change and not is_main_admin(request.user):
            original = R2Account.objects.only("owner_id").get(pk=obj.pk)
            if original.owner_id != obj.owner_id:
                raise PermissionDenied("Ownership cannot be reassigned.")
        super().save_model(request, obj, form, change)
        rotated = bool(form.cleaned_data.get("secret_access_key")) and change
        if rotated:
            action = "r2.account.rotate"
        elif change:
            action = "r2.account.update"
        else:
            action = "r2.account.create"
        _audit(request.user, action, obj, credential_rotated=rotated)

    def delete_model(self, request, obj):
        _audit(request.user, "r2.account.delete", obj, buckets=obj.bucket_count)
        super().delete_model(request, obj)

    def delete_queryset(self, request, queryset):
        for account in queryset:
            _audit(request.user, "r2.account.delete", account, buckets=account.bucket_count)
        super().delete_queryset(request, queryset)

    # -- columns -----------------------------------------------------------

    @admin.display(description="Account id", ordering="account_id")
    def account_column(self, obj):
        return format_html("<code>{}</code>", obj.masked_account_id())

    @admin.display(description="Buckets")
    def bucket_summary(self, obj):
        total = getattr(obj, "bucket_total", None)
        if total is None:
            total = obj.bucket_count
        if not total:
            return format_html('<span style="color:#b91c1c">none yet</span>')
        return f"{total} · {obj.connected_bucket_count} connected"

    @admin.display(description="Token")
    def credential_column(self, obj):
        if not obj.has_credentials():
            return format_html('<span style="color:#b91c1c">missing</span>')
        return format_html("<code>{}</code>", obj.access_key_hint or "stored")

    @admin.display(description="Connection")
    def status_column(self, obj):
        if not obj.is_active:
            return _badge(None, "Switched off")
        if not obj.has_credentials():
            return _badge(False, "No API token")
        if obj.last_check_ok is None:
            return _badge(None, "Not tested yet")
        return _badge(obj.last_check_ok, "Connected" if obj.last_check_ok else "Failed")

    @admin.display(description="Endpoint")
    def endpoint_column(self, obj):
        if not obj.account_id:
            return "—"
        return format_html(
            '<code>{}</code><br><span class="help">Every bucket in this account '
            "lives at that address.</span>",
            obj.endpoint,
        )

    @admin.display(description="Stored token")
    def credential_state(self, obj):
        if obj is None or not obj.pk:
            return "The token is encrypted as soon as you save."
        if not obj.has_credentials():
            return format_html('<span style="color:#b91c1c">No token stored.</span>')
        return format_html(
            "Encrypted and stored ({}). It cannot be read back from this page.",
            obj.access_key_hint or "stored",
        )

    # -- actions -----------------------------------------------------------

    @admin.action(description="Test the connection to every bucket in these accounts")
    def test_all_buckets(self, request, queryset):
        ok = failed = 0
        for account in queryset:
            for _bucket, verdict in test_account(account, actor=request.user):
                ok += 1 if verdict.ok else 0
                failed += 0 if verdict.ok else 1
        if not (ok or failed):
            self.message_user(
                request,
                "No buckets to test yet — add one under the account first.",
                messages.WARNING,
            )
            return
        level = messages.SUCCESS if not failed else messages.WARNING
        self.message_user(
            request,
            f"{ok} bucket(s) connected, {failed} failed. The reason is on each bucket.",
            level,
        )


@admin.register(R2Bucket)
class R2BucketAdmin(StaffConsoleMixin, admin.ModelAdmin):
    form = R2BucketForm
    list_display = (
        "name",
        "account",
        "owner_column",
        "purposes_column",
        "defaults_column",
        "enabled",
        "status_column",
        "last_checked_at",
    )
    list_filter = ("enabled", "last_check_ok", "account")
    search_fields = ("name", "account__name", "account__owner__username")
    autocomplete_fields = ("account",)
    ordering = ("account__name", "name")
    actions = ("test_selected",)
    readonly_fields = ("status_detail", "last_checked_at", "test_link")
    fieldsets = (
        (
            "The bucket",
            {
                "fields": ("account", "name", "public_base_url", "enabled"),
                "description": (
                    "The name must match Cloudflare exactly. A public base URL "
                    "(custom domain or the r2.dev address) makes files permanently "
                    "readable; without one, links are signed and expire."
                ),
            },
        ),
        (
            "What it may hold",
            {
                "fields": (
                    "allow_community_images",
                    "allow_course_images",
                    "allow_pdfs",
                    "is_default_community",
                    "is_default_course_images",
                    "is_default_pdfs",
                ),
                "description": (
                    "Tick every purpose this bucket serves. Ticking a default moves "
                    "that default off whichever bucket held it before — one default "
                    "per purpose, per owner."
                ),
            },
        ),
        ("Connection", {"fields": ("status_detail", "last_checked_at", "test_link")}),
    )

    def get_queryset(self, request):
        queryset = super().get_queryset(request).select_related("account", "account__owner")
        if is_main_admin(request.user):
            return queryset
        return queryset.filter(account__owner=request.user)

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "account" and not is_main_admin(request.user):
            kwargs["queryset"] = R2Account.objects.filter(owner=request.user)
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        _audit(
            request.user,
            "r2.bucket.update" if change else "r2.bucket.create",
            obj,
            bucket=obj.name,
            enabled=obj.enabled,
        )

    def delete_model(self, request, obj):
        _audit(request.user, "r2.bucket.delete", obj, bucket=obj.name)
        super().delete_model(request, obj)

    @admin.display(description="Owner")
    def owner_column(self, obj):
        return obj.account.owner

    @admin.display(description="Purposes")
    def purposes_column(self, obj):
        labels = obj.purposes
        if labels:
            return ", ".join(labels)
        return format_html('<span style="color:#b91c1c">none</span>')

    @admin.display(description="Defaults")
    def defaults_column(self, obj):
        labels = [f"★ {label}" for purpose, label in Purpose.choices if obj.is_default_for(purpose)]
        return ", ".join(labels) or "—"

    @admin.display(description="Connection")
    def status_column(self, obj):
        if not obj.enabled:
            return _badge(None, "Bucket switched off")
        if not obj.account.is_active:
            return _badge(None, "Account switched off")
        if obj.last_check_ok is None:
            return _badge(None, "Not tested yet")
        return _badge(obj.last_check_ok, "Connected" if obj.last_check_ok else "Failed")

    @admin.display(description="Last result")
    def status_detail(self, obj):
        if obj is None or not obj.pk:
            return "Save the bucket, then test the connection."
        if obj.last_check_ok is None:
            return "Not tested yet."
        return obj.last_check_detail or "—"

    @admin.display(description="Test")
    def test_link(self, obj):
        if obj is None or not obj.pk:
            return "—"
        url = reverse("admin:objectstore_r2bucket_test", args=[obj.pk])
        return format_html('<a class="button" href="{}">Test the connection now</a>', url)

    @admin.action(description="Test the connection to these buckets")
    def test_selected(self, request, queryset):
        ok = failed = 0
        for bucket in queryset:
            verdict = test_bucket(bucket, actor=request.user)
            ok += 1 if verdict.ok else 0
            failed += 0 if verdict.ok else 1
        level = messages.SUCCESS if not failed else messages.WARNING
        self.message_user(
            request,
            f"{ok} bucket(s) connected, {failed} failed. The reason is on each row.",
            level,
        )

    # -- one-bucket test ---------------------------------------------------

    def get_urls(self):
        custom = [
            path(
                "<path:object_id>/test/",
                self.admin_site.admin_view(self.test_view),
                name="objectstore_r2bucket_test",
            )
        ]
        return custom + super().get_urls()

    def test_view(self, request, object_id):
        bucket = self.get_object(request, object_id)
        if bucket is None:
            self.message_user(request, "That bucket does not exist.", messages.ERROR)
        else:
            verdict = test_bucket(bucket, actor=request.user)
            self.message_user(
                request,
                f"{bucket.name}: {verdict.message}",
                messages.SUCCESS if verdict.ok else messages.ERROR,
            )
        return HttpResponseRedirect(reverse("admin:objectstore_r2bucket_changelist"))
