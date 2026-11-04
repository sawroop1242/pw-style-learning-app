import json

from django.contrib import admin, messages
from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied
from django.db.models import Count, Max, Q
from django import forms
from django.forms.models import BaseInlineFormSet
from django.http import Http404, JsonResponse
from django.template.response import TemplateResponse
from django.urls import path, reverse
from django.utils import timezone
from django.utils.html import format_html

from config.admin_ui import pill

from accounts.models import Role
from accounts.roles import is_main_admin, is_staff_role, user_role
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
from courses.outline import (
    OutlineError,
    apply_order,
    build_outline,
    describe_outline,
    revision_of,
)

User = get_user_model()



class CompactTextareaMixin:
    """Give every long-text field four visible lines instead of ten.

    A course blurb, a folder description or a statement is a paragraph, and
    Django's ten-row textarea makes each of those forms twice as tall as the
    fields it sits between. The handle is still there for anything longer.
    """

    def formfield_for_dbfield(self, db_field, request, **kwargs):
        field = super().formfield_for_dbfield(db_field, request, **kwargs)
        if field is not None and isinstance(field.widget, forms.Textarea):
            # `forms.Textarea` seeds its attrs with rows=10, so setdefault()
            # would never fire; replace that default and leave any explicit
            # size an author set alone.
            if str(field.widget.attrs.get("rows", "10")) == "10":
                field.widget.attrs["rows"] = 4
        return field


class OwnershipScopedAdmin(CompactTextareaMixin, admin.ModelAdmin):
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

    @admin.display(description="Updated", ordering="updated_at")
    def last_edited(self, obj):
        """A compact timestamp for list columns.

        Django prints ``Nov. 1, 2026, 8:41 p.m.``, which is 26 characters of
        noise per row and the widest thing in a list. The day is what a person
        scans for; the clock only matters for today's rows.
        """
        stamp = timezone.localtime(obj.updated_at)
        now = timezone.localtime()
        if stamp.date() == now.date():
            return f"Today {stamp:%H:%M}"
        if stamp.year == now.year:
            return f"{stamp:%d %b} {stamp:%H:%M}"
        return f"{stamp:%d %b %Y}"

    def changelist_view(self, request, extra_context=None):
        """Name the list after what it holds.

        Django titles every list "Select <model> to change", which reads like
        an instruction and repeats on all 25 of them. The heading is the thing
        the page is about.
        """
        extra_context = dict(extra_context or {})
        extra_context.setdefault("title", str(self.model._meta.verbose_name_plural).capitalize())
        return super().changelist_view(request, extra_context)


    @admin.display(description="Status", ordering="is_published")
    def publish_status(self, obj):
        # Deliberately not called `status`: AccessCode has a `status` of its
        # own, and a ModelAdmin attribute of the same name would hide it.
        """Published rows are green, drafts blue — the console's one palette."""
        return pill("Published" if obj.is_published else "Draft",
                    "ok" if obj.is_published else "info")


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

    def get_changeform_initial_data(self, request):
        """Pre-select the signed-in person as owner of anything new.

        Without it the owner picker opens on "---------" and the row is saved
        with no owner at all, which then hides it from every sub-admin.
        """
        initial = super().get_changeform_initial_data(request)
        if is_main_admin(request.user):
            initial.setdefault(self.owner_field, request.user.pk)
        return initial

    def save_model(self, request, obj, form, change):
        if not change:
            if not getattr(obj, self.owner_field, None):
                setattr(obj, self.owner_field, request.user)
        elif not is_main_admin(request.user):
            original = type(obj).objects.get(pk=obj.pk)
            if getattr(original, self.owner_field) != getattr(obj, self.owner_field):
                raise PermissionDenied("Ownership cannot be reassigned.")
        super().save_model(request, obj, form, change)


class StaffInlineMixin:
    """Inlines are gated on the staff *role*, not on model permissions.

    Django falls back to `<app>.add_<model>` when an inline does not define the
    permission methods. A sub-admin holds none of those permissions, so every
    inline silently disappeared from their forms — the answers section on a
    question, and now the sections and lessons on a batch. The role is the thing
    that decides access everywhere else in this admin; it decides it here too.
    """

    def has_add_permission(self, request, obj):
        return is_staff_role(request.user)

    def has_view_permission(self, request, obj):
        return is_staff_role(request.user)

    def has_change_permission(self, request, obj):
        return is_staff_role(request.user)

    def has_delete_permission(self, request, obj):
        return is_staff_role(request.user)


class PublishableAdmin(OwnershipScopedAdmin):
    """Publish or unpublish many rows at once.

    Publishing was the most repeated job in the console — a new batch has a
    dozen lessons, and each one had to be opened, ticked and saved. The action
    runs on the queryset the changelist already filtered to, so a sub-admin can
    only flip rows the list showed them.
    """

    publish_label = "rows"
    # `@admin.action` only marks a method; it is not registered until it is
    # named here. Without this line the bulk publish never appeared on a list
    # page — `get_actions` below then raised KeyError and the page 500ed.
    actions = ("publish_selected", "unpublish_selected")

    @admin.action(description="Publish the selected rows")
    def publish_selected(self, request, queryset):
        updated = queryset.update(is_published=True, updated_at=timezone.now())
        self.message_user(request, f"{updated} {self.publish_label} published.", messages.SUCCESS)

    @admin.action(description="Unpublish the selected rows")
    def unpublish_selected(self, request, queryset):
        updated = queryset.update(is_published=False, updated_at=timezone.now())
        self.message_user(request, f"{updated} {self.publish_label} unpublished.", messages.SUCCESS)

    def get_actions(self, request):
        actions = super().get_actions(request)
        # The wording names the model; the tuple carries the description, so
        # nothing shared between requests is mutated here.
        for name, verb in (("publish_selected", "Publish"), ("unpublish_selected", "Unpublish")):
            if name not in actions:
                # A subclass may offer only one of the two.
                continue
            action, action_name, _ = actions[name]
            actions[name] = (action, action_name, f"{verb} the selected {self.publish_label}")
        return actions


class FolderLessonFormSet(BaseInlineFormSet):
    """Lessons written inside a section inherit the section's batch.

    `Lesson.course` is a required foreign key that is not on this inline — the
    section already knows it. Setting it while the form is *built* (rather than
    only when it is saved) is what lets the model's own clean() check compare
    the two and pass.
    """

    def _construct_form(self, i, **kwargs):
        form = super()._construct_form(i, **kwargs)
        if self.instance.pk:
            form.instance.course_id = self.instance.course_id
        return form


class FolderLessonInlineForm(forms.ModelForm):
    """A plain URL box.

    The admin's URL widget prints "Currently: <link>" above the input and wraps
    both in one paragraph, which inside a table row doubled the height and cut
    the URL off at the point you need to check. In a row, the value in the box
    is the whole story.
    """

    class Meta:
        model = Lesson
        fields = ("title", "video_url", "duration_minutes", "position", "is_published")
        widgets = {
            "title": forms.TextInput(attrs={"placeholder": "Class title"}),
            "video_url": forms.URLInput(attrs={"placeholder": "https://embed…"}),
        }


class FolderLessonInline(StaffInlineMixin, admin.TabularInline):
    model = Lesson
    fk_name = "folder"
    form = FolderLessonInlineForm
    formset = FolderLessonFormSet
    fields = ("title", "video_url", "duration_minutes", "position", "is_published")
    extra = 1
    ordering = ("position", "id")
    verbose_name = "class"
    verbose_name_plural = "Classes in this section"


class FolderPdfInlineForm(forms.ModelForm):
    class Meta:
        model = PdfResource
        fields = ("title", "file_url", "position", "is_published", "is_protected")
        widgets = {
            "title": forms.TextInput(attrs={"placeholder": "Note or PDF title"}),
            "file_url": forms.URLInput(attrs={"placeholder": "https://…pdf"}),
        }


class FolderPdfInline(StaffInlineMixin, admin.TabularInline):
    model = PdfResource
    fk_name = "folder"
    form = FolderPdfInlineForm
    fields = ("title", "file_url", "position", "is_published", "is_protected")
    extra = 1
    ordering = ("position", "id")
    verbose_name = "PDF"
    verbose_name_plural = "Notes and PDFs"


class CourseFolderInline(StaffInlineMixin, admin.TabularInline):
    """Sections on the batch page.

    A batch used to be built in two places: the batch here, then "Course
    folders" somewhere else, with the batch picked again from a dropdown. The
    sections are part of the batch, so they are edited on it.
    """

    model = CourseFolder
    fk_name = "course"
    fields = ("title", "position")
    extra = 1
    ordering = ("position", "id")
    verbose_name = "section"
    verbose_name_plural = "Sections (folders of classes)"
    show_change_link = True


class FolderChoiceField(forms.ModelChoiceField):
    """Every section in the catalogue, labelled with the batch it is in.

    The label is the whole point: a dropdown of bare section names ("Week 1")
    is unusable once a second batch has a "Week 1" too, and the list used to be
    narrowed to one batch at a time. Each option now reads
    "Batch — Section", so the whole catalogue can be shown at once without
    anybody guessing which section belongs where.
    """

    def label_from_instance(self, folder):
        return f"{folder.course.title} — {folder.title}"


class LessonAdminForm(forms.ModelForm):
    """Lesson form whose section list is the whole catalogue.

    Nothing is filtered by the selected batch and nothing is filtered by
    ownership: every section is offered, labelled with its batch. Picking a
    section therefore decides the batch, which is what the model requires
    anyway (`Lesson.clean` refuses a section from another course).
    """

    folder = FolderChoiceField(
        # Replaced with the real queryset in __init__; the class body only
        # needs something to satisfy ModelChoiceField.
        queryset=CourseFolder.objects.none(),
        required=False,
        label="Batch — Section",
        empty_label="— no section —",
        help_text=(
            "Every section of every batch is listed, as “Batch — Section”. "
            "Choosing one sets the batch above to match it."
        ),
    )

    class Meta:
        model = Lesson
        fields = "__all__"

    def __init__(self, *args, **kwargs):
        self.request = kwargs.pop("request", None)
        super().__init__(*args, **kwargs)
        self.fields["folder"].queryset = CourseFolder.objects.select_related(
            "course"
        ).order_by("course__title", "position", "id")
        # The batch is optional in the form because a chosen section sets it.
        # `clean` below puts it back before the instance is built.
        self.fields["course"].required = False

    def clean(self):
        cleaned = super().clean()
        folder = cleaned.get("folder")
        course = cleaned.get("course")

        if folder is not None:
            # The section decides the batch. Without this a form could be saved
            # with the two disagreeing and fail `Lesson.clean` on the next edit.
            cleaned["course"] = folder.course
            course = folder.course

            user = getattr(self.request, "user", None)
            if user is not None and not is_main_admin(user) and folder.course.owner_id != user.id:
                raise forms.ValidationError(
                    {
                        "folder": (
                            f"“{folder.title}” is a section of “{folder.course.title}”, "
                            "which belongs to another teacher. Add the class to a "
                            "section of one of your own batches."
                        )
                    }
                )
        elif course is None:
            raise forms.ValidationError(
                {"course": "Pick a batch, or a section — the section sets the batch."}
            )
        return cleaned


def _outline_summary(sections) -> str:
    """Say "3 sections and 7 classes", with the singular where it belongs."""
    lessons = sum(len(section.lessons) for section in sections)
    return (
        f"{len(sections)} section{'s' if len(sections) != 1 else ''} and "
        f"{lessons} class{'es' if lessons != 1 else ''}"
    )


class CourseOutlineMixin:
    """The batch's outline: sections and classes, arranged by moving them.

    A tabular inline of `position` integers is how the console used to express
    order — every move meant retyping the neighbours. This screen is the order
    itself: drag a section, drag a class inside or across sections, then save
    once. Everything it posts goes through `courses.outline`, which validates
    the whole order or refuses it.
    """

    outline_template = "admin/courses/course_outline.html"

    def get_urls(self):
        # Registered before Django's own patterns so `<pk>/outline/` is not
        # mistaken for a change-form sub-path.
        return [
            path(
                "<path:object_id>/outline/",
                self.admin_site.admin_view(self.outline_view),
                name="courses_course_outline",
            ),
        ] + super().get_urls()

    def _outline_course(self, request, object_id):
        """The batch this account may rearrange, or the reason it cannot.

        The lookup goes through the admin's own queryset, so a sub-admin asking
        for a colleague's batch gets the same 404 they get from the change form
        rather than a screen that reveals it exists.
        """
        if not str(object_id).isdigit():
            raise Http404("That batch does not exist.")
        course = self.get_queryset(request).filter(pk=int(object_id)).first()
        if course is None:
            raise Http404("That batch does not exist.")
        if not self.has_change_permission(request, course):
            raise PermissionDenied("You may not change this batch.")
        return course

    def outline_view(self, request, object_id):
        course = self._outline_course(request, object_id)
        if request.method == "POST":
            return self._save_outline(request, course)
        return self._render_outline(request, course)

    def _render_outline(self, request, course):
        sections = build_outline(course)
        context = {
            **self.admin_site.each_context(request),
            "title": "Outline",
            "opts": self.model._meta,
            "app_label": self.model._meta.app_label,
            "course": course,
            "sections": sections,
            "revision": revision_of(sections),
            "summary": _outline_summary(sections),
            "change_url": reverse("admin:courses_course_change", args=[course.pk]),
        }
        return TemplateResponse(request, self.outline_template, context)

    def _save_outline(self, request, course):
        try:
            payload = json.loads(request.body.decode("utf-8") or "{}")
        except (UnicodeDecodeError, ValueError):
            return JsonResponse(
                {
                    "error": "invalid",
                    "message": "That request was not readable. Reload the page and try again.",
                },
                status=400,
            )

        before = revision_of(build_outline(course))
        try:
            sections = apply_order(course, payload)
        except OutlineError as exc:
            return JsonResponse({"error": exc.code, "message": exc.message}, status=exc.status)

        after = revision_of(sections)
        if after != before:
            # The batch's History should say the outline moved, without a row
            # per class — this is one action by one person.
            self.log_change(request, course, f"Reordered the outline ({_outline_summary(sections)})")
            message = f"Saved — {_outline_summary(sections)}, in this order."
        else:
            message = "Nothing moved — the outline is already in this order."
        return JsonResponse({"ok": True, "message": message, **describe_outline(sections)})


@admin.register(Course)
class CourseAdmin(CourseOutlineMixin, PublishableAdmin, OwnerAssignAdmin):
    publish_label = "batches"
    # Autocomplete views paginate the model admin's queryset, which needs a
    # stable order (Django warns "Pagination may yield inconsistent results"
    # otherwise).
    ordering = ("title",)
    list_display = (
        "title", "subject", "pricing_mode", "price", "lesson_total", "folder_total",
        "publish_status", "owner", "updated_at",
    )
    list_filter = ("subject", "pricing_mode", "is_published")
    search_fields = ("title", "description", "slug")
    prepopulated_fields = {"slug": ("title",)}
    inlines = [CourseFolderInline]
    save_on_top = True
    # A fieldset may only name a non-model field when it is declared read-only.
    readonly_fields = ("shortcuts", "image_preview", "telegram_preview")

    def get_fieldsets(self, request, obj=None):
        """`owner` is hidden from sub-admins by OwnerAssignAdmin, so it is only
        named in the fieldset for someone who may actually change it."""
        batch_fields = ("title", "slug", "subject")
        if is_main_admin(request.user):
            batch_fields = batch_fields + ("owner",)
        fieldsets = (
            ("The batch", {
                "fields": batch_fields,
                "description": "What the card in the catalogue says.",
            }),
            ("Artwork", {
                "fields": ("image_url", "image_preview"),
                "description": (
                    "Paste any https image link — a CDN, Drive, Imgur. It becomes "
                    "the cover on the catalogue card; leave it empty and the card "
                    "keeps its subject colour."
                ),
            }),
            ("Description", {"fields": ("description",)}),
            ("Pricing", {
                "fields": ("pricing_mode", "price", "currency"),
                "description": "A free batch must cost 0; a paid batch needs a price. "
                               "Nobody pays here — a paid batch unlocks with an access code.",
            }),
            ("Access codes and Telegram", {
                "fields": ("telegram_handle", "telegram_url", "telegram_preview"),
                "description": (
                    "Fill in the Telegram username to answer for this batch. "
                    "A learner who opens a paid batch sees “Get code”, which "
                    "opens a chat with that account with the batch name and "
                    "number already typed, so you know what they are asking "
                    "for. The public channel link is optional."
                ),
            }),
            ("Visibility", {"fields": ("is_published", "position")}),
        )
        if obj is not None:
            # Appended as a one-element tuple of (name, options).
            fieldsets += ((
                "What is in this batch",
                {
                    "fields": ("shortcuts",),
                    "description": (
                        "Add a section, a class, a test or a teacher, or arrange "
                        "the order the sections and classes appear in."
                    ),
                },
            ),)
        return fieldsets

    @admin.display(description="What the learner will send")
    def telegram_preview(self, obj):
        """Show the exact DM the button opens, or say the button is hidden.

        Seeing the draft here is the only way to notice a wrong handle before
        a learner does: the message is what arrives in the provider's Telegram.
        """
        if obj is None:
            return format_html(
                '<span class="ss-muted">Save the batch first — the draft names '
                "the batch number.</span>"
            )
        url = obj.telegram_dm_url
        if not url:
            return format_html(
                '<span class="ss-muted">No usable username yet, so the paid batch '
                "shows no “Get code” button and keeps the code box only.</span>"
            )
        return format_html(
            '<a href="{}" target="_blank" rel="noopener">{}</a>'
            '<br><span class="ss-muted">Opens a chat with @{}.</span>',
            url,
            obj.telegram_dm_message,
            obj.telegram_username,
        )

    @admin.display(description="Cover preview")
    def image_preview(self, obj):
        """Show the pasted image, or say plainly that there is none."""
        url = getattr(obj, "image_url", "") or ""
        if not url:
            return format_html(
                '<span class="ss-muted">No cover yet — the card will use its subject colour.</span>'
            )
        return format_html(
            '<img src="{}" alt="" loading="lazy" '
            'style="max-width:320px;max-height:180px;border-radius:12px;'
            'object-fit:cover;background:#0b0f1a;">',
            url,
        )

    @admin.display(description="Shortcuts")
    def shortcuts(self, obj):
        """Straight to the add form, with this batch already chosen.

        Picking the batch from a dropdown for every new class is the step people
        get wrong (and the reason a class occasionally lands in the wrong
        batch), so the next action carries the id with it.
        """
        if obj is None:
            return ""
        return format_html(
            '<span class="ss-shortcuts">'
            '<a class="ss-shortcut ss-shortcut--primary" href="{}">Arrange classes and sections</a>'
            '<a class="ss-shortcut" href="{}">+ Add a class</a>'
            '<a class="ss-shortcut" href="{}">+ Add a section</a>'
            '<a class="ss-shortcut" href="{}">+ Add a test</a>'
            '<a class="ss-shortcut" href="{}">+ Add faculty</a>'
            "</span>",
            reverse("admin:courses_course_outline", args=[obj.pk]),
            reverse("admin:courses_lesson_add") + f"?course={obj.pk}",
            reverse("admin:courses_coursefolder_add") + f"?course={obj.pk}",
            reverse("admin:courses_quiz_add") + f"?course={obj.pk}",
            reverse("admin:courses_coursefaculty_add") + f"?course={obj.pk}",
        )

    def scope_filter(self, user):
        return Q(owner=user)

    def get_queryset(self, request):
        # Two counts in the list, so annotate rather than query per row.
        return super().get_queryset(request).annotate(
            _lessons=Count("lessons", distinct=True),
            _folders=Count("folders", distinct=True),
        )

    @admin.display(description="Lessons", ordering="_lessons")
    def lesson_total(self, obj):
        return obj._lessons

    @admin.display(description="Sections", ordering="_folders")
    def folder_total(self, obj):
        return obj._folders


@admin.register(CourseFaculty)
class CourseFacultyAdmin(OwnershipScopedAdmin):
    list_display = ("name", "course", "subject", "position")
    list_filter = ("course__subject",)
    search_fields = ("name", "subject", "course__title")
    autocomplete_fields = ("course",)

    def scope_filter(self, user):
        return Q(course__owner=user)

    def owner_scoped_fk_querysets(self, user):
        return {"course": Course.objects.filter(owner=user)}


@admin.register(CourseFolder)
class CourseFolderAdmin(OwnershipScopedAdmin):
    ordering = ("course__title", "position", "title")
    list_display = ("title", "course", "lesson_total", "position", "created_at")
    list_filter = ("course__subject", "course")
    search_fields = ("title", "course__title")
    list_select_related = ("course",)
    autocomplete_fields = ("course",)
    inlines = [FolderLessonInline, FolderPdfInline]
    save_on_top = True
    readonly_fields = ("shortcuts",)
    def get_fieldsets(self, request, obj=None):
        base = (
            ("Which batch", {
                "fields": ("course",),
                "description": "Type a few letters — the list is searchable.",
            }),
            ("The section", {"fields": ("title", "description", "position")}),
        )
        if obj is None:
            return base
        return base + (("Add to this section", {"fields": ("shortcuts",)}),)

    @admin.display(description="Shortcuts")
    def shortcuts(self, obj):
        if obj is None:
            return ""
        return format_html(
            '<span class="ss-shortcuts">'
            '<a class="ss-shortcut" href="{}">+ Add a class</a>'
            '<a class="ss-shortcut" href="{}">+ Add a PDF</a>'
            "</span>",
            reverse("admin:courses_lesson_add") + f"?folder={obj.pk}",
            reverse("admin:courses_pdfresource_add") + f"?folder={obj.pk}",
        )

    def scope_filter(self, user):
        return Q(course__owner=user)

    def owner_scoped_fk_querysets(self, user):
        return {"course": Course.objects.filter(owner=user)}

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(_lessons=Count("lessons"))

    @admin.display(description="Classes", ordering="_lessons")
    def lesson_total(self, obj):
        return obj._lessons


@admin.register(Lesson)
class LessonAdmin(PublishableAdmin):
    """Classes.

    Two jobs dominated this screen: publishing a new batch's lessons (bulk
    action below) and turning one written class into the next one (Duplicate).
    Both are here so neither needs a row opened one at a time.
    """

    publish_label = "lessons"
    list_display = (
        "title", "course", "folder", "position", "duration_minutes",
        "recording", "publish_status",
    )
    list_filter = ("is_published", "course")
    search_fields = ("title", "description", "course__title")
    list_select_related = ("course", "folder")
    list_editable = ("position",)
    form = LessonAdminForm
    # `course` stays an autocomplete (there may be a hundred batches); the
    # section is a plain select listing every section in the catalogue.
    autocomplete_fields = ("course",)
    save_on_top = True
    actions = ("publish_selected", "unpublish_selected", "duplicate_selected")

    def get_form(self, request, obj=None, change=False, **kwargs):
        """Hand the request to the form.

        `ModelAdmin` has no hook for extra constructor arguments — a
        `get_form_kwargs` method looks like one but is never called — so the
        form class is wrapped here with the request bound. Without it the form
        could not tell a main admin from a sub-admin, and the section list was
        never scoped the way the code appeared to say.
        """
        form_class = super().get_form(request, obj, change, **kwargs)

        class RequestBoundForm(form_class):
            def __init__(self, *args, **form_kwargs):
                form_kwargs.setdefault("request", request)
                super().__init__(*args, **form_kwargs)

        RequestBoundForm.__name__ = form_class.__name__
        RequestBoundForm.__qualname__ = form_class.__qualname__
        return RequestBoundForm

    fieldsets = (
        ("Which batch", {
            "fields": ("course", "folder"),
            "description": (
                "The section list shows every section of every batch, labelled "
                "“Batch — Section”. Pick the section and the batch follows it; "
                "pick neither and the class sits at the top of its batch."
            ),
        }),
        ("The class", {"fields": ("title", "description")}),
        ("Recording", {
            "fields": ("video_url", "recording_preview", "duration_minutes"),
            "description": "A direct .mp4 plays in the page's own player; a hosted "
                           "embed page (…/embed/…) is framed instead. Both work.",
        }),
        ("Order and visibility", {"fields": ("position", "is_published")}),
    )
    readonly_fields = ("recording_preview",)

    def scope_filter(self, user):
        return Q(course__owner=user)

    def owner_scoped_fk_querysets(self, user):
        return {
            "course": Course.objects.filter(owner=user),
            "folder": CourseFolder.objects.filter(course__owner=user),
        }

    def get_changeform_initial_data(self, request):
        """`?course=…` / `?folder=…` prefill the form.

        The batch and section pages link here, so adding the next class means
        typing a title instead of re-picking the batch from a dropdown and
        hoping it is the right one. Values are checked against the rows this
        user owns; a forged id in the URL is ignored, not obeyed.
        """
        initial = super().get_changeform_initial_data(request)
        user = request.user
        course_qs = Course.objects.all() if is_main_admin(user) else Course.objects.filter(owner=user)
        folder_qs = (
            CourseFolder.objects.all()
            if is_main_admin(user)
            else CourseFolder.objects.filter(course__owner=user)
        )
        folder_id = request.GET.get("folder")
        if folder_id and folder_qs.filter(pk=folder_id).exists():
            folder = folder_qs.get(pk=folder_id)
            initial["folder"] = folder.pk
            initial["course"] = folder.course_id
            initial.setdefault("position", folder.lessons.count() + 1)
        course_id = request.GET.get("course")
        if course_id and course_qs.filter(pk=course_id).exists():
            initial["course"] = int(course_id)
        return initial

    @admin.display(description="Recording")
    def recording(self, obj):
        return "Yes" if obj.video_url else "—"

    @admin.display(description="Preview")
    def recording_preview(self, obj):
        """Open the URL before publishing it.

        A pasted URL is not a checked URL: the host may refuse framing, or the
        file may be gone. This saves a round trip through the learner's player.
        """
        if not obj or not obj.video_url:
            return "Save the class with a video URL to preview it."
        return format_html(
            '<a href="{}" target="_blank" rel="noopener">Open the recording ↗</a>',
            obj.video_url,
        )

    @admin.action(description="Duplicate the selected lessons")
    def duplicate_selected(self, request, queryset):
        made = 0
        for lesson in queryset:
            lesson.pk = None
            lesson.title = f"{lesson.title} (copy)"[:180]
            lesson.is_published = False
            lesson.position = lesson.position + 1
            lesson.save()
            made += 1
        self.message_user(
            request,
            f"{made} lesson(s) duplicated as drafts. They keep the recording and the section.",
            messages.SUCCESS,
        )


@admin.register(PdfResource)
class PdfResourceAdmin(OwnershipScopedAdmin):
    list_display = ("title", "folder", "position", "publish_status", "is_protected")
    list_filter = ("is_published", "is_protected")
    search_fields = ("title", "description")
    autocomplete_fields = ("folder",)
    fieldsets = (
        ("The document", {
            "fields": ("title", "description", "file_url", "embed_url"),
            "description": (
                "file_url is the file or the share link the provider gave you — "
                "the in-app reader frames it, so pdfhost's /v/… link opens in "
                "pdfhost's own reader. embed_url is optional: paste the provider's "
                "embed link only if it has one, and the reader frames exactly that. "
                "A Google Drive /view link is turned into its /preview."
            ),
        }),
        ("Placement", {
            "fields": ("folder", "position", "is_published", "is_protected"),
            "description": (
                "A protected PDF returns its URL only to learners enrolled in the "
                "batch. That is what makes the reader private rather than public."
            ),
        }),
    )

    def get_changeform_initial_data(self, request):
        initial = super().get_changeform_initial_data(request)
        folder_id = request.GET.get("folder")
        if folder_id:
            allowed = (
                CourseFolder.objects.all()
                if is_main_admin(request.user)
                else CourseFolder.objects.filter(course__owner=request.user)
            )
            if allowed.filter(pk=folder_id).exists():
                initial["folder"] = int(folder_id)
        return initial

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
    autocomplete_fields = ("course",)
    search_fields = ("course__title",)

    def get_changeform_initial_data(self, request):
        initial = super().get_changeform_initial_data(request)
        course_id = request.GET.get("course")
        if course_id:
            allowed = (
                Course.objects.all()
                if is_main_admin(request.user)
                else Course.objects.filter(owner=request.user)
            )
            if allowed.filter(pk=course_id).exists():
                initial["course"] = int(course_id)
        return initial

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
    list_display = ("title", "subject", "owner", "publish_status", "last_edited")
    list_filter = ("subject", "is_published")
    search_fields = ("title", "description")
    prepopulated_fields = {"slug": ("title",)}

    def scope_filter(self, user):
        return Q(owner=user)


@admin.register(Quiz)
class QuizAdmin(PublishableAdmin):
    publish_label = "tests"
    list_display = (
        "title", "series", "course", "timing_mode", "duration",
        "question_total", "publish_status", "last_edited",
    )
    list_filter = ("timing_mode", "is_published", "series")
    search_fields = ("title", "description")
    list_select_related = ("series", "course")
    list_editable = ()
    autocomplete_fields = ("series", "course")
    save_on_top = True
    fieldsets = (
        ("Which test", {
            "fields": ("title", "series", "course", "description", "instructions"),
            "description": "A paper belongs to a series or to a batch — usually one of the two.",
        }),
        ("Timing", {
            "fields": ("timing_mode", "duration_minutes", "attempt_limit"),
            "description": "The deadline is fixed when a learner starts, so changing "
                           "the duration never moves a paper that is already running.",
        }),
        ("Marking", {
            "fields": ("marks_per_question", "negative_marks_per_wrong", "pass_threshold_percent"),
        }),
        ("When results appear", {"fields": ("result_release_policy",)}),
        ("Shuffling", {
            "fields": ("shuffle_questions", "shuffle_options"),
            "classes": ("collapse",),
            "description": "Optional. Leave collapsed unless the paper needs it.",
        }),
        ("Window and visibility", {"fields": ("opens_at", "closes_at", "is_published")}),
    )

    def scope_filter(self, user):
        return Q(series__owner=user) | Q(course__owner=user)

    def owner_scoped_fk_querysets(self, user):
        return {
            "series": TestSeries.objects.filter(owner=user),
            "course": Course.objects.filter(owner=user),
        }

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(_questions=Count("questions"))

    @admin.display(description="Minutes", ordering="duration_minutes")
    def duration(self, obj):
        """The header is the unit, so the cell is just the number.

        ``Duration minutes`` was the widest heading in the list and pushed the
        last column off the right edge at 1440px.
        """
        return obj.duration_minutes

    @admin.display(description="Questions", ordering="_questions")
    def question_total(self, obj):
        return obj._questions


class ChoiceForm(forms.ModelForm):
    """The four answer rows, labelled the way a question paper reads."""

    class Meta:
        model = Choice
        fields = ("text", "is_correct")
        labels = {"text": "Answer", "is_correct": "Correct"}


class ChoiceInlineFormSet(BaseInlineFormSet):
    """Number the answers for the admin.

    `position` used to be a visible integer column, so writing one question
    meant typing 0, 1, 2, 3 by hand — and a mistake there reordered the paper.
    The order the rows are shown in is the order they are served in, so the
    value is assigned on save and never typed.
    """

    def clean(self):
        super().clean()
        if any(self.errors):
            return
        position = 0
        for form in self.forms:
            data = getattr(form, "cleaned_data", None)
            if not data or data.get("DELETE"):
                continue
            if not (data.get("text") or "").strip():
                continue
            form.instance.position = position
            position += 1


class ChoiceInline(admin.TabularInline):
    """The answers to one question.

    The permission methods are not decoration. Django falls back to the model
    permissions (`courses.add_choice`) when an inline does not define them, and
    a sub-admin has none — so the answers section vanished from the question
    form and a question saved with no answers at all. The gate is the role, the
    same one the parent admin uses.
    """

    model = Choice
    form = ChoiceForm
    formset = ChoiceInlineFormSet
    fields = ("text", "is_correct")
    extra = 4
    max_num = 10
    ordering = ("position",)
    verbose_name = "answer"
    verbose_name_plural = "Answers"

    def has_add_permission(self, request, obj):
        return is_staff_role(request.user)

    def has_view_permission(self, request, obj):
        return is_staff_role(request.user)

    def has_change_permission(self, request, obj):
        return is_staff_role(request.user)

    def has_delete_permission(self, request, obj):
        return is_staff_role(request.user)


@admin.register(Question)
class QuestionAdmin(OwnershipScopedAdmin):
    list_display = ("prompt_short", "quiz", "question_type", "difficulty", "position", "topic")
    list_filter = ("question_type", "difficulty", "quiz")
    search_fields = ("prompt", "topic", "quiz__title")
    inlines = [ChoiceInline]
    list_select_related = ("quiz",)
    autocomplete_fields = ("quiz",)
    save_on_top = True
    actions = ("duplicate_selected",)
    fieldsets = (
        ("The question", {
            "fields": ("quiz", "prompt", "explanation"),
            "description": "The explanation is what a learner reads in review. "
                           "Leave it blank rather than writing \"see the notes\".",
        }),
        ("Marking", {
            "fields": ("question_type", "marks", "negative_marks"),
            "description": "Blank marks fall back to the test's own values.",
        }),
        ("Classification", {
            "fields": ("difficulty", "topic"),
            "description": "The topic is what the result's strengths panel groups by.",
        }),
        ("Placement", {"fields": ("position",)}),
    )

    def get_changeform_initial_data(self, request):
        initial = super().get_changeform_initial_data(request)
        quiz_id = request.GET.get("quiz")
        if quiz_id:
            allowed = self.owner_scoped_fk_querysets(request.user).get("quiz", Quiz.objects.none())
            if is_main_admin(request.user):
                allowed = Quiz.objects.all()
            if allowed.filter(pk=quiz_id).exists():
                initial["quiz"] = int(quiz_id)
                initial.setdefault(
                    "position", (Question.objects.filter(quiz_id=quiz_id).aggregate(top=Max("position"))["top"] or 0) + 1
                )
        return initial

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

    @admin.action(description="Duplicate the selected questions")
    def duplicate_selected(self, request, queryset):
        """Copy a question *and its answers*, which is how a paper is built."""
        made = 0
        for question in queryset.prefetch_related("choices"):
            choices = list(question.choices.all())
            question.pk = None
            question.position = (
                (queryset.model.objects.filter(quiz=question.quiz).aggregate(
                    top=Max("position")
                )["top"] or 0) + 1
            )
            question.save()
            for choice in choices:
                choice.pk = None
                choice.question = question
                choice.save()
            made += 1
        self.message_user(
            request,
            f"{made} question(s) duplicated at the end of their paper, answers and all.",
            messages.SUCCESS,
        )


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

    list_display = ("user", "title", "lesson", "question", "last_edited")
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


class PrivateDataAdminBase(CompactTextareaMixin, admin.ModelAdmin):
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
    list_select_related = ("question", "attempt")
    actions = ("mark_reviewing", "mark_resolved", "mark_dismissed")

    def _set_status(self, request, queryset, status, label):
        updated = queryset.update(status=status)
        self.message_user(request, f"{updated} report(s) {label}.", messages.SUCCESS)

    @admin.action(description="Mark the selected reports as being reviewed")
    def mark_reviewing(self, request, queryset):
        self._set_status(request, queryset, QuestionReport.Status.REVIEWING, "now under review")

    @admin.action(description="Resolve the selected reports (the question was fixed)")
    def mark_resolved(self, request, queryset):
        self._set_status(request, queryset, QuestionReport.Status.RESOLVED, "resolved")

    @admin.action(description="Dismiss the selected reports (nothing to fix)")
    def mark_dismissed(self, request, queryset):
        self._set_status(request, queryset, QuestionReport.Status.DISMISSED, "dismissed")

    def scope_filter(self, user):
        # A Quiz has no owner of its own: it belongs to a series or to a batch,
        # and the owner sits on whichever of those it hangs from.
        return Q(attempt__quiz__series__owner=user) | Q(attempt__quiz__course__owner=user)

    def get_readonly_fields(self, request, obj=None):
        base = list(self.readonly_fields)
        return base
