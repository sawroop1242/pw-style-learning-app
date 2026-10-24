from datetime import timedelta

from django.db import IntegrityError, transaction
from django.db.models import Count, Prefetch, Q
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import filters, permissions, serializers, status, viewsets
from rest_framework.decorators import (
    action,
    api_view,
    permission_classes,
    throttle_classes,
)
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response
from rest_framework.throttling import UserRateThrottle

from accounts.models import Role
from . import grading, policy
from .models import (
    AccessCode,
    AttemptAnswer,
    Bookmark,
    Choice,
    Course,
    CourseAccessGrant,
    CourseFolder,
    CsvImportJob,
    Lesson,
    Note,
    PdfResource,
    Progress,
    Question,
    Quiz,
    QuizAttempt,
    RevisionItem,
    StudyTask,
    TestSeries,
)
from .models.access import (
    generate_access_code,
    hash_access_code,
    legacy_hash_access_code,
    verify_access_code,
)
from .serializers import (
    AttemptAnswerSerializer,
    BookmarkSerializer,
    CourseDetailSerializer,
    CourseFolderSerializer,
    CourseListSerializer,
    LessonSerializer,
    NoteSerializer,
    PdfResourceSerializer,
    ProgressSerializer,
    QuizAttemptSerializer,
    QuizResultSerializer,
    QuizSerializer,
    QuizSubmissionSerializer,
    RevisionItemSerializer,
    StaffLessonSerializer,
    StaffPdfResourceSerializer,
    StudyTaskSerializer,
)
import random


class RedeemThrottle(UserRateThrottle):
    """Stops automated guessing of access codes from a compromised account."""

    rate = "20/hour"


class StartAttemptThrottle(UserRateThrottle):
    """Keeps a scripted client from opening attempts in a tight loop."""

    rate = "60/hour"


class IsSubAdminOrMainAdmin(permissions.BasePermission):
    """Allow access to sub-admins and main admins."""
    
    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False
        profile = getattr(request.user, "profile", None)
        return profile and profile.role in (Role.SUB_ADMIN, Role.MAIN_ADMIN)


class IsOwnerOrMainAdmin(permissions.BasePermission):
    """Allow access to object owner or main admin."""
    
    def has_object_permission(self, request, view, obj):
        if not request.user.is_authenticated:
            return False
        profile = getattr(request.user, "profile", None)
        if not profile:
            return False
        if profile.role == Role.MAIN_ADMIN:
            return True
        if profile.role == Role.SUB_ADMIN:
            # Check ownership via course owner
            owner = getattr(obj, "owner", None)
            if owner is None and hasattr(obj, "course"):
                owner = obj.course.owner
            return owner == request.user
        return False


class StaffCourseViewSet(viewsets.ModelViewSet):
    """Staff CRUD for courses - owner-scoped for sub-admins."""
    
    serializer_class = CourseDetailSerializer
    permission_classes = [IsSubAdminOrMainAdmin, IsOwnerOrMainAdmin]
    filter_backends = [filters.OrderingFilter, filters.SearchFilter]
    search_fields = ["title", "description", "subject"]
    ordering_fields = ["title", "subject", "position", "created_at", "is_published"]
    ordering = ["position", "-created_at"]
    
    def get_queryset(self):
        user = self.request.user
        profile = getattr(user, "profile", None)
        if profile and profile.role == Role.MAIN_ADMIN:
            return Course.objects.all().select_related("owner").annotate(
                lesson_count=Count("lessons", filter=Q(lessons__is_published=True)),
                folder_count=Count("folders")
            )
        # Sub-admin sees only owned courses
        return Course.objects.filter(owner=user).select_related("owner").annotate(
            lesson_count=Count("lessons", filter=Q(lessons__is_published=True)),
            folder_count=Count("folders")
        )
    
    def perform_create(self, serializer):
        serializer.save(owner=self.request.user)
    
    @action(detail=True, methods=["post"])
    def publish(self, request, pk=None):
        course = self.get_object()
        course.is_published = True
        course.save(update_fields=["is_published", "updated_at"])
        return Response({"status": "published"})
    
    @action(detail=True, methods=["post"])
    def unpublish(self, request, pk=None):
        course = self.get_object()
        course.is_published = False
        course.save(update_fields=["is_published", "updated_at"])
        return Response({"status": "unpublished"})


class StaffCourseFolderViewSet(viewsets.ModelViewSet):
    """Staff CRUD for course folders - owner-scoped."""
    
    serializer_class = CourseFolderSerializer
    permission_classes = [IsSubAdminOrMainAdmin, IsOwnerOrMainAdmin]
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ["position", "title", "created_at"]
    ordering = ["position", "id"]
    
    def get_queryset(self):
        user = self.request.user
        profile = getattr(user, "profile", None)
        if profile and profile.role == Role.MAIN_ADMIN:
            return CourseFolder.objects.all().select_related("course")
        return CourseFolder.objects.filter(course__owner=user).select_related("course")
    
    def perform_create(self, serializer):
        course_id = self.kwargs.get("course_pk") or self.request.data.get("course")
        course = get_object_or_404(Course, pk=course_id)
        # Check ownership
        if course.owner != self.request.user:
            profile = getattr(self.request.user, "profile", None)
            if not (profile and profile.role == Role.MAIN_ADMIN):
                raise PermissionDenied("You can only create folders in your own courses.")
        serializer.save(course=course)


class StaffLessonViewSet(viewsets.ModelViewSet):
    """Staff CRUD for lessons - owner-scoped."""

    serializer_class = StaffLessonSerializer
    permission_classes = [IsSubAdminOrMainAdmin, IsOwnerOrMainAdmin]
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ["position", "title", "created_at"]
    ordering = ["position", "id"]

    def get_queryset(self):
        user = self.request.user
        profile = getattr(user, "profile", None)
        if profile and profile.role == Role.MAIN_ADMIN:
            return Lesson.objects.all().select_related("course", "folder")
        return Lesson.objects.filter(course__owner=user).select_related("course", "folder")

    def _resolve_course(self, request):
        course_id = self.kwargs.get("course_pk") or request.data.get("course")
        if course_id in (None, ""):
            raise ValidationError({"course": ["This field is required."]})
        course = get_object_or_404(Course, pk=course_id)
        if course.owner != request.user and not policy.is_main_admin(request.user):
            raise PermissionDenied("You can only create lessons in your own courses.")
        return course

    def perform_create(self, serializer):
        course = self._resolve_course(self.request)
        # ``folder`` is a primary key once validated, so compare IDs rather
        # than attribute access on raw request data.
        folder = serializer.validated_data.get("folder")
        if folder is not None and folder.course_id != course.id:
            raise ValidationError({"folder": ["Folder must belong to the same course."]})
        serializer.save(course=course)

    def perform_update(self, serializer):
        # Object-level ownership is already enforced by get_object().
        instance = serializer.instance
        course = serializer.validated_data.get("course", instance.course)
        folder = serializer.validated_data.get("folder", instance.folder)
        if folder is not None and folder.course_id != course.id:
            raise ValidationError({"folder": ["Folder must belong to the same course."]})
        serializer.save()
    
    @action(detail=True, methods=["post"])
    def publish(self, request, pk=None):
        lesson = self.get_object()
        lesson.is_published = True
        lesson.save(update_fields=["is_published", "updated_at"])
        return Response({"status": "published"})
    
    @action(detail=True, methods=["post"])
    def unpublish(self, request, pk=None):
        lesson = self.get_object()
        lesson.is_published = False
        lesson.save(update_fields=["is_published", "updated_at"])
        return Response({"status": "unpublished"})


class StaffPdfResourceViewSet(viewsets.ModelViewSet):
    """Staff CRUD for PDF resources - owner-scoped."""

    serializer_class = StaffPdfResourceSerializer
    permission_classes = [IsSubAdminOrMainAdmin, IsOwnerOrMainAdmin]
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ["position", "title", "created_at"]
    ordering = ["position", "id"]
    
    def get_queryset(self):
        user = self.request.user
        profile = getattr(user, "profile", None)
        if profile and profile.role == Role.MAIN_ADMIN:
            return PdfResource.objects.all().select_related("folder", "folder__course")
        return PdfResource.objects.filter(folder__course__owner=user).select_related("folder", "folder__course")
    
    def perform_create(self, serializer):
        folder = serializer.validated_data.get("folder")
        folder_id = self.kwargs.get("folder_pk")
        if folder_id is not None:
            folder = get_object_or_404(CourseFolder, pk=folder_id)
        if folder is None:
            raise ValidationError({"folder": ["This field is required."]})
        if folder.course.owner != self.request.user and not policy.is_main_admin(
            self.request.user
        ):
            raise PermissionDenied("You can only add PDFs to folders in your own courses.")
        serializer.save(folder=folder)
    
    @action(detail=True, methods=["post"])
    def publish(self, request, pk=None):
        pdf = self.get_object()
        pdf.is_published = True
        pdf.save(update_fields=["is_published", "updated_at"])
        return Response({"status": "published"})
    
    @action(detail=True, methods=["post"])
    def unpublish(self, request, pk=None):
        pdf = self.get_object()
        pdf.is_published = False
        pdf.save(update_fields=["is_published", "updated_at"])
        return Response({"status": "unpublished"})


class AccessCodeRedemptionSerializer(serializers.Serializer):
    code = serializers.CharField(max_length=20)
    course_id = serializers.IntegerField()


class AccessCodeSerializer(serializers.ModelSerializer):
    """Serializer for staff access code management."""
    raw_code = serializers.CharField(read_only=True)
    status = serializers.CharField(read_only=True)
    is_expired = serializers.BooleanField(read_only=True)
    
    class Meta:
        model = AccessCode
        fields = [
            "id", "course", "code_hash", "raw_code", "max_uses", "uses_count",
            "expires_at", "status", "is_expired", "created_by", "last_redeemed_by",
            "last_redeemed_at", "revoked_at", "revoked_by", "created_at"
        ]
        read_only_fields = ["id", "code_hash", "raw_code", "uses_count", "status", 
                           "is_expired", "created_by", "last_redeemed_by",
                           "last_redeemed_at", "revoked_at", "revoked_by", "created_at"]


class StaffAccessCodeViewSet(viewsets.ModelViewSet):
    """Staff CRUD for access codes - owner-scoped."""
    
    serializer_class = AccessCodeSerializer
    permission_classes = [IsSubAdminOrMainAdmin, IsOwnerOrMainAdmin]
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ["created_at", "uses_count"]
    ordering = ["-created_at"]
    
    def get_queryset(self):
        user = self.request.user
        profile = getattr(user, "profile", None)
        if profile and profile.role == Role.MAIN_ADMIN:
            return AccessCode.objects.all().select_related("course", "created_by")
        return AccessCode.objects.filter(course__owner=user).select_related("course", "created_by")
    
    def perform_create(self, serializer):
        course_id = self.kwargs.get("course_pk") or self.request.data.get("course")
        course = get_object_or_404(Course, pk=course_id)
        if course.owner != self.request.user:
            profile = getattr(self.request.user, "profile", None)
            if not (profile and profile.role == Role.MAIN_ADMIN):
                raise PermissionDenied("You can only create codes for your own courses.")
        if course.pricing_mode != Course.PricingMode.PAID:
            raise ValidationError("Access codes can only be created for paid courses.")
        
        raw_code = generate_access_code()
        code_hash = hash_access_code(raw_code)
        serializer.save(course=course, code_hash=code_hash, created_by=self.request.user)
        # Add raw_code to response context
        serializer.instance.raw_code = raw_code
    
    @action(detail=True, methods=["post"])
    def revoke(self, request, pk=None):
        code = self.get_object()
        if code.revoked_at:
            return Response({"detail": "Code already revoked."}, status=status.HTTP_400_BAD_REQUEST)
        code.revoked_at = timezone.now()
        code.revoked_by = request.user
        code.save(update_fields=["revoked_at", "revoked_by", "updated_at"])
        return Response({"status": "revoked"})


@api_view(["POST"])
@permission_classes([permissions.IsAuthenticated])
@throttle_classes([RedeemThrottle])
def redeem_access_code(request):
    """Redeem a paid-course access code for the authenticated student.

    The code is matched by keyed hash, the row is locked for update while the
    use counter moves, and a duplicate grant (double tap, retry after timeout)
    resolves to the existing grant instead of a 500.
    """
    serializer = AccessCodeRedemptionSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)

    code_value = serializer.validated_data["code"].strip().upper()
    course_id = serializer.validated_data["course_id"]
    user = request.user

    course = get_object_or_404(Course, pk=course_id, is_published=True)

    if course.pricing_mode != Course.PricingMode.PAID:
        return Response(
            {"detail": "This course does not require an access code."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    existing_grant = CourseAccessGrant.objects.filter(
        user=user, course=course, revoked_at__isnull=True
    ).first()
    if existing_grant is not None:
        return Response(
            {"detail": "You already have access to this course."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    candidate_hashes = [hash_access_code(code_value)]
    legacy_hash = legacy_hash_access_code(code_value)
    candidate_hashes.append(legacy_hash)

    invalid = Response(
        {"detail": "Invalid or expired access code."},
        status=status.HTTP_400_BAD_REQUEST,
    )

    try:
        with transaction.atomic():
            access_code = (
                AccessCode.objects.select_for_update()
                .filter(course=course, code_hash__in=candidate_hashes, revoked_at__isnull=True)
                .first()
            )
            if access_code is None:
                return invalid

            # Re-verify in constant time; the query only narrows candidates.
            matches, needs_upgrade = verify_access_code(code_value, access_code.code_hash)
            if not matches:
                return invalid

            if access_code.is_expired:
                return invalid
            if access_code.uses_count >= access_code.max_uses:
                return invalid

            access_code.uses_count += 1
            access_code.last_redeemed_by = user
            access_code.last_redeemed_at = timezone.now()
            update_fields = [
                "uses_count",
                "last_redeemed_by",
                "last_redeemed_at",
                "updated_at",
            ]
            if needs_upgrade:
                # Transparently move legacy rows onto the keyed construction.
                access_code.code_hash = hash_access_code(code_value)
                update_fields.append("code_hash")
            access_code.save(update_fields=update_fields)

            grant, _created = CourseAccessGrant.objects.get_or_create(
                user=user,
                course=course,
                defaults={
                    "access_code": access_code,
                    "granted_by": access_code.created_by,
                },
            )
    except IntegrityError:
        # Lost a race with a concurrent redemption for the same course.
        grant = CourseAccessGrant.objects.filter(
            user=user, course=course, revoked_at__isnull=True
        ).first()
        if grant is None:
            return invalid

    return Response(
        {
            "message": "Access code redeemed successfully.",
            "course": {"id": course.id, "title": course.title},
            "grant_id": grant.id,
        },
        status=status.HTTP_201_CREATED,
    )


class CourseViewSet(viewsets.ReadOnlyModelViewSet):
    """Course catalogue with search, filter, and ordering."""
    
    queryset = Course.objects.filter(is_published=True).select_related("owner").annotate(
        lesson_count=Count("lessons", filter=Q(lessons__is_published=True), distinct=True),
        folder_count=Count("folders", distinct=True),
        quiz_total=Count("quizzes", filter=Q(quizzes__is_published=True), distinct=True),
    )
    serializer_class = CourseListSerializer
    permission_classes = [permissions.AllowAny]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ["title", "description", "subject"]
    ordering_fields = ["title", "subject", "position", "created_at", "price"]
    ordering = ["position", "-created_at"]
    
    def get_serializer_class(self):
        if self.action == "retrieve":
            return CourseDetailSerializer
        return CourseListSerializer
    
    def get_queryset(self):
        qs = super().get_queryset()
        # A batch page addresses its course by slug, so the list endpoint has to
        # be able to resolve one.
        slug = self.request.query_params.get("slug")
        if slug:
            qs = qs.filter(slug=slug)
        # Filter by subject
        subject = self.request.query_params.get("subject")
        if subject:
            qs = qs.filter(subject__iexact=subject)
        # Filter by pricing mode
        pricing_mode = self.request.query_params.get("pricing_mode")
        if pricing_mode:
            qs = qs.filter(pricing_mode=pricing_mode)
        # Filter by free/paid
        is_free = self.request.query_params.get("is_free")
        if is_free is not None:
            is_free = is_free.lower() == "true"
            if is_free:
                qs = qs.filter(pricing_mode=Course.PricingMode.FREE)
            else:
                qs = qs.filter(pricing_mode=Course.PricingMode.PAID)
        return qs


class LessonViewSet(viewsets.ReadOnlyModelViewSet):
    """Lesson listing limited to courses the caller may consume.

    Only free published courses (and paid courses with an active grant) are
    listed. Media URLs are additionally gated by the serializer, so a lesson
    that leaks into a response still cannot leak its video URL.
    """

    serializer_class = LessonSerializer
    permission_classes = [permissions.AllowAny]
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ["position", "title", "created_at"]
    ordering = ["position", "id"]

    def get_queryset(self):
        user = self.request.user
        qs = (
            Lesson.objects.filter(is_published=True, course__is_published=True)
            .select_related("course", "course__owner", "folder")
        )

        course_id = self.request.query_params.get("course")
        if course_id:
            try:
                course_id = int(course_id)
            except (ValueError, TypeError):
                return qs.none()
            qs = qs.filter(course_id=course_id)

        allowed_course_ids = set(
            Course.objects.filter(
                is_published=True, pricing_mode=Course.PricingMode.FREE
            ).values_list("id", flat=True)
        ) | policy.granted_course_ids(user)
        return qs.filter(course_id__in=allowed_course_ids)


class ProgressViewSet(viewsets.ModelViewSet):
    """Private lesson progress.

    A progress record is keyed by (user, lesson): re-posting the same lesson
    updates the existing row instead of raising a uniqueness error, and the
    lesson may not be swapped on update (that would expose other courses'
    lesson titles through the response).
    """

    serializer_class = ProgressSerializer
    permission_classes = [permissions.IsAuthenticated]
    http_method_names = ["get", "post", "patch", "head", "options"]
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ["updated_at", "lesson__position"]
    ordering = ["lesson__position", "lesson_id"]

    def get_queryset(self):
        return Progress.objects.filter(user=self.request.user).select_related(
            "lesson", "lesson__course"
        )

    @transaction.atomic
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        lesson = serializer.validated_data["lesson"]
        completed = serializer.validated_data.get("completed", False)

        record, created = Progress.objects.get_or_create(
            user=request.user,
            lesson=lesson,
            defaults={
                "completed": completed,
                "completed_at": timezone.now() if completed else None,
            },
        )
        if not created:
            record.completed = completed
            record.completed_at = timezone.now() if completed else None
            record.save(update_fields=["completed", "completed_at", "updated_at"])

        output = self.get_serializer(record)
        return Response(
            output.data,
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )

    def perform_update(self, serializer):
        completed = serializer.validated_data.get("completed", serializer.instance.completed)
        serializer.save(completed_at=timezone.now() if completed else None)


class NoteViewSet(viewsets.ModelViewSet):
    """Private notes CRUD for authenticated users."""
    serializer_class = NoteSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [filters.OrderingFilter, filters.SearchFilter]
    search_fields = ["title", "body"]
    ordering_fields = ["updated_at", "created_at"]
    ordering = ["-updated_at"]
    
    def get_queryset(self):
        return Note.objects.filter(user=self.request.user).select_related("lesson", "question")
    
    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


class BookmarkViewSet(viewsets.ModelViewSet):
    """Private bookmarks CRUD for authenticated users."""
    serializer_class = BookmarkSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ["created_at"]
    ordering = ["-created_at"]
    
    def get_queryset(self):
        return Bookmark.objects.filter(user=self.request.user).select_related("content_type")
    
    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


class RevisionItemViewSet(viewsets.ModelViewSet):
    """Private revision items CRUD for authenticated users."""
    serializer_class = RevisionItemSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ["updated_at", "status"]
    ordering = ["-updated_at"]
    
    def get_queryset(self):
        return RevisionItem.objects.filter(user=self.request.user).select_related("content_type")
    
    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


class StudyTaskViewSet(viewsets.ModelViewSet):
    """Private study tasks CRUD for authenticated users."""
    serializer_class = StudyTaskSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [filters.OrderingFilter, filters.SearchFilter]
    search_fields = ["title", "notes"]
    ordering_fields = ["due_at", "priority", "is_completed", "created_at"]
    ordering = ["is_completed", "due_at", "-created_at"]
    
    def get_queryset(self):
        return StudyTask.objects.filter(user=self.request.user).select_related("linked_content_type")
    
    def perform_create(self, serializer):
        serializer.save(user=self.request.user)
    
    @action(detail=True, methods=["post"])
    def complete(self, request, pk=None):
        """Mark task as completed."""
        task = self.get_object()
        task.is_completed = True
        task.completed_at = timezone.now()
        task.save(update_fields=["is_completed", "completed_at", "updated_at"])
        return Response(StudyTaskSerializer(task, context={"request": request}).data)
    
    @action(detail=True, methods=["post"])
    def reopen(self, request, pk=None):
        """Mark task as incomplete (reopen)."""
        task = self.get_object()
        task.is_completed = False
        task.completed_at = None
        task.save(update_fields=["is_completed", "completed_at", "updated_at"])
        return Response(StudyTaskSerializer(task, context={"request": request}).data)


class QuizViewSet(viewsets.ReadOnlyModelViewSet):
    """Public quiz listing and detail.

    Only quizzes the caller may sit are listed. Questions are withheld by the
    serializer unless access is granted, so a paid test's paper is never part
    of a public payload.
    """

    serializer_class = QuizSerializer
    permission_classes = [permissions.AllowAny]
    filter_backends = [filters.OrderingFilter, filters.SearchFilter]
    search_fields = ["title", "description", "instructions"]
    ordering_fields = ["title", "created_at"]
    ordering = ["id"]

    def get_queryset(self):
        user = self.request.user
        qs = (
            Quiz.objects.filter(is_published=True)
            .select_related("series", "series__owner", "course", "course__owner")
            .annotate(
                question_total=Count("questions", distinct=True),
                attempt_total=Count("attempts", distinct=True),
            )
        )
        if not policy.is_staff_role(user):
            # Free published courses, plus paid courses the student holds a
            # grant for. Series-only quizzes are public when the series is.
            qs = qs.filter(
                Q(course__is_published=True, course__pricing_mode=Course.PricingMode.FREE)
                | Q(course_id__in=policy.granted_course_ids(user))
                | Q(course__isnull=True, series__is_published=True)
            )
        # Nested listings: a batch page shows the tests that belong to it.
        course = self.request.query_params.get("course")
        if course:
            qs = qs.filter(course_id=course) if str(course).isdigit() else qs.filter(course__slug=course)
        series = self.request.query_params.get("series")
        if series:
            qs = qs.filter(series_id=series) if str(series).isdigit() else qs.filter(series__slug=series)
        return qs.prefetch_related("questions__choices")


class QuizAttemptViewSet(viewsets.GenericViewSet, viewsets.mixins.ListModelMixin,
                          viewsets.mixins.RetrieveModelMixin):
    """Student attempt history plus the submit / autosave / result actions.

    Attempts are server-owned: this view exposes no create, update or destroy
    route, so a client can never set its own status, score, question order or
    release time. Starting an attempt is a separate, quota-checked endpoint.
    """

    serializer_class = QuizAttemptSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ["started_at", "status"]
    ordering = ["-started_at"]

    def get_queryset(self):
        return QuizAttempt.objects.filter(user=self.request.user).select_related("quiz")

    def get_serializer_class(self):
        if self.action == "submit":
            return QuizSubmissionSerializer
        if self.action in ("retrieve", "result"):
            return QuizResultSerializer
        return QuizAttemptSerializer

    @staticmethod
    def _release_if_due(attempt):
        """Honour AFTER_CLOSE releases at read time, without a cron job."""
        if attempt.result_released_at is not None:
            return False
        quiz = attempt.quiz
        if (
            quiz.result_release_policy == Quiz.ResultReleasePolicy.AFTER_CLOSE
            and attempt.status == QuizAttempt.Status.SUBMITTED
            and quiz.closes_at is not None
            and timezone.now() >= quiz.closes_at
        ):
            attempt.result_released_at = timezone.now()
            attempt.save(update_fields=["result_released_at", "updated_at"])
            return True
        return False

    def _persist_answers(self, attempt, answers_data):
        """Write the submitted answers, then grade from the database.

        Grading never trusts the payload: an autosaved answer that is absent
        from the final submit still counts, and the denominator covers every
        question in the attempt snapshot.
        """
        question_ids = set(attempt.question_order or [])
        questions = {
            question.id: question
            for question in Question.objects.filter(
                id__in=question_ids, quiz=attempt.quiz
            ).prefetch_related("choices")
        }

        for entry in answers_data:
            question_id = entry.get("question_id")
            if question_id not in questions:
                continue
            question = questions[question_id]
            raw_choices = entry.get("choice_ids") or []
            if not isinstance(raw_choices, (list, tuple)):
                raise ValidationError({"choice_ids": ["Expected a list of choice IDs."]})
            try:
                choice_ids = {int(choice_id) for choice_id in raw_choices}
            except (TypeError, ValueError):
                raise ValidationError({"choice_ids": ["Choice IDs must be integers."]})

            valid_ids = {choice.id for choice in question.choices.all()}
            invalid = sorted(choice_ids - valid_ids)
            if invalid:
                raise ValidationError(
                    {"choice_ids": [f"Invalid choice IDs: {invalid}"]}
                )

            answer, _created = AttemptAnswer.objects.get_or_create(
                attempt=attempt, question=question
            )
            answer.answered = bool(choice_ids)
            answer.marked_for_review = bool(entry.get("marked_for_review", False))
            answer.save(update_fields=["answered", "marked_for_review", "updated_at"])
            answer.selected_choices.set(choice_ids)

    @action(detail=True, methods=["post"])
    def submit(self, request, pk=None):
        """Submit the attempt and score it server-side."""
        attempt = self.get_object()

        if attempt.status != QuizAttempt.Status.IN_PROGRESS:
            raise ValidationError("This attempt has already been submitted or expired.")

        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        now = timezone.now()
        expired = attempt.deadline is not None and now > attempt.deadline

        with transaction.atomic():
            # Lock the row so a double submit cannot score twice.
            attempt = QuizAttempt.objects.select_for_update().get(pk=attempt.pk)
            if attempt.status != QuizAttempt.Status.IN_PROGRESS:
                raise ValidationError("This attempt has already been submitted or expired.")

            if not expired:
                self._persist_answers(attempt, serializer.validated_data["answers"])

            result = grading.grade_attempt(attempt)
            attempt.status = (
                QuizAttempt.Status.EXPIRED if expired else QuizAttempt.Status.SUBMITTED
            )
            attempt.submitted_at = now
            attempt.score = result["score"]
            attempt.max_score = result["max_score"]
            update_fields = [
                "status", "submitted_at", "score", "max_score", "updated_at",
            ]
            if attempt.quiz.result_release_policy == Quiz.ResultReleasePolicy.IMMEDIATE:
                attempt.result_released_at = now
                update_fields.append("result_released_at")
            attempt.save(update_fields=update_fields)

        response = QuizResultSerializer(attempt, context={"request": request}).data
        return Response(response)

    @action(detail=True, methods=["get"])
    def result(self, request, pk=None):
        """Result payload, subject to the quiz's release policy."""
        attempt = self.get_object()
        self._release_if_due(attempt)

        if not attempt.is_released:
            return Response(
                {"detail": "Results not yet released.", "status": attempt.status},
                status=status.HTTP_403_FORBIDDEN,
            )
        return Response(QuizResultSerializer(attempt, context={"request": request}).data)

    @action(detail=True, methods=["post"])
    def autosave(self, request, pk=None):
        """Persist a single answer without scoring it."""
        attempt = self.get_object()

        if attempt.status != QuizAttempt.Status.IN_PROGRESS:
            raise ValidationError("Cannot autosave on a submitted or expired attempt.")
        if attempt.deadline is not None and timezone.now() > attempt.deadline:
            raise ValidationError("Time limit exceeded; the attempt is closed.")

        question_id = request.data.get("question_id")
        if not question_id:
            raise ValidationError({"question_id": ["Required."]})
        try:
            question_id = int(question_id)
        except (TypeError, ValueError):
            raise ValidationError({"question_id": ["Must be an integer."]})

        question = get_object_or_404(
            Question, pk=question_id, quiz=attempt.quiz
        )
        if question_id not in set(attempt.question_order or []):
            raise ValidationError({"question_id": ["Not part of this attempt."]})

        raw_choices = request.data.get("choice_ids") or []
        if not isinstance(raw_choices, (list, tuple)):
            raise ValidationError({"choice_ids": ["Expected a list of choice IDs."]})
        try:
            choice_ids = {int(choice_id) for choice_id in raw_choices}
        except (TypeError, ValueError):
            raise ValidationError({"choice_ids": ["Choice IDs must be integers."]})

        valid_ids = set(question.choices.values_list("id", flat=True))
        invalid = sorted(choice_ids - valid_ids)
        if invalid:
            raise ValidationError({"choice_ids": [f"Invalid choice IDs: {invalid}"]})

        answer, _created = AttemptAnswer.objects.get_or_create(
            attempt=attempt, question=question
        )
        answer.answered = bool(choice_ids)
        answer.marked_for_review = bool(request.data.get("marked_for_review", False))
        answer.save(update_fields=["answered", "marked_for_review", "updated_at"])
        answer.selected_choices.set(choice_ids)

        return Response({"status": "saved", "answered": answer.answered})


class StaffQuizViewSet(viewsets.ModelViewSet):
    """Staff CRUD for quizzes - owner-scoped."""
    serializer_class = QuizSerializer
    permission_classes = [IsSubAdminOrMainAdmin, IsOwnerOrMainAdmin]
    filter_backends = [filters.OrderingFilter, filters.SearchFilter]
    search_fields = ["title", "description", "instructions"]
    ordering_fields = ["title", "created_at", "is_published"]
    ordering = ["-created_at"]
    
    def get_queryset(self):
        user = self.request.user
        profile = getattr(user, "profile", None)
        if profile and profile.role == Role.MAIN_ADMIN:
            return Quiz.objects.all().select_related("series", "course")
        # Sub-admin sees only owned quizzes
        return Quiz.objects.filter(
            Q(series__owner=user) | Q(course__owner=user)
        ).distinct().select_related("series", "course")
    
    @action(detail=True, methods=["post"])
    def publish(self, request, pk=None):
        quiz = self.get_object()
        quiz.is_published = True
        quiz.save(update_fields=["is_published", "updated_at"])
        return Response({"status": "published"})
    
    @action(detail=True, methods=["post"])
    def unpublish(self, request, pk=None):
        quiz = self.get_object()
        quiz.is_published = False
        quiz.save(update_fields=["is_published", "updated_at"])
        return Response({"status": "unpublished"})


class StaffQuestionViewSet(viewsets.ModelViewSet):
    """Staff CRUD for questions - owner-scoped."""
    permission_classes = [IsSubAdminOrMainAdmin, IsOwnerOrMainAdmin]
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ["position", "created_at"]
    ordering = ["position", "id"]
    
    def get_queryset(self):
        user = self.request.user
        profile = getattr(user, "profile", None)
        if profile and profile.role == Role.MAIN_ADMIN:
            return Question.objects.all().select_related("quiz")
        return Question.objects.filter(
            Q(quiz__series__owner=user) | Q(quiz__course__owner=user)
        ).distinct().select_related("quiz")
    
    def get_serializer_class(self):
        from rest_framework import serializers
        
        class QuestionCreateSerializer(serializers.ModelSerializer):
            class Meta:
                model = Question
                fields = [
                    "id", "quiz", "prompt", "explanation", "question_type",
                    "marks", "negative_marks", "difficulty", "topic", "position"
                ]
                read_only_fields = ["id"]
        
        return QuestionCreateSerializer


class StaffChoiceViewSet(viewsets.ModelViewSet):
    """Staff CRUD for choices - owner-scoped."""
    permission_classes = [IsSubAdminOrMainAdmin, IsOwnerOrMainAdmin]
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ["position", "created_at"]
    ordering = ["position", "id"]
    
    def get_queryset(self):
        user = self.request.user
        profile = getattr(user, "profile", None)
        if profile and profile.role == Role.MAIN_ADMIN:
            return Choice.objects.all().select_related("question")
        return Choice.objects.filter(
            Q(question__quiz__series__owner=user) | Q(question__quiz__course__owner=user)
        ).distinct().select_related("question")
    
    def get_serializer_class(self):
        from rest_framework import serializers
        
        class ChoiceSerializer(serializers.ModelSerializer):
            class Meta:
                model = Choice
                fields = ["id", "question", "text", "is_correct", "position"]
                read_only_fields = ["id"]
        
        return ChoiceSerializer


class CsvImportJobViewSet(viewsets.ModelViewSet):
    """Staff CSV import job management."""
    serializer_class = serializers.ModelSerializer
    permission_classes = [IsSubAdminOrMainAdmin, IsOwnerOrMainAdmin]
    
    class CsvImportJobSerializer(serializers.ModelSerializer):
        class Meta:
            model = CsvImportJob
            fields = [
                "id", "quiz", "source_url", "status", "total_rows",
                "imported_rows", "error_summary", "confirmed_at", "created_at"
            ]
            read_only_fields = ["id", "status", "total_rows", "imported_rows", "error_summary", "confirmed_at", "created_at"]
    
    serializer_class = CsvImportJobSerializer
    
    def get_queryset(self):
        user = self.request.user
        profile = getattr(user, "profile", None)
        if profile and profile.role == Role.MAIN_ADMIN:
            return CsvImportJob.objects.all().select_related("quiz")
        return CsvImportJob.objects.filter(
            Q(quiz__series__owner=user) | Q(quiz__course__owner=user)
        ).distinct().select_related("quiz")
    
    @action(detail=True, methods=["post"])
    def validate(self, request, pk=None):
        """Validate CSV from URL without importing."""
        job = self.get_object()
        
        if job.status != CsvImportJob.Status.PENDING:
            raise ValidationError("Job already processed.")
        
        # In a real implementation, fetch and validate CSV here
        # For now, just update status
        job.status = CsvImportJob.Status.VALIDATED
        job.total_rows = 0  # Would be set from actual CSV
        job.save(update_fields=["status", "total_rows", "updated_at"])
        
        return Response({"status": "validated", "preview": []})
    
    @action(detail=True, methods=["post"])
    def confirm_import(self, request, pk=None):
        """Confirm and execute CSV import."""
        job = self.get_object()
        
        if job.status != CsvImportJob.Status.VALIDATED:
            raise ValidationError("Job must be validated first.")
        
        # In a real implementation, import CSV here
        job.status = CsvImportJob.Status.IMPORTED
        job.imported_rows = job.total_rows
        job.confirmed_at = timezone.now()
        job.save(update_fields=["status", "imported_rows", "confirmed_at", "updated_at"])
        
        return Response({"status": "imported"})


class StaffTestSeriesViewSet(viewsets.ModelViewSet):
    """Staff CRUD for test series - owner-scoped."""
    permission_classes = [IsSubAdminOrMainAdmin, IsOwnerOrMainAdmin]
    filter_backends = [filters.OrderingFilter, filters.SearchFilter]
    search_fields = ["title", "description", "subject"]
    ordering_fields = ["title", "created_at", "is_published"]
    ordering = ["-created_at"]
    
    def get_serializer_class(self):
        from rest_framework import serializers
        
        class TestSeriesSerializer(serializers.ModelSerializer):
            class Meta:
                model = TestSeries
                fields = [
                    "id", "title", "slug", "description", "image_url",
                    "subject", "is_published", "created_at", "updated_at"
                ]
                read_only_fields = ["id", "slug", "created_at", "updated_at"]
        
        return TestSeriesSerializer
    
    def get_queryset(self):
        user = self.request.user
        profile = getattr(user, "profile", None)
        if profile and profile.role == Role.MAIN_ADMIN:
            return TestSeries.objects.all()
        return TestSeries.objects.filter(owner=user)
    
    def perform_create(self, serializer):
        serializer.save(owner=self.request.user)
    
    @action(detail=True, methods=["post"])
    def publish(self, request, pk=None):
        series = self.get_object()
        series.is_published = True
        series.save(update_fields=["is_published", "updated_at"])
        return Response({"status": "published"})
    
    @action(detail=True, methods=["post"])
    def unpublish(self, request, pk=None):
        series = self.get_object()
        series.is_published = False
        series.save(update_fields=["is_published", "updated_at"])
        return Response({"status": "unpublished"})


@api_view(["POST"])
@permission_classes([permissions.IsAuthenticated])
@throttle_classes([StartAttemptThrottle])
def start_quiz_attempt(request):
    """Start (or resume) an attempt for an accessible, published quiz.

    Resuming is the default: a learner with an open attempt gets that attempt
    back rather than a second one, so a refresh never burns an attempt.
    """
    quiz_id = request.data.get("quiz_id")
    if not quiz_id:
        return Response({"quiz_id": ["Required."]}, status=status.HTTP_400_BAD_REQUEST)
    try:
        quiz_id = int(quiz_id)
    except (TypeError, ValueError):
        return Response({"quiz_id": ["Must be an integer."]}, status=status.HTTP_400_BAD_REQUEST)

    quiz = get_object_or_404(Quiz.objects.select_related("course", "series"), pk=quiz_id)

    if not policy.can_access_quiz(request.user, quiz):
        return Response(
            {"detail": "You do not have access to this test."},
            status=status.HTTP_403_FORBIDDEN,
        )

    now = timezone.now()
    if quiz.opens_at and now < quiz.opens_at:
        return Response({"detail": "Test is not open yet."}, status=status.HTTP_400_BAD_REQUEST)
    if quiz.closes_at and now > quiz.closes_at:
        return Response({"detail": "Test has closed."}, status=status.HTTP_400_BAD_REQUEST)

    with transaction.atomic():
        # Serialise concurrent starts for this learner+quiz pair.
        in_progress = (
            QuizAttempt.objects.select_for_update()
            .filter(user=request.user, quiz=quiz, status=QuizAttempt.Status.IN_PROGRESS)
            .first()
        )
        if in_progress is not None:
            return Response(
                QuizAttemptSerializer(in_progress, context={"request": request}).data
            )

        if quiz.attempt_limit is not None:
            used = QuizAttempt.objects.filter(user=request.user, quiz=quiz).count()
            if used >= quiz.attempt_limit:
                return Response(
                    {"detail": f"Attempt limit ({quiz.attempt_limit}) reached."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        questions = list(quiz.questions.all().order_by("position", "id"))
        question_ids = [question.id for question in questions]
        if quiz.shuffle_questions:
            random.shuffle(question_ids)

        rules_snapshot = {
            "timing_mode": quiz.timing_mode,
            "duration_minutes": quiz.duration_minutes,
            "marks_per_question": str(quiz.marks_per_question),
            "negative_marks_per_wrong": str(quiz.negative_marks_per_wrong),
            "shuffle_options": quiz.shuffle_options,
            "result_release_policy": quiz.result_release_policy,
        }

        deadline = None
        if (
            quiz.timing_mode in (Quiz.TimingMode.TIMED, Quiz.TimingMode.TOTAL_AND_SECTION)
            and quiz.duration_minutes
        ):
            deadline = now + timedelta(minutes=quiz.duration_minutes)

        attempt = QuizAttempt.objects.create(
            user=request.user,
            quiz=quiz,
            deadline=deadline,
            question_order=question_ids,
            rules_snapshot=rules_snapshot,
        )
        grading.ensure_answer_rows(attempt, questions)

    return Response(
        QuizAttemptSerializer(attempt, context={"request": request}).data,
        status=status.HTTP_201_CREATED,
    )


@api_view(["GET"])
@permission_classes([permissions.AllowAny])
def api_root(request):
    return Response({
        "name": "StudySpace API", 
        "courses": "/api/courses/", 
        "lessons": "/api/lessons/", 
        "quizzes": "/api/quizzes/", 
        "notes": "/api/notes/", 
        "progress": "/api/progress/", 
        "token": "/api/token/",
        "quiz_attempts": "/api/quiz-attempts/",
        "start_quiz": "/api/quizzes/start/",
    })
