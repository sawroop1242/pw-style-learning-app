from rest_framework import serializers
from django.contrib.contenttypes.models import ContentType
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


class PdfResourceSerializer(serializers.ModelSerializer):
    class Meta:
        model = PdfResource
        fields = [
            "id", "folder", "title", "description", "file_url", "position",
            "is_published", "is_protected"
        ]
        read_only_fields = ["id"]


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
    video_url = serializers.URLField(validators=[validate_video_url])

    class Meta:
        model = Lesson
        fields = [
            "id", "course", "folder", "title", "description", "video_url",
            "duration_minutes", "position", "is_published"
        ]
        read_only_fields = ["id"]


class CourseListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for course listings."""
    lesson_count = serializers.IntegerField(source="lessons.count", read_only=True)
    folder_count = serializers.IntegerField(source="folders.count", read_only=True)

    class Meta:
        model = Course
        fields = [
            "id", "title", "slug", "description", "subject", "image_url",
            "pricing_mode", "price", "currency", "telegram_handle", "telegram_url",
            "is_published", "lesson_count", "folder_count", "position",
            "created_at", "updated_at"
        ]


class CourseDetailSerializer(serializers.ModelSerializer):
    """Full serializer for course detail with nested folders/lessons/PDFs."""
    lesson_count = serializers.IntegerField(source="lessons.count", read_only=True)
    folder_count = serializers.IntegerField(source="folders.count", read_only=True)
    folders = serializers.SerializerMethodField()

    class Meta:
        model = Course
        fields = [
            "id", "title", "slug", "description", "subject", "image_url",
            "pricing_mode", "price", "currency", "telegram_handle", "telegram_url",
            "is_published", "lesson_count", "folder_count", "position",
            "folders", "created_at", "updated_at"
        ]

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
    questions = QuestionSerializer(many=True, read_only=True)

    class Meta:
        model = Quiz
        fields = [
            "id", "course", "series", "title", "description", "instructions",
            "timing_mode", "duration_minutes", "attempt_limit",
            "shuffle_questions", "shuffle_options", "result_release_policy",
            "marks_per_question", "negative_marks_per_wrong",
            "pass_threshold_percent", "opens_at", "closes_at",
            "is_published", "questions", "created_at", "updated_at"
        ]
        read_only_fields = ["id", "created_at", "updated_at"]


class QuizAttemptSerializer(serializers.ModelSerializer):
    class Meta:
        model = QuizAttempt
        fields = [
            "id", "quiz", "status", "started_at", "deadline", "submitted_at",
            "score", "max_score", "question_order", "rules_snapshot", "result_released_at"
        ]
        read_only_fields = ["id", "started_at", "deadline", "submitted_at", "score", "max_score", "rules_snapshot", "question_order"]


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

    def get_correct_count(self, obj):
        correct = 0
        for ans in obj.answers.all():
            question = ans.question
            correct_choice_ids = set(
                question.choices.filter(is_correct=True).values_list("id", flat=True)
            )
            selected = set(ans.selected_choices.values_list("id", flat=True))
            if question.question_type == Question.QuestionType.SINGLE_CHOICE:
                if len(selected) == 1 and selected == correct_choice_ids:
                    correct += 1
            elif question.question_type == Question.QuestionType.MULTIPLE_CHOICE:
                if selected == correct_choice_ids:
                    correct += 1
            elif question.question_type == Question.QuestionType.TRUE_FALSE:
                if len(selected) == 1 and selected == correct_choice_ids:
                    correct += 1
        return correct

    def get_incorrect_count(self, obj):
        incorrect = 0
        for ans in obj.answers.all():
            question = ans.question
            correct_choice_ids = set(
                question.choices.filter(is_correct=True).values_list("id", flat=True)
            )
            selected = set(ans.selected_choices.values_list("id", flat=True))
            if not ans.answered:
                continue
            is_correct = False
            if question.question_type == Question.QuestionType.SINGLE_CHOICE:
                if len(selected) == 1 and selected == correct_choice_ids:
                    is_correct = True
            elif question.question_type == Question.QuestionType.MULTIPLE_CHOICE:
                if selected == correct_choice_ids:
                    is_correct = True
            elif question.question_type == Question.QuestionType.TRUE_FALSE:
                if len(selected) == 1 and selected == correct_choice_ids:
                    is_correct = True
            if not is_correct:
                incorrect += 1
        return incorrect

    def get_unanswered_count(self, obj):
        return obj.answers.filter(answered=False).count()

    def get_marked_for_review_count(self, obj):
        return obj.answers.filter(marked_for_review=True).count()

    def get_answers_detail(self, obj):
        # Only include if result is released
        if not obj.is_released:
            return None
        return AttemptAnswerDetailSerializer(obj.answers.all(), many=True, context=self.context).data

    def get_section_breakdown(self, obj):
        # Placeholder for section-wise breakdown
        return None


class AttemptAnswerDetailSerializer(serializers.ModelSerializer):
    """Detailed answer with correct answer info - only for released results."""
    selected_choices = ChoiceSerializer(many=True, read_only=True)
    correct_choices = ChoiceSerializer(many=True, read_only=True, source="question.choices.filter(is_correct=True)")
    is_correct = serializers.BooleanField(read_only=True)
    explanation = serializers.CharField(source="question.explanation", read_only=True)

    class Meta:
        model = AttemptAnswer
        fields = [
            "id", "question", "selected_choices", "correct_choices",
            "answered", "marked_for_review", "is_correct", "explanation"
        ]


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
