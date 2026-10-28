from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    CommunityPostViewSet, PdfResourceViewSet,
    CourseViewSet, LessonViewSet, QuizViewSet, NoteViewSet, ProgressViewSet,
    QuizAttemptViewSet, BookmarkViewSet, RevisionItemViewSet, StudyTaskViewSet,
    StaffCourseViewSet, StaffCourseFolderViewSet, StaffLessonViewSet,
    StaffPdfResourceViewSet, StaffAccessCodeViewSet,
    StaffQuizViewSet, StaffQuestionViewSet, StaffChoiceViewSet,
    CsvImportJobViewSet, StaffTestSeriesViewSet,
    redeem_access_code, start_quiz_attempt, api_root
)

router = DefaultRouter()
router.register("courses", CourseViewSet, basename="course")
router.register("pdfs", PdfResourceViewSet, basename="pdf")
router.register("community", CommunityPostViewSet, basename="community")
router.register("lessons", LessonViewSet, basename="lesson")
router.register("quizzes", QuizViewSet, basename="quiz")
router.register("notes", NoteViewSet, basename="note")
router.register("progress", ProgressViewSet, basename="progress")
router.register("bookmarks", BookmarkViewSet, basename="bookmark")
router.register("revision-items", RevisionItemViewSet, basename="revision-item")
router.register("study-tasks", StudyTaskViewSet, basename="study-task")
router.register("quiz-attempts", QuizAttemptViewSet, basename="quiz-attempt")

# Staff routes (owner-scoped)
staff_router = DefaultRouter()
staff_router.register("courses", StaffCourseViewSet, basename="staff-course")
staff_router.register("folders", StaffCourseFolderViewSet, basename="staff-folder")
staff_router.register("lessons", StaffLessonViewSet, basename="staff-lesson")
staff_router.register("pdfs", StaffPdfResourceViewSet, basename="staff-pdf")
staff_router.register("access-codes", StaffAccessCodeViewSet, basename="staff-access-code")
staff_router.register("quizzes", StaffQuizViewSet, basename="staff-quiz")
staff_router.register("questions", StaffQuestionViewSet, basename="staff-question")
staff_router.register("choices", StaffChoiceViewSet, basename="staff-choice")
staff_router.register("import-jobs", CsvImportJobViewSet, basename="staff-import-job")
staff_router.register("test-series", StaffTestSeriesViewSet, basename="staff-test-series")

urlpatterns = [
    path("", api_root),
    path("quizzes/start/", start_quiz_attempt, name="start-quiz-attempt"),
    path("access-codes/redeem/", redeem_access_code, name="redeem-access-code"),
    path("", include(router.urls)),
    path("staff/", include(staff_router.urls)),
]
