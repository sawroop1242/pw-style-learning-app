from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import CourseViewSet, LessonViewSet, QuizViewSet, NoteViewSet, ProgressViewSet, api_root
router = DefaultRouter()
router.register("courses", CourseViewSet, basename="course")
router.register("lessons", LessonViewSet, basename="lesson")
router.register("quizzes", QuizViewSet, basename="quiz")
router.register("notes", NoteViewSet, basename="note")
router.register("progress", ProgressViewSet, basename="progress")
urlpatterns = [path("", api_root), path("", include(router.urls))]
