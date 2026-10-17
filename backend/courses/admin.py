from django.contrib import admin
from .models import Course, Lesson, Quiz, Question, Choice, Note, Progress

class LessonInline(admin.TabularInline):
    model = Lesson
    extra = 0
class ChoiceInline(admin.TabularInline):
    model = Choice
    extra = 2
class QuestionInline(admin.TabularInline):
    model = Question
    extra = 1
@admin.register(Course)
class CourseAdmin(admin.ModelAdmin):
    list_display = ("title", "subject", "is_published")
    list_filter = ("subject", "is_published")
    search_fields = ("title", "description")
    inlines = [LessonInline]
@admin.register(Quiz)
class QuizAdmin(admin.ModelAdmin):
    list_display = ("title", "course", "is_published")
    inlines = [QuestionInline]
@admin.register(Question)
class QuestionAdmin(admin.ModelAdmin):
    list_display = ("prompt", "quiz", "position")
    inlines = [ChoiceInline]
admin.site.register(Note)
admin.site.register(Progress)
