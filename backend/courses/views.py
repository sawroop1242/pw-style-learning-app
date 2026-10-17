from rest_framework import viewsets, permissions
from rest_framework.decorators import api_view
from rest_framework.response import Response
from .models import Course, Lesson, Quiz, Note, Progress
from .serializers import CourseSerializer, LessonSerializer, QuizSerializer, NoteSerializer, ProgressSerializer

class CourseViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = CourseSerializer
    queryset = Course.objects.filter(is_published=True).prefetch_related("lessons")
class LessonViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = LessonSerializer
    queryset = Lesson.objects.filter(is_published=True).select_related("course")
    def get_queryset(self):
        qs = super().get_queryset()
        course_id = self.request.query_params.get("course")
        return qs.filter(course_id=course_id) if course_id else qs
class QuizViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = QuizSerializer
    queryset = Quiz.objects.filter(is_published=True).prefetch_related("questions__choices")
class NoteViewSet(viewsets.ModelViewSet):
    serializer_class = NoteSerializer
    permission_classes = [permissions.IsAuthenticated]
    def get_queryset(self): return Note.objects.filter(user=self.request.user)
    def perform_create(self, serializer): serializer.save(user=self.request.user)
class ProgressViewSet(viewsets.ModelViewSet):
    serializer_class = ProgressSerializer
    permission_classes = [permissions.IsAuthenticated]
    http_method_names = ["get", "post", "patch", "head", "options"]
    def get_queryset(self): return Progress.objects.filter(user=self.request.user)
    def perform_create(self, serializer): serializer.save(user=self.request.user)
@api_view(["GET"])
def api_root(request):
    return Response({"name":"StudySpace API", "courses":"/api/courses/", "lessons":"/api/lessons/", "quizzes":"/api/quizzes/", "notes":"/api/notes/", "progress":"/api/progress/", "token":"/api/token/"})
