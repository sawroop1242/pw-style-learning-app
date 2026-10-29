from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    CommunityPostViewSet, PdfResourceViewSet,
    QuestionReportViewSet, notifications_read, notifications_view,
    CourseViewSet, LessonViewSet, QuizViewSet, NoteViewSet, ProgressViewSet,
    QuizAttemptViewSet, BookmarkViewSet, RevisionItemViewSet, StudyTaskViewSet,
    StaffCourseViewSet, StaffCourseFolderViewSet, StaffLessonViewSet,
    StaffPdfResourceViewSet, StaffAccessCodeViewSet,
    StaffQuizViewSet, StaffQuestionViewSet, StaffChoiceViewSet,
    CsvImportJobViewSet, StaffTestSeriesViewSet, StaffCourseFacultyViewSet,
    StaffQuestionReportViewSet,
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
router.register("question-reports", QuestionReportViewSet, basename="question-report")

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
staff_router.register("faculty", StaffCourseFacultyViewSet, basename="staff-faculty")
staff_router.register("question-reports", StaffQuestionReportViewSet, basename="staff-question-report")

urlpatterns = [
    path("", api_root),
    path("quizzes/start/", start_quiz_attempt, name="start-quiz-attempt"),
    path("access-codes/redeem/", redeem_access_code, name="redeem-access-code"),
    path("notifications/", notifications_view, name="notifications"),
    path("notifications/read/", notifications_read, name="notifications-read"),
    path("", include(router.urls)),
    path("staff/", include(staff_router.urls)),
]
