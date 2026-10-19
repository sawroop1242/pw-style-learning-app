from django.contrib import admin

from .models import AuditEvent, PasswordResetOTP, Profile, Role


@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "role", "created_at")
    list_filter = ("role",)
    search_fields = ("user__username", "user__email")

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("user")

    def has_add_permission(self, request):
        # Profiles are created by signal; role changes are a sensitive action.
        return request.user.is_superuser

    def has_change_permission(self, request, obj=None):
        return request.user.is_superuser

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(PasswordResetOTP)
class PasswordResetOTPAdmin(admin.ModelAdmin):
    list_display = ("user", "purpose", "expires_at", "attempts_used", "consumed_at", "created_at")
    list_filter = ("purpose",)
    readonly_fields = [f.name for f in PasswordResetOTP._meta.fields]

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("user")

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser


@admin.register(AuditEvent)
class AuditEventAdmin(admin.ModelAdmin):
    list_display = ("action", "actor", "target_type", "target_id", "outcome", "created_at")
    list_filter = ("action", "outcome")
    search_fields = ("action", "target_type", "target_id")
    readonly_fields = [f.name for f in AuditEvent._meta.fields]

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("actor")

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser
