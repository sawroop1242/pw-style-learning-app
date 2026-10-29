from django.contrib import admin, messages
from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied
from django.db.models import Q
from django.utils import timezone

from accounts.models import Role
from courses import csv_import
from courses.models import (
    AccessCode,
    AttemptAnswer,
    Bookmark,
    Choice,
    CommunityPost,
    Course,
    CourseAccessGrant,
    CourseFaculty,
    CourseFolder,
    CsvImportJob,
    Lesson,
    Note,
    PdfResource,
    Progress,
    Question,
    Quiz,
    QuizAttempt,
    QuestionReport,
    RevisionItem,
    StudyTask,
    TestSeries,
)
from courses.models.access import generate_access_code

User = get_user_model()


def user_role(user):
    profile = getattr(user, "profile", None)
    return profile.role if profile else None


def is_main_admin(user):
    return user.is_authenticated and user_role(user) == Role.MAIN_ADMIN


def is_staff_role(user):
    return user.is_authenticated and user_role(user) in {Role.MAIN_ADMIN, Role.SUB_ADMIN}


class OwnershipScopedAdmin(admin.ModelAdmin):
    """Main admins see everything; sub-admins only rows belonging to courses
    or series they own. Object-level checks mirror the queryset scoping."""

    def scope_filter(self, user):
        raise NotImplementedError

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if is_main_admin(request.user):
            return qs
        return qs.filter(self.scope_filter(request.user)).distinct()

    def has_add_permission(self, request):
        # Roles are the single source of truth; FK fields are restricted to
        # owner-scoped rows below, so a sub-admin cannot attach a new row to
        # a foreign owner's course/series via a forged ID.
        return is_staff_role(request.user)

    def has_module_permission(self, request):
        return is_staff_role(request.user)

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        """Restrict every foreign-key choice to rows the user may see, so the
        ModelChoiceField validation enforces ownership on submit."""
        user = request.user
        if not is_main_admin(user):
            field_querysets = self.owner_scoped_fk_querysets(user)
            if db_field.name in field_querysets:
                kwargs["queryset"] = field_querysets[db_field.name]
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    def owner_scoped_fk_querysets(self, user):
        """Map FK field name -> the allowed queryset for this user.
        Override in subclasses; every FK offered on a form must be listed or
        the default unrestricted queryset would allow cross-owner rows."""
        return {}

    def has_view_permission(self, request, obj=None):
        if not is_staff_role(request.user):
            return False
        if obj is None or is_main_admin(request.user):
            return True
        return self.get_queryset(request).filter(pk=obj.pk).exists()

    def has_change_permission(self, request, obj=None):
        return self.has_view_permission(request, obj)

    def has_delete_permission(self, request, obj=None):
        return self.has_view_permission(request, obj)


class OwnerAssignAdmin(OwnershipScopedAdmin):
    """Also assigns the current staff user as owner on create and blocks
    sub-admins from reassigning ownership. Sub-admins never see the owner
    field; main admins may set it explicitly."""

    owner_field = "owner"

    def get_exclude(self, request, obj=None):
        exclude = super().get_exclude(request, obj)
        if not is_main_admin(request.user):
            exclude = list(exclude or []) + [self.owner_field]
        return exclude

    def save_model(self, request, obj, form, change):
        if not change:
            if not getattr(obj, self.owner_field, None):
                setattr(obj, self.owner_field, request.user)
        elif not is_main_admin(request.user):
            original = type(obj).objects.get(pk=obj.pk)
            if getattr(original, self.owner_field) != getattr(obj, self.owner_field):
                raise PermissionDenied("Ownership cannot be reassigned.")
        super().save_model(request, obj, form, change)


@admin.register(Course)
class CourseAdmin(OwnerAssignAdmin):
    list_display = ("title", "subject", "owner", "pricing_mode", "price", "is_published", "updated_at")
    list_filter = ("subject", "pricing_mode", "is_published")
    search_fields = ("title", "description", "slug")
    prepopulated_fields = {"slug": ("title",)}

    def scope_filter(self, user):
        return Q(owner=user)


@admin.register(CourseFaculty)
class CourseFacultyAdmin(OwnershipScopedAdmin):
    list_display = ("name", "course", "subject", "position")
    list_filter = ("course__subject",)
    search_fields = ("name", "subject", "course__title")

    def scope_filter(self, user):
        return Q(course__owner=user)

    def owner_scoped_fk_querysets(self, user):
        return {"course": Course.objects.filter(owner=user)}


@admin.register(CourseFolder)
class CourseFolderAdmin(OwnershipScopedAdmin):
    list_display = ("title", "course", "position", "created_at")
    list_filter = ("course__subject",)
    search_fields = ("title", "course__title")

    def scope_filter(self, user):
        return Q(course__owner=user)

    def owner_scoped_fk_querysets(self, user):
        return {"course": Course.objects.filter(owner=user)}


@admin.register(Lesson)
class LessonAdmin(OwnershipScopedAdmin):
    list_display = ("title", "course", "folder", "position", "is_published")
    list_filter = ("is_published", "course")
    search_fields = ("title", "description")

    def scope_filter(self, user):
        return Q(course__owner=user)

    def owner_scoped_fk_querysets(self, user):
        return {
            "course": Course.objects.filter(owner=user),
            "folder": CourseFolder.objects.filter(course__owner=user),
        }


@admin.register(PdfResource)
class PdfResourceAdmin(OwnershipScopedAdmin):
    list_display = ("title", "folder", "position", "is_published", "is_protected")
    list_filter = ("is_published", "is_protected")
    search_fields = ("title", "description")

    def scope_filter(self, user):
        return Q(folder__course__owner=user)

    def owner_scoped_fk_querysets(self, user):
        return {"folder": CourseFolder.objects.filter(course__owner=user)}


@admin.register(AccessCode)
class AccessCodeAdmin(OwnershipScopedAdmin):
    """Codes are created without a code field: the admin generates a secure
    value, stores only its hash, and shows the raw code once via a message."""

    fields = ("course", "max_uses", "expires_at")
    list_display = ("course", "status", "max_uses", "uses_count", "expires_at", "created_by", "created_at")
    list_filter = ("course",)
    search_fields = ("course__title",)

    def scope_filter(self, user):
        return Q(course__owner=user)

    def owner_scoped_fk_querysets(self, user):
        return {"course": Course.objects.filter(owner=user)}

    def save_model(self, request, obj, form, change):
        if not change:
            raw_code = generate_access_code()
            obj.code_hash = AccessCode.hash_code(raw_code)
            obj.created_by = request.user
            super().save_model(request, obj, form, change)
            messages.warning(
                request,
                f"Access code created. Copy it now — it will not be shown again: {raw_code}",
            )
        else:
            super().save_model(request, obj, form, change)


@admin.register(CourseAccessGrant)
class CourseAccessGrantAdmin(OwnershipScopedAdmin):
    list_display = ("user", "course", "access_code", "granted_by", "revoked_at", "created_at")
    list_filter = ("course",)
    search_fields = ("user__username", "course__title")

    def scope_filter(self, user):
        return Q(course__owner=user)

    def owner_scoped_fk_querysets(self, user):
        return {"course": Course.objects.filter(owner=user)}

    def has_add_permission(self, request):
        # Grants are created only by server-side code redemption.
        return False


@admin.register(TestSeries)
class TestSeriesAdmin(OwnerAssignAdmin):
    list_display = ("title", "subject", "owner", "is_published", "updated_at")
    list_filter = ("subject", "is_published")
    search_fields = ("title", "description")
    prepopulated_fields = {"slug": ("title",)}

    def scope_filter(self, user):
        return Q(owner=user)


@admin.register(Quiz)
class QuizAdmin(OwnershipScopedAdmin):
    list_display = ("title", "series", "course", "timing_mode", "is_published", "updated_at")
    list_filter = ("timing_mode", "is_published", "series")
    search_fields = ("title", "description")

    def scope_filter(self, user):
        return Q(series__owner=user) | Q(course__owner=user)

    def owner_scoped_fk_querysets(self, user):
        return {
            "series": TestSeries.objects.filter(owner=user),
            "course": Course.objects.filter(owner=user),
        }


class ChoiceInline(admin.TabularInline):
    model = Choice
    extra = 2
    ordering = ("position",)


@admin.register(Question)
class QuestionAdmin(OwnershipScopedAdmin):
    list_display = ("prompt_short", "quiz", "question_type", "position", "topic")
    list_filter = ("question_type", "difficulty", "quiz")
    search_fields = ("prompt", "topic")
    inlines = [ChoiceInline]

    @admin.display(description="Prompt")
    def prompt_short(self, obj):
        return obj.prompt[:60]

    def scope_filter(self, user):
        return Q(quiz__series__owner=user) | Q(quiz__course__owner=user)

    def owner_scoped_fk_querysets(self, user):
        return {
            "quiz": Quiz.objects.filter(series__owner=user)
            | Quiz.objects.filter(course__owner=user)
        }


@admin.register(QuizAttempt)
class QuizAttemptAdmin(OwnershipScopedAdmin):
    list_display = ("user", "quiz", "status", "score", "max_score", "started_at", "submitted_at")
    list_filter = ("status", "quiz")
    search_fields = ("user__username", "quiz__title")

    def scope_filter(self, user):
        return Q(quiz__series__owner=user) | Q(quiz__course__owner=user)

    def owner_scoped_fk_querysets(self, user):
        return {
            "quiz": Quiz.objects.filter(series__owner=user)
            | Quiz.objects.filter(course__owner=user)
        }

    def has_add_permission(self, request):
        return False


@admin.register(AttemptAnswer)
class AttemptAnswerAdmin(OwnershipScopedAdmin):
    list_display = ("attempt", "question", "answered", "marked_for_review")

    def scope_filter(self, user):
        return Q(attempt__quiz__series__owner=user) | Q(attempt__quiz__course__owner=user)

    def has_add_permission(self, request):
        return False


@admin.register(CsvImportJob)
class CsvImportJobAdmin(OwnershipScopedAdmin):
    """Validate and import CSV links without leaving the admin.

    Admin actions are the only way to drive an import from the browser: there
    is no staff console in the frontend, and an import must never be a file
    upload. Both actions call the same module the API uses, so the rules (and
    the error messages) are identical.
    """

    list_display = (
        "quiz", "status", "total_rows", "imported_rows", "digest", "requested_by", "created_at",
    )
    list_filter = ("status",)
    search_fields = ("quiz__title",)
    readonly_fields = (
        "status", "error_summary", "source_sha256", "total_rows", "imported_rows",
        "confirmed_at", "requested_by",
    )
    fields = ("quiz", "source_url", "status", "requested_by", "total_rows",
              "imported_rows", "source_sha256", "error_summary", "confirmed_at")
    actions = ("validate_selected", "import_selected")

    def scope_filter(self, user):
        return Q(quiz__series__owner=user) | Q(quiz__course__owner=user)

    def owner_scoped_fk_querysets(self, user):
        return {
            "quiz": Quiz.objects.filter(series__owner=user)
            | Quiz.objects.filter(course__owner=user)
        }

    def has_add_permission(self, request):
        # Pasting the URL of a hosted CSV is the whole job; the quiz choice is
        # already restricted to the provider's own tests. No CSV body passes
        # through the admin form.
        return is_staff_role(request.user)

    def save_model(self, request, obj, form, change):
        if not change and obj.requested_by_id is None:
            obj.requested_by = request.user
        super().save_model(request, obj, form, change)

    @admin.display(description="SHA-256")
    def digest(self, obj):
        return f"{obj.source_sha256[:12]}…" if obj.source_sha256 else "—"

    @admin.action(description="Validate the selected files (writes no questions)")
    def validate_selected(self, request, queryset):
        validated = failed = 0
        for job in queryset.exclude(status=CsvImportJob.Status.IMPORTED):
            try:
                report = csv_import.parse_questions_csv(csv_import.fetch_csv(job.source_url))
            except csv_import.CsvImportError as error:
                job.status = CsvImportJob.Status.FAILED
                job.total_rows = 0
                job.source_sha256 = ""
                job.error_summary = str(error)[:4000]
                job.save(update_fields=["status", "total_rows", "source_sha256", "error_summary"])
                self.message_user(request, f"“{job}” failed: {error}", messages.ERROR)
                failed += 1
                continue

            job.total_rows = report.total_rows
            job.error_summary = report.summary()
            job.source_sha256 = report.digest if not report.errors else ""
            job.status = (
                CsvImportJob.Status.VALIDATED if not report.errors else CsvImportJob.Status.FAILED
            )
            job.save(update_fields=["status", "total_rows", "source_sha256", "error_summary"])

            if report.errors:
                failed += 1
                self.message_user(
                    request,
                    f"“{job}”: {report.error_count} row error(s); nothing will be imported. "
                    "Open the job to read the error summary.",
                    messages.ERROR,
                )
            else:
                validated += 1
                self.message_user(
                    request,
                    f"“{job}”: {report.valid_rows} question(s) ready to import.",
                    messages.SUCCESS,
                )

        if validated or failed:
            self.message_user(
                request,
                f"{validated} file(s) validated, {failed} failed. No questions were written yet.",
                messages.INFO,
            )

    @admin.action(description="Import the selected files (append; all or nothing)")
    def import_selected(self, request, queryset):
        for job in queryset.filter(status=CsvImportJob.Status.VALIDATED):
            try:
                report = csv_import.parse_questions_csv(csv_import.fetch_csv(job.source_url))
            except csv_import.CsvImportError as error:
                self.message_user(request, f"“{job}” failed: {error}", messages.ERROR)
                continue

            if report.errors or report.digest != job.source_sha256:
                job.status = CsvImportJob.Status.FAILED
                job.source_sha256 = ""
                job.error_summary = "The file changed or became invalid after validation."
                job.save(update_fields=["status", "source_sha256", "error_summary"])
                self.message_user(
                    request,
                    f"“{job}” was refetched and no longer matches what was validated. "
                    "Validate it again.",
                    messages.ERROR,
                )
                continue

            try:
                imported = csv_import.import_questions(job.quiz, report)
            except csv_import.ImportBlocked as error:
                self.message_user(request, f"“{job}” refused: {error}", messages.WARNING)
                continue

            job.status = CsvImportJob.Status.IMPORTED
            job.imported_rows = imported
            job.confirmed_at = timezone.now()
            job.error_summary = ""
            job.save(update_fields=["status", "imported_rows", "confirmed_at", "error_summary"])
            self.message_user(
                request,
                f"“{job}”: imported {imported} question(s) into “{job.quiz.title}”.",
                messages.SUCCESS,
            )


@admin.register(CommunityPost)
class CommunityPostAdmin(OwnershipScopedAdmin):
    list_display = ("title", "author", "course", "is_published", "is_pinned", "created_at")
    list_filter = ("is_published", "is_pinned")
    search_fields = ("title", "body", "author__username")

    def scope_filter(self, user):
        return Q(author=user) | Q(course__owner=user)

    def owner_scoped_fk_querysets(self, user):
        return {"course": Course.objects.filter(owner=user)}

    def save_model(self, request, obj, form, change):
        if not change:
            obj.author = request.user
        super().save_model(request, obj, form, change)


@admin.register(Note)
class NoteAdmin(OwnershipScopedAdmin):
    """Notes are private; only main admins may view them for support."""

    list_display = ("user", "title", "lesson", "question", "updated_at")
    search_fields = ("title", "body", "user__username")

    def scope_filter(self, user):
        return Q(lesson__course__owner=user)

    def has_module_permission(self, request):
        return is_main_admin(request.user)

    def has_view_permission(self, request, obj=None):
        return is_main_admin(request.user)

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(Progress)
class ProgressAdmin(OwnershipScopedAdmin):
    list_display = ("user", "lesson", "completed", "completed_at", "updated_at")
    list_filter = ("completed",)
    search_fields = ("user__username", "lesson__title")

    def scope_filter(self, user):
        return Q(lesson__course__owner=user)


class PrivateDataAdminBase(admin.ModelAdmin):
    """Private user data: read-only, main-admin support access only."""

    def has_module_permission(self, request):
        return is_main_admin(request.user)

    def has_view_permission(self, request, obj=None):
        return is_main_admin(request.user)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(Bookmark)
class BookmarkAdmin(PrivateDataAdminBase):
    list_display = ("user", "content_type", "object_id", "tag", "created_at")
    search_fields = ("user__username",)


@admin.register(RevisionItem)
class RevisionItemAdmin(PrivateDataAdminBase):
    list_display = ("user", "content_type", "object_id", "status", "updated_at")
    search_fields = ("user__username",)


@admin.register(StudyTask)
class StudyTaskAdmin(PrivateDataAdminBase):
    list_display = ("user", "title", "due_at", "priority", "is_completed", "created_at")
    search_fields = ("user__username", "title")


@admin.register(QuestionReport)
class QuestionReportAdmin(OwnershipScopedAdmin):
    """Triage queue for reported questions.

    Deliberately read-mostly: a provider changes ``status`` (open → reviewing →
    resolved/dismissed). The learner's reason and note are inputs, not fields a
    provider should be able to rewrite.
    """

    list_display = ("question", "reason", "status", "attempt", "created_at")
    list_filter = ("status", "reason")
    search_fields = ("question__prompt", "detail")
    readonly_fields = ("attempt", "question", "user", "reason", "detail", "created_at")
    date_hierarchy = "created_at"

    def scope_filter(self, user):
        return Q(attempt__quiz__owner=user)

    def get_readonly_fields(self, request, obj=None):
        base = list(self.readonly_fields)
        return base
