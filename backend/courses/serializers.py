from rest_framework import serializers
from .models import Course, Lesson, Quiz, Question, Choice, Note, Progress

class LessonSerializer(serializers.ModelSerializer):
    class Meta:
        model = Lesson
        fields = ["id", "course", "title", "video_url", "duration_minutes", "position"]
class CourseSerializer(serializers.ModelSerializer):
    lesson_count = serializers.IntegerField(source="lessons.count", read_only=True)
    class Meta:
        model = Course
        fields = ["id", "title", "description", "subject", "lesson_count"]
class ChoiceSerializer(serializers.ModelSerializer):
    class Meta:
        model = Choice
        fields = ["id", "text"]
class QuestionSerializer(serializers.ModelSerializer):
    choices = ChoiceSerializer(many=True, read_only=True)
    class Meta:
        model = Question
        fields = ["id", "prompt", "explanation", "position", "choices"]
class QuizSerializer(serializers.ModelSerializer):
    questions = QuestionSerializer(many=True, read_only=True)
    class Meta:
        model = Quiz
        fields = ["id", "course", "title", "description", "questions"]
class NoteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Note
        fields = ["id", "title", "body", "updated_at"]
        read_only_fields = ["id", "updated_at"]
class ProgressSerializer(serializers.ModelSerializer):
    lesson_title = serializers.CharField(source="lesson.title", read_only=True)
    class Meta:
        model = Progress
        fields = ["id", "lesson", "lesson_title", "completed", "updated_at"]
        read_only_fields = ["id", "updated_at"]
