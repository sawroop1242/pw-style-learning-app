from rest_framework import viewsets, permissions, status, filters, serializers
from rest_framework.decorators import api_view, action
from rest_framework.response import Response
from rest_framework.exceptions import ValidationError, PermissionDenied, NotFound
from django.db import IntegrityError, transaction
from django.shortcuts import get_object_or_404
from django.db.models import Q, Count
from django.utils import timezone
from .models import (
    Course, Lesson, Quiz, Note, Progress, CourseAccessGrant,
    CourseFolder, PdfResource, AccessCode, Question, Choice,
    QuizAttempt, AttemptAnswer, CsvImportJob, TestSeries,
    Bookmark, RevisionItem, StudyTask
)
from .models.access import generate_access_code, hash_access_code
from .serializers import (
    CourseListSerializer, CourseDetailSerializer, LessonSerializer,
    QuizSerializer, QuizAttemptSerializer, AttemptAnswerSerializer,
    QuizSubmissionSerializer, QuizResultSerializer,
    NoteSerializer, ProgressSerializer, BookmarkSerializer,
    RevisionItemSerializer, StudyTaskSerializer,
    PdfResourceSerializer, CourseFolderSerializer
)
from accounts.models import Role, Profile
import random
import json


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
    
    serializer_class = LessonSerializer
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
    
    def perform_create(self, serializer):
        course_id = self.kwargs.get("course_pk") or self.request.data.get("course")
        course = get_object_or_404(Course, pk=course_id)
        if course.owner != self.request.user:
            profile = getattr(self.request.user, "profile", None)
            if not (profile and profile.role == Role.MAIN_ADMIN):
                raise PermissionDenied("You can only create lessons in your own courses.")
        
        # Validate folder belongs to same course
        folder = self.request.data.get("folder")
        if folder:
            if folder.course_id != course.id:
                raise ValidationError({"folder": "Folder must belong to the same course."})
        
        serializer.save(course=course)
    
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
    
    serializer_class = PdfResourceSerializer
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
        folder_id = self.kwargs.get("folder_pk") or self.request.data.get("folder")
        folder = get_object_or_404(CourseFolder, pk=folder_id)
        if folder.course.owner != self.request.user:
            profile = getattr(self.request.user, "profile", None)
            if not (profile and profile.role == Role.MAIN_ADMIN):
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
def redeem_access_code(request):
    """Student endpoint to redeem an access code for a paid course."""
    serializer = AccessCodeRedemptionSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    
    code_value = serializer.validated_data["code"].strip().upper()
    course_id = serializer.validated_data["course_id"]
    user = request.user
    
    if not user.is_authenticated:
        return Response(
            {"detail": "Authentication required."},
            status=status.HTTP_401_UNAUTHORIZED
        )
    
    course = get_object_or_404(Course, pk=course_id, is_published=True)
    
    if course.pricing_mode != Course.PricingMode.PAID:
        return Response(
            {"detail": "This course does not require an access code."},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    # Check if user already has a grant
    if CourseAccessGrant.objects.filter(user=user, course=course, revoked_at__isnull=True).exists():
        return Response(
            {"detail": "You already have access to this course."},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    # Find matching code
    code_hash = hash_access_code(code_value)
    
    try:
        with transaction.atomic():
            access_code = AccessCode.objects.select_for_update().get(
                course=course,
                code_hash=code_hash,
                revoked_at__isnull=True,
            )
            
            # Check expiry
            if access_code.is_expired:
                return Response(
                    {"detail": "Invalid or expired access code."},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Check uses
            if access_code.uses_count >= access_code.max_uses:
                return Response(
                    {"detail": "Invalid or expired access code."},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Redeem
            access_code.uses_count += 1
            access_code.last_redeemed_by = user
            access_code.last_redeemed_at = timezone.now()
            access_code.save(update_fields=["uses_count", "last_redeemed_by", "last_redeemed_at", "updated_at"])
            
            # Create grant
            grant = CourseAccessGrant.objects.create(
                user=user,
                course=course,
                access_code=access_code,
                granted_by=access_code.created_by,
            )
            
            return Response({
                "message": "Access code redeemed successfully.",
                "course": {"id": course.id, "title": course.title},
                "grant_id": grant.id
            }, status=status.HTTP_201_CREATED)
            
    except AccessCode.DoesNotExist:
        # Generic error to prevent enumeration
        return Response(
            {"detail": "Invalid or expired access code."},
            status=status.HTTP_400_BAD_REQUEST
        )

class CourseViewSet(viewsets.ReadOnlyModelViewSet):
    """Course catalogue with search, filter, and ordering."""
    
    queryset = Course.objects.filter(is_published=True).select_related("owner").annotate(
        lesson_count=Count("lessons", filter=Q(lessons__is_published=True)),
        folder_count=Count("folders")
    )
    serializer_class = CourseListSerializer
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
    serializer_class = LessonSerializer
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ["position", "title", "created_at"]
    ordering = ["position", "id"]
    
    def get_queryset(self):
        qs = Lesson.objects.filter(is_published=True).select_related("course", "folder")
        
        # Filter by course if provided
        course_id = self.request.query_params.get("course")
        if course_id:
            try:
                course_id = int(course_id)
            except (ValueError, TypeError):
                return qs.none()
            qs = qs.filter(course_id=course_id)
        
        # If user is authenticated, filter out paid course lessons they don't have access to
        user = self.request.user
        if user.is_authenticated:
            free_course_ids = Course.objects.filter(
                is_published=True, pricing_mode=Course.PricingMode.FREE
            ).values_list("id", flat=True)
            
            paid_course_ids = CourseAccessGrant.objects.filter(
                user=user, revoked_at__isnull=True
            ).values_list("course_id", flat=True)
            
            allowed_course_ids = set(free_course_ids) | set(paid_course_ids)
            qs = qs.filter(course_id__in=allowed_course_ids)
        else:
            free_course_ids = Course.objects.filter(
                is_published=True, pricing_mode=Course.PricingMode.FREE
            ).values_list("id", flat=True)
            qs = qs.filter(course_id__in=free_course_ids)
            
        return qs


class QuizViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = QuizSerializer
    queryset = Quiz.objects.filter(is_published=True).prefetch_related("questions__choices")
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ["title", "created_at"]
    ordering = ["id"]


class NoteViewSet(viewsets.ModelViewSet):
    serializer_class = NoteSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ["updated_at", "created_at"]
    ordering = ["-updated_at"]
    
    def get_queryset(self):
        return Note.objects.filter(user=self.request.user)
    
    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


class ProgressViewSet(viewsets.ModelViewSet):
    serializer_class = ProgressSerializer
    permission_classes = [permissions.IsAuthenticated]
    http_method_names = ["get", "post", "patch", "head", "options"]
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ["updated_at", "lesson__position"]
    ordering = ["lesson__position", "lesson_id"]
    
    def get_queryset(self):
        return Progress.objects.filter(user=self.request.user).select_related("lesson", "lesson__course")
    
    def perform_create(self, serializer):
        lesson = serializer.validated_data.get("lesson")
        if lesson and not lesson.is_published:
            from rest_framework.exceptions import ValidationError
            raise ValidationError({"lesson": "Cannot record progress on a draft lesson."})
        
        try:
            serializer.save(user=self.request.user)
        except IntegrityError:
            existing = Progress.objects.get(user=self.request.user, lesson=lesson)
            if "completed" in serializer.validated_data:
                existing.completed = serializer.validated_data["completed"]
                existing.save(update_fields=["completed", "updated_at"])
            serializer.instance = existing


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
    """Public quiz listing and detail - no correct answers or explanations."""
    serializer_class = QuizSerializer
    filter_backends = [filters.OrderingFilter, filters.SearchFilter]
    search_fields = ["title", "description", "instructions"]
    ordering_fields = ["title", "created_at"]
    ordering = ["id"]
    
    def get_queryset(self):
        return Quiz.objects.filter(is_published=True).select_related("series", "course").prefetch_related(
            "questions__choices"
        )


class QuizAttemptViewSet(viewsets.ModelViewSet):
    """Quiz attempt management - start, submit, autosave, results."""
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
        if self.action in ["retrieve", "result"]:
            return QuizResultSerializer
        return QuizAttemptSerializer
    
    @action(detail=True, methods=["post"])
    def submit(self, request, pk=None):
        """Submit quiz answers and calculate score."""
        attempt = self.get_object()
        
        if attempt.status != QuizAttempt.Status.IN_PROGRESS:
            raise ValidationError("This attempt has already been submitted or expired.")
        
        # Check deadline
        if attempt.deadline and timezone.now() > attempt.deadline:
            # Auto-expire
            attempt.status = QuizAttempt.Status.EXPIRED
            attempt.submitted_at = timezone.now()
            attempt.save(update_fields=["status", "submitted_at", "updated_at"])
            raise ValidationError("Time limit exceeded. Attempt auto-submitted.")
        
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        answers_data = serializer.validated_data["answers"]
        
        with transaction.atomic():
            # Calculate score
            score, max_score = self._calculate_score(attempt, answers_data)
            
            # Save answers to AttemptAnswer records
            for ans_data in answers_data:
                question_id = ans_data.get("question_id")
                choice_ids = ans_data.get("choice_ids", [])
                marked_for_review = ans_data.get("marked_for_review", False)
                
                if not question_id:
                    continue
                
                try:
                    question = Question.objects.get(id=question_id, quiz=attempt.quiz)
                except Question.DoesNotExist:
                    continue
                
                # Validate choices belong to question
                if choice_ids:
                    valid_choice_ids = set(question.choices.values_list("id", flat=True))
                    invalid = [cid for cid in choice_ids if cid not in valid_choice_ids]
                    if invalid:
                        raise ValidationError({"choice_ids": f"Invalid choice IDs: {invalid}"})
                
                # Upsert answer
                answer, created = AttemptAnswer.objects.get_or_create(
                    attempt=attempt,
                    question=question,
                    defaults={"answered": bool(choice_ids), "marked_for_review": marked_for_review}
                )
                
                if not created:
                    answer.marked_for_review = marked_for_review
                
                answer.answered = bool(choice_ids)
                answer.save(update_fields=["answered", "marked_for_review", "updated_at"])
                
                # Update many-to-many
                answer.selected_choices.set(choice_ids)
            
            # Update attempt
            attempt.status = QuizAttempt.Status.SUBMITTED
            attempt.submitted_at = timezone.now()
            attempt.score = score
            attempt.max_score = max_score
            attempt.save(update_fields=["status", "submitted_at", "score", "max_score", "updated_at"])
            
            # Release result immediately if policy allows
            quiz = attempt.quiz
            if quiz.result_release_policy == Quiz.ResultReleasePolicy.IMMEDIATE:
                attempt.result_released_at = timezone.now()
                attempt.save(update_fields=["result_released_at", "updated_at"])
        
        return Response(QuizResultSerializer(attempt, context={"request": request}).data)
    
    @action(detail=True, methods=["get"])
    def result(self, request, pk=None):
        """Get quiz result (respects release policy)."""
        attempt = self.get_object()
        
        if not attempt.is_released:
            return Response(
                {"detail": "Results not yet released.", "status": attempt.status},
                status=status.HTTP_403_FORBIDDEN
            )
        
        return Response(QuizResultSerializer(attempt, context={"request": request}).data)
    
    @action(detail=True, methods=["post"])
    def autosave(self, request, pk=None):
        """Autosave answer for a question."""
        attempt = self.get_object()
        
        if attempt.status != QuizAttempt.Status.IN_PROGRESS:
            raise ValidationError("Cannot autosave on a submitted or expired attempt.")
        
        question_id = request.data.get("question_id")
        choice_ids = request.data.get("choice_ids", [])
        marked_for_review = request.data.get("marked_for_review", False)
        
        if not question_id:
            raise ValidationError({"question_id": "Required."})
        
        question = get_object_or_404(Question, pk=question_id, quiz=attempt.quiz)
        
        # Validate choices belong to question
        if choice_ids:
            valid_choice_ids = set(question.choices.values_list("id", flat=True))
            invalid = [cid for cid in choice_ids if cid not in valid_choice_ids]
            if invalid:
                raise ValidationError({"choice_ids": f"Invalid choice IDs: {invalid}"})
        
        # Upsert answer
        answer, created = AttemptAnswer.objects.get_or_create(
            attempt=attempt,
            question=question,
            defaults={"answered": True, "marked_for_review": marked_for_review}
        )
        
        if not created:
            answer.marked_for_review = marked_for_review
        
        answer.answered = bool(choice_ids)
        answer.save(update_fields=["answered", "marked_for_review", "updated_at"])
        
        # Update many-to-many
        answer.selected_choices.set(choice_ids)
        
        return Response({"status": "saved", "answered": answer.answered})
    
    def _calculate_score(self, attempt, answers_data):
        """Calculate score from submitted answers."""
        quiz = attempt.quiz
        score = 0
        max_score = 0
        
        # Get questions from attempt's question_order (snapshot)
        question_ids = attempt.question_order
        questions = {q.id: q for q in Question.objects.filter(id__in=question_ids)}
        
        for ans in answers_data:
            question_id = ans.get("question_id")
            choice_ids = set(ans.get("choice_ids", []))
            
            if question_id not in questions:
                continue
            
            question = questions[question_id]
            q_marks = question.marks or quiz.marks_per_question
            q_neg_marks = question.negative_marks if question.negative_marks is not None else quiz.negative_marks_per_wrong
            max_score += q_marks
            
            # Get correct choices
            correct_choice_ids = set(
                question.choices.filter(is_correct=True).values_list("id", flat=True)
            )
            
            # Check if answered
            if not choice_ids:
                # Unanswered - no marks, no penalty
                continue
            
            # Check correctness based on question type
            if question.question_type == Question.QuestionType.SINGLE_CHOICE:
                if len(choice_ids) == 1 and choice_ids == correct_choice_ids:
                    score += q_marks
                elif len(choice_ids) == 1:
                    # Wrong single choice
                    score -= q_neg_marks
            elif question.question_type == Question.QuestionType.MULTIPLE_CHOICE:
                if choice_ids == correct_choice_ids:
                    # Full correct
                    score += q_marks
                elif choice_ids & correct_choice_ids:
                    # Partial credit - only if explicitly configured
                    # For now, treat partial as incorrect
                    score -= q_neg_marks
                else:
                    # Completely wrong
                    score -= q_neg_marks
            elif question.question_type == Question.QuestionType.TRUE_FALSE:
                if len(choice_ids) == 1 and choice_ids == correct_choice_ids:
                    score += q_marks
                elif len(choice_ids) == 1:
                    score -= q_neg_marks
        
        # Score cannot go below zero
        score = max(score, 0)
        
        return score, max_score


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
def start_quiz_attempt(request):
    """Start a new quiz attempt."""
    quiz_id = request.data.get("quiz_id")
    if not quiz_id:
        return Response({"quiz_id": "Required."}, status=status.HTTP_400_BAD_REQUEST)
    
    quiz = get_object_or_404(Quiz, pk=quiz_id, is_published=True)
    
    # Check attempt limit
    if quiz.attempt_limit:
        attempt_count = QuizAttempt.objects.filter(user=request.user, quiz=quiz).count()
        if attempt_count >= quiz.attempt_limit:
            return Response(
                {"detail": f"Attempt limit ({quiz.attempt_limit}) reached."},
                status=status.HTTP_400_BAD_REQUEST
            )
    
    # Check availability window
    now = timezone.now()
    if quiz.opens_at and now < quiz.opens_at:
        return Response({"detail": "Quiz not yet open."}, status=status.HTTP_400_BAD_REQUEST)
    if quiz.closes_at and now > quiz.closes_at:
        return Response({"detail": "Quiz has closed."}, status=status.HTTP_400_BAD_REQUEST)
    
    # Check if there's an in-progress attempt to resume
    in_progress = QuizAttempt.objects.filter(
        user=request.user, quiz=quiz, status=QuizAttempt.Status.IN_PROGRESS
    ).first()
    
    if in_progress:
        # Resume existing attempt
        return Response(QuizAttemptSerializer(in_progress, context={"request": request}).data)
    
    # Create new attempt
    with transaction.atomic():
        # Get question order (with optional shuffling)
        questions = list(quiz.questions.all().order_by("position"))
        question_ids = [q.id for q in questions]
        
        if quiz.shuffle_questions:
            random.shuffle(question_ids)
        
        # Snapshot rules
        rules_snapshot = {
            "timing_mode": quiz.timing_mode,
            "duration_minutes": quiz.duration_minutes,
            "marks_per_question": str(quiz.marks_per_question),
            "negative_marks_per_wrong": str(quiz.negative_marks_per_wrong),
            "shuffle_options": quiz.shuffle_options,
            "result_release_policy": quiz.result_release_policy,
        }
        
        # Calculate deadline
        deadline = None
        if quiz.timing_mode in [Quiz.TimingMode.TIMED, Quiz.TimingMode.TOTAL_AND_SECTION]:
            if quiz.duration_minutes:
                deadline = now + timezone.timedelta(minutes=quiz.duration_minutes)
        
        attempt = QuizAttempt.objects.create(
            user=request.user,
            quiz=quiz,
            deadline=deadline,
            question_order=question_ids,
            rules_snapshot=rules_snapshot,
        )
        
        # Pre-create answer records for all questions
        for q in questions:
            AttemptAnswer.objects.create(attempt=attempt, question=q)
    
    return Response(QuizAttemptSerializer(attempt, context={"request": request}).data, status=status.HTTP_201_CREATED)


@api_view(["GET"])
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
