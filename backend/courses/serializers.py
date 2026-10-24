from rest_framework import serializers
from django.contrib.contenttypes.models import ContentType
from . import grading, policy
from .models import (
    Course, CourseFolder, Lesson, PdfResource, Quiz, Question, Choice, Note, Progress,
    QuizAttempt, AttemptAnswer, Bookmark, RevisionItem, StudyTask
)

ALLOWED_VIDEO_SCHEMES = {"https"}
ALLOWED_VIDEO_HOSTS = {
    "www.youtube.com", "youtube.com", "youtu.be",
    "www.vimeo.com", "vimeo.com", "player.vimeo.com",
    "drive.google.com", "www.drive.google.com",
}


def validate_video_url(value):
    """Validate video URL uses allowed scheme and host."""
    if not value:
        return value
    from urllib.parse import urlparse
    parsed = urlparse(value)
    if parsed.scheme not in ALLOWED_VIDEO_SCHEMES:
        raise serializers.ValidationError("Video URL must use HTTPS.")
    if parsed.netloc not in ALLOWED_VIDEO_HOSTS:
        raise serializers.ValidationError(
            f"Video host '{parsed.netloc}' is not allowed. "
            f"Allowed: {', '.join(sorted(ALLOWED_VIDEO_HOSTS))}"
        )
    return value


def _request_user(serializer):
    request = serializer.context.get("request")
    return getattr(request, "user", None)


class PdfResourceSerializer(serializers.ModelSerializer):
    """PDF metadata. ``file_url`` is withheld unless the caller may read the
    course, so a protected chapter cannot be fetched from a public payload."""

    file_url = serializers.SerializerMethodField()
    is_locked = serializers.SerializerMethodField()

    class Meta:
        model = PdfResource
        fields = [
            "id", "folder", "title", "description", "file_url", "position",
            "is_published", "is_protected", "is_locked"
        ]
        read_only_fields = ["id"]

    def get_file_url(self, obj):
        course = getattr(obj.folder, "course", None)
        if obj.is_protected and not policy.can_read_media(_request_user(self), course):
            return None
        return obj.file_url

    def get_is_locked(self, obj):
        return self.get_file_url(obj) is None


class CourseFolderSerializer(serializers.ModelSerializer):
    lessons = serializers.SerializerMethodField()
    pdf_resources = serializers.SerializerMethodField()

    class Meta:
        model = CourseFolder
        fields = ["id", "course", "title", "description", "position", "lessons", "pdf_resources"]
        read_only_fields = ["id"]

    def get_lessons(self, folder):
        lessons = folder.lessons.filter(is_published=True)
        return LessonSerializer(lessons, many=True, context=self.context).data

    def get_pdf_resources(self, folder):
        pdfs = folder.pdf_resources.filter(is_published=True)
        return PdfResourceSerializer(pdfs, many=True, context=self.context).data


class LessonSerializer(serializers.ModelSerializer):
    """Public lesson payload. ``video_url`` is only returned to learners who
    may consume the course; titles stay visible for curriculum previews."""

    video_url = serializers.SerializerMethodField()
    is_locked = serializers.SerializerMethodField()

    class Meta:
        model = Lesson
        fields = [
            "id", "course", "folder", "title", "description", "video_url",
            "duration_minutes", "position", "is_published", "is_locked"
        ]
        read_only_fields = fields

    def get_video_url(self, obj):
        if not policy.can_read_media(_request_user(self), obj.course):
            return None
        return obj.video_url

    def get_is_locked(self, obj):
        return bool(obj.video_url) and self.get_video_url(obj) is None


class StaffLessonSerializer(serializers.ModelSerializer):
    """Write serializer for staff; ``video_url`` is optional and validated."""

    video_url = serializers.URLField(
        required=False, allow_blank=True, validators=[validate_video_url]
    )

    class Meta:
        model = Lesson
        fields = [
            "id", "course", "folder", "title", "description", "video_url",
            "duration_minutes", "position", "is_published"
        ]
        read_only_fields = ["id"]

    def validate(self, attrs):
        course = attrs.get("course") or getattr(self.instance, "course", None)
        folder = attrs.get("folder") or getattr(self.instance, "folder", None)
        if folder is not None and course is not None and folder.course_id != course.id:
            raise serializers.ValidationError(
                {"folder": "Folder must belong to the same course as the lesson."}
            )
        return attrs


class StaffPdfResourceSerializer(serializers.ModelSerializer):
    """Write serializer for staff; the storage URL is writable here only."""

    file_url = serializers.URLField()

    class Meta:
        model = PdfResource
        fields = [
            "id", "folder", "title", "description", "file_url", "position",
            "is_published", "is_protected"
        ]
        read_only_fields = ["id"]


class CourseListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for course listings."""
    lesson_count = serializers.IntegerField(source="lessons.count", read_only=True)
    folder_count = serializers.IntegerField(source="folders.count", read_only=True)
    quiz_count = serializers.SerializerMethodField()

    class Meta:
        model = Course
        fields = [
            "id", "title", "slug", "description", "subject", "image_url",
            "pricing_mode", "price", "currency", "telegram_handle", "telegram_url",
            "is_published", "lesson_count", "folder_count", "quiz_count", "position",
            "created_at", "updated_at"
        ]

    def get_quiz_count(self, course):
        annotated = getattr(course, "quiz_total", None)
        if annotated is not None:
            return annotated
        return course.quizzes.filter(is_published=True).count()


class CourseDetailSerializer(serializers.ModelSerializer):
    """Full serializer for course detail with nested folders/lessons/PDFs.

    ``has_access`` tells the client whether media URLs are present or locked;
    the URLs themselves are gated by the nested serializers.
    """
    lesson_count = serializers.IntegerField(source="lessons.count", read_only=True)
    folder_count = serializers.IntegerField(source="folders.count", read_only=True)
    quiz_count = serializers.SerializerMethodField()
    has_access = serializers.SerializerMethodField()
    folders = serializers.SerializerMethodField()

    class Meta:
        model = Course
        fields = [
            "id", "title", "slug", "description", "subject", "image_url",
            "pricing_mode", "price", "currency", "telegram_handle", "telegram_url",
            "is_published", "lesson_count", "folder_count", "quiz_count", "position",
            "has_access", "folders", "created_at", "updated_at"
        ]

    def get_quiz_count(self, course):
        annotated = getattr(course, "quiz_total", None)
        if annotated is not None:
            return annotated
        return course.quizzes.filter(is_published=True).count()

    def get_has_access(self, course):
        return policy.can_access_course(_request_user(self), course)

    def get_folders(self, course):
        folders = course.folders.all().prefetch_related("lessons", "pdf_resources")
        return CourseFolderSerializer(folders, many=True, context=self.context).data


class ChoiceSerializer(serializers.ModelSerializer):
    class Meta:
        model = Choice
        fields = ["id", "text"]


class QuestionSerializer(serializers.ModelSerializer):
    choices = ChoiceSerializer(many=True, read_only=True)

    class Meta:
        model = Question
        # Explanation should NOT be returned before submission
        fields = [
            "id", "prompt", "position", "choices", "question_type", "marks",
            "negative_marks", "difficulty", "topic"
        ]


class QuizSerializer(serializers.ModelSerializer):
    """Quiz metadata. Questions and choices are only included when the caller
    may sit the test; a paid test must not be readable from a public list.

    ``series_title``/``series_subject``/``course_title``/``course_slug`` and
    ``attempt_count`` are read-only conveniences so a listing can label a test
    without a second request per row.
    """

    questions = serializers.SerializerMethodField()
    question_count = serializers.SerializerMethodField()
    has_access = serializers.SerializerMethodField()
    series_title = serializers.CharField(source="series.title", read_only=True, default=None)
    series_subject = serializers.CharField(source="series.subject", read_only=True, default=None)
    course_title = serializers.CharField(source="course.title", read_only=True, default=None)
    course_slug = serializers.CharField(source="course.slug", read_only=True, default=None)
    course_subject = serializers.CharField(source="course.subject", read_only=True, default=None)
    attempt_count = serializers.SerializerMethodField()

    class Meta:
        model = Quiz
        fields = [
            "id", "course", "series", "title", "description", "instructions",
            "timing_mode", "duration_minutes", "attempt_limit",
            "shuffle_questions", "shuffle_options", "result_release_policy",
            "marks_per_question", "negative_marks_per_wrong",
            "pass_threshold_percent", "opens_at", "closes_at",
            "is_published", "has_access", "question_count", "questions",
            "series_title", "series_subject", "course_title", "course_slug",
            "course_subject", "attempt_count",
            "created_at", "updated_at"
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    def _question_count(self, quiz):
        annotated = getattr(quiz, "question_total", None)
        if annotated is not None:
            return annotated
        return quiz.questions.count()

    def get_question_count(self, quiz):
        return self._question_count(quiz)

    def get_has_access(self, quiz):
        return policy.can_access_quiz(_request_user(self), quiz)

    def get_attempt_count(self, quiz):
        annotated = getattr(quiz, "attempt_total", None)
        if annotated is not None:
            return annotated
        return quiz.attempts.count()

    def get_questions(self, quiz):
        if not self.get_has_access(quiz):
            return []
        return QuestionSerializer(quiz.questions.all(), many=True, context=self.context).data


class QuizAttemptSerializer(serializers.ModelSerializer):
    """Read-only view of an attempt. Every field is server-owned: a client may
    never set status, score, snapshot or release state directly."""

    class Meta:
        model = QuizAttempt
        fields = [
            "id", "quiz", "status", "started_at", "deadline", "submitted_at",
            "score", "max_score", "question_order", "rules_snapshot", "result_released_at"
        ]
        read_only_fields = fields


class AttemptAnswerSerializer(serializers.ModelSerializer):
    selected_choices = serializers.PrimaryKeyRelatedField(
        many=True, queryset=Choice.objects.all(), required=False
    )

    class Meta:
        model = AttemptAnswer
        fields = ["id", "question", "selected_choices", "answered", "marked_for_review"]
        read_only_fields = ["id", "answered"]


class QuizSubmissionSerializer(serializers.Serializer):
    """Serializer for submitting quiz answers."""
    answers = serializers.ListField(
        child=serializers.DictField(child=serializers.JSONField()),
        help_text="List of answer objects with question_id and choice_ids"
    )


class QuizResultSerializer(serializers.Serializer):
    """Serializer for quiz results after submission/release."""
    id = serializers.IntegerField()
    quiz = serializers.SerializerMethodField()
    status = serializers.CharField()
    started_at = serializers.DateTimeField()
    deadline = serializers.DateTimeField(allow_null=True)
    submitted_at = serializers.DateTimeField(allow_null=True)
    score = serializers.DecimalField(max_digits=8, decimal_places=2, allow_null=True)
    max_score = serializers.DecimalField(max_digits=8, decimal_places=2, allow_null=True)
    percentage = serializers.SerializerMethodField()
    passed = serializers.SerializerMethodField()
    time_taken_seconds = serializers.SerializerMethodField()
    correct_count = serializers.SerializerMethodField()
    incorrect_count = serializers.SerializerMethodField()
    unanswered_count = serializers.SerializerMethodField()
    marked_for_review_count = serializers.SerializerMethodField()
    answers_detail = serializers.SerializerMethodField()
    section_breakdown = serializers.SerializerMethodField()
    result_released_at = serializers.DateTimeField(allow_null=True)
    
    def get_quiz(self, obj):
        if hasattr(obj.quiz, 'id'):
            return obj.quiz.id
        return obj.quiz

    def get_percentage(self, obj):
        if obj.max_score and obj.max_score > 0:
            return round((obj.score / obj.max_score) * 100, 2)
        return 0.0

    def get_passed(self, obj):
        quiz = obj.quiz
        if quiz.pass_threshold_percent is not None and obj.score is not None and obj.max_score and obj.max_score > 0:
            return obj.score >= (obj.max_score * quiz.pass_threshold_percent / 100)
        return None

    def get_time_taken_seconds(self, obj):
        if obj.submitted_at and obj.started_at:
            return int((obj.submitted_at - obj.started_at).total_seconds())
        return None

    def _graded(self, obj):
        """Grade once per serialization and cache it on the instance."""
        cached = getattr(obj, "_graded_cache", None)
        if cached is None:
            cached = grading.grade_attempt(obj)
            obj._graded_cache = cached
        return cached

    def get_correct_count(self, obj):
        return self._graded(obj)["correct"]

    def get_incorrect_count(self, obj):
        return self._graded(obj)["incorrect"]

    def get_unanswered_count(self, obj):
        return self._graded(obj)["unanswered"]

    def get_marked_for_review_count(self, obj):
        return self._graded(obj)["marked_for_review"]

    def get_answers_detail(self, obj):
        # Only include if result is released
        if not obj.is_released:
            return None
        answers = obj.answers.select_related("question").prefetch_related(
            "selected_choices", "question__choices"
        ).order_by("question__position", "question_id")
        return AttemptAnswerDetailSerializer(answers, many=True, context=self.context).data

    def get_section_breakdown(self, obj):
        if not obj.is_released:
            return None
        return [
            {
                "section": bucket["section"],
                "correct": bucket["correct"],
                "incorrect": bucket["incorrect"],
                "unanswered": bucket["unanswered"],
                "score": str(bucket["score"]),
                "max_score": str(bucket["max_score"]),
            }
            for bucket in self._graded(obj)["sections"]
        ]


class AttemptAnswerDetailSerializer(serializers.ModelSerializer):
    """Detailed answer with correct answer info - only for released results."""
    selected_choices = ChoiceSerializer(many=True, read_only=True)
    correct_choices = serializers.SerializerMethodField()
    is_correct = serializers.SerializerMethodField()
    explanation = serializers.CharField(source="question.explanation", read_only=True)

    class Meta:
        model = AttemptAnswer
        fields = [
            "id", "question", "selected_choices", "correct_choices",
            "answered", "marked_for_review", "is_correct", "explanation"
        ]

    def get_correct_choices(self, answer):
        correct = [choice for choice in answer.question.choices.all() if choice.is_correct]
        return ChoiceSerializer(correct, many=True).data

    def get_is_correct(self, answer):
        return grading.answer_is_correct(answer.question, grading.selected_ids(answer))


class NoteSerializer(serializers.ModelSerializer):
    lesson_title = serializers.CharField(source="lesson.title", read_only=True)
    question_text = serializers.CharField(source="question.prompt", read_only=True)

    class Meta:
        model = Note
        fields = ["id", "title", "body", "lesson", "lesson_title", "question", "question_text", "updated_at"]
        read_only_fields = ["id", "updated_at"]


class ProgressSerializer(serializers.ModelSerializer):
    lesson_title = serializers.CharField(source="lesson.title", read_only=True)

    class Meta:
        model = Progress
        fields = ["id", "lesson", "lesson_title", "completed", "completed_at", "updated_at"]
        read_only_fields = ["id", "updated_at", "completed_at"]

    def validate_lesson(self, lesson):
        """A progress row may only point at a published lesson the caller can
        actually access. Without this, a student could re-point an existing row
        at a draft lesson and read its title back from the response."""
        user = _request_user(self)
        if not lesson.is_published:
            raise serializers.ValidationError("Cannot record progress on a draft lesson.")
        if not policy.can_access_course(user, lesson.course):
            raise serializers.ValidationError(
                "You do not have access to this lesson."
            )
        if self.instance is not None and self.instance.lesson_id != lesson.id:
            raise serializers.ValidationError(
                "The lesson of a progress record cannot be changed."
            )
        return lesson

    def validate(self, attrs):
        if self.instance is not None and "lesson" in attrs:
            attrs.pop("lesson")
        return attrs


class BookmarkSerializer(serializers.ModelSerializer):
    resource_type = serializers.CharField(source="content_type.model", read_only=True)
    resource_title = serializers.SerializerMethodField()

    class Meta:
        model = Bookmark
        fields = ["id", "content_type", "object_id", "resource_type", "resource_title", "note", "tag", "created_at"]
        read_only_fields = ["id", "created_at", "resource_type"]

    def get_resource_title(self, obj):
        if obj.resource:
            if hasattr(obj.resource, 'title'):
                return obj.resource.title
            elif hasattr(obj.resource, 'prompt'):
                return obj.resource.prompt[:80]
            elif hasattr(obj.resource, 'text'):
                return obj.resource.text[:80]
        return str(obj.resource)

    def validate(self, attrs):
        content_type = attrs.get("content_type")
        object_id = attrs.get("object_id")
        user = self.context["request"].user

        if content_type and content_type.model not in Bookmark.BOOKMARKABLE_MODELS:
            raise serializers.ValidationError({"content_type": "Resource type cannot be bookmarked."})

        # Check if resource exists and is accessible
        if content_type and object_id:
            model_class = content_type.model_class()
            try:
                resource = model_class.objects.get(pk=object_id)
                # For courses/lessons, check if published or user has access
                if hasattr(resource, 'is_published') and not resource.is_published:
                    # Allow bookmarking draft if user is owner
                    if hasattr(resource, 'owner') and resource.owner != user:
                        raise serializers.ValidationError({"object_id": "Cannot bookmark unpublished resource."})
            except model_class.DoesNotExist:
                raise serializers.ValidationError({"object_id": "Resource not found."})

        return attrs


class RevisionItemSerializer(serializers.ModelSerializer):
    resource_type = serializers.CharField(source="content_type.model", read_only=True)
    resource_title = serializers.SerializerMethodField()

    class Meta:
        model = RevisionItem
        fields = ["id", "content_type", "object_id", "resource_type", "resource_title", "status", "note", "updated_at"]
        read_only_fields = ["id", "updated_at", "resource_type"]

    def get_resource_title(self, obj):
        if obj.resource:
            if hasattr(obj.resource, 'title'):
                return obj.resource.title
            elif hasattr(obj.resource, 'prompt'):
                return obj.resource.prompt[:80]
        return str(obj.resource)

    def validate(self, attrs):
        content_type = attrs.get("content_type")
        object_id = attrs.get("object_id")

        if content_type and content_type.model not in RevisionItem.REVISABLE_MODELS:
            raise serializers.ValidationError({"content_type": "Resource type cannot be revised."})

        # Check if resource exists
        if content_type and object_id:
            model_class = content_type.model_class()
            if not model_class.objects.filter(pk=object_id).exists():
                raise serializers.ValidationError({"object_id": "Resource not found."})

        return attrs


class StudyTaskSerializer(serializers.ModelSerializer):
    linked_resource_type = serializers.CharField(source="linked_content_type.model", read_only=True)
    linked_resource_title = serializers.SerializerMethodField()

    class Meta:
        model = StudyTask
        fields = [
            "id", "title", "notes", "due_at", "duration_minutes", "priority",
            "is_completed", "completed_at", "linked_content_type", "linked_object_id",
            "linked_resource_type", "linked_resource_title", "created_at", "updated_at"
        ]
        read_only_fields = ["id", "created_at", "updated_at", "completed_at", "linked_resource_type"]

    def get_linked_resource_title(self, obj):
        if obj.linked_resource:
            if hasattr(obj.linked_resource, 'title'):
                return obj.linked_resource.title
            elif hasattr(obj.linked_resource, 'prompt'):
                return obj.linked_resource.prompt[:80]
        return str(obj.linked_resource)

    def validate(self, attrs):
        linked_content_type = attrs.get("linked_content_type")
        linked_object_id = attrs.get("linked_object_id")

        if linked_content_type and linked_content_type.model not in ("course", "lesson", "quiz", "revisionitem"):
            raise serializers.ValidationError({"linked_content_type": "Unsupported linked resource."})

        if linked_content_type and linked_object_id:
            model_class = linked_content_type.model_class()
            if not model_class.objects.filter(pk=linked_object_id).exists():
                raise serializers.ValidationError({"linked_object_id": "Linked resource not found."})

        if attrs.get("duration_minutes") is not None and attrs["duration_minutes"] <= 0:
            raise serializers.ValidationError({"duration_minutes": "Duration must be positive."})

        return attrs
