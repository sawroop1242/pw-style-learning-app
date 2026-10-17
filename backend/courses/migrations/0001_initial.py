from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion

class Migration(migrations.Migration):
    initial = True
    dependencies = [migrations.swappable_dependency(settings.AUTH_USER_MODEL)]
    operations = [
        migrations.CreateModel(name="Course", fields=[
            ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
            ("title", models.CharField(max_length=180)),
            ("description", models.TextField(blank=True)),
            ("subject", models.CharField(default="General", max_length=80)),
            ("is_published", models.BooleanField(default=True)),
        ]),
        migrations.CreateModel(name="Lesson", fields=[
            ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
            ("title", models.CharField(max_length=180)),
            ("video_url", models.URLField(blank=True)),
            ("duration_minutes", models.PositiveIntegerField(default=0)),
            ("position", models.PositiveIntegerField(default=1)),
            ("is_published", models.BooleanField(default=True)),
            ("course", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="lessons", to="courses.course")),
        ], options={"ordering": ["position", "id"]}),
        migrations.CreateModel(name="Quiz", fields=[
            ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
            ("title", models.CharField(max_length=180)),
            ("description", models.TextField(blank=True)),
            ("is_published", models.BooleanField(default=True)),
            ("course", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name="quizzes", to="courses.course")),
        ]),
        migrations.CreateModel(name="Question", fields=[
            ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
            ("prompt", models.TextField()),
            ("explanation", models.TextField(blank=True)),
            ("position", models.PositiveIntegerField(default=1)),
            ("quiz", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="questions", to="courses.quiz")),
        ], options={"ordering": ["position", "id"]}),
        migrations.CreateModel(name="Choice", fields=[
            ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
            ("text", models.CharField(max_length=400)),
            ("is_correct", models.BooleanField(default=False)),
            ("question", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="choices", to="courses.question")),
        ]),
        migrations.CreateModel(name="Note", fields=[
            ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
            ("title", models.CharField(default="My note", max_length=180)),
            ("body", models.TextField()),
            ("updated_at", models.DateTimeField(auto_now=True)),
            ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="study_notes", to=settings.AUTH_USER_MODEL)),
        ], options={"ordering": ["-updated_at"]}),
        migrations.CreateModel(name="Progress", fields=[
            ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
            ("completed", models.BooleanField(default=False)),
            ("updated_at", models.DateTimeField(auto_now=True)),
            ("lesson", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="progress_records", to="courses.lesson")),
            ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="lesson_progress", to=settings.AUTH_USER_MODEL)),
        ], options={"constraints": [models.UniqueConstraint(fields=("user", "lesson"), name="unique_user_lesson_progress")]}),
    ]
