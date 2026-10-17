from django.conf import settings
from django.db import models

class Course(models.Model):
    title = models.CharField(max_length=180)
    description = models.TextField(blank=True)
    subject = models.CharField(max_length=80, default="General")
    is_published = models.BooleanField(default=True)
    def __str__(self): return self.title

class Lesson(models.Model):
    course = models.ForeignKey(Course, related_name="lessons", on_delete=models.CASCADE)
    title = models.CharField(max_length=180)
    video_url = models.URLField(blank=True)
    duration_minutes = models.PositiveIntegerField(default=0)
    position = models.PositiveIntegerField(default=1)
    is_published = models.BooleanField(default=True)
    class Meta: ordering = ["position", "id"]
    def __str__(self): return f"{self.course}: {self.title}"

class Quiz(models.Model):
    course = models.ForeignKey(Course, related_name="quizzes", on_delete=models.CASCADE, null=True, blank=True)
    title = models.CharField(max_length=180)
    description = models.TextField(blank=True)
    is_published = models.BooleanField(default=True)
    def __str__(self): return self.title

class Question(models.Model):
    quiz = models.ForeignKey(Quiz, related_name="questions", on_delete=models.CASCADE)
    prompt = models.TextField()
    explanation = models.TextField(blank=True)
    position = models.PositiveIntegerField(default=1)
    class Meta: ordering = ["position", "id"]
    def __str__(self): return self.prompt[:80]

class Choice(models.Model):
    question = models.ForeignKey(Question, related_name="choices", on_delete=models.CASCADE)
    text = models.CharField(max_length=400)
    is_correct = models.BooleanField(default=False)
    def __str__(self): return self.text[:80]

class Note(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, related_name="study_notes", on_delete=models.CASCADE)
    title = models.CharField(max_length=180, default="My note")
    body = models.TextField()
    updated_at = models.DateTimeField(auto_now=True)
    class Meta: ordering = ["-updated_at"]
    def __str__(self): return f"{self.user}: {self.title}"

class Progress(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, related_name="lesson_progress", on_delete=models.CASCADE)
    lesson = models.ForeignKey(Lesson, related_name="progress_records", on_delete=models.CASCADE)
    completed = models.BooleanField(default=False)
    updated_at = models.DateTimeField(auto_now=True)
    class Meta:
        constraints = [models.UniqueConstraint(fields=["user", "lesson"], name="unique_user_lesson_progress")]
    def __str__(self): return f"{self.user} — {self.lesson}"
