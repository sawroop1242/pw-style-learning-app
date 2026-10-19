from django.conf import settings
from django.db import models

from .catalog import Course
from .common import TimeStampedModel


class CommunityPost(TimeStampedModel):
    """Announcement authored by staff. Platform-wide when course is null;
    course-scoped otherwise. Students are read-only."""

    title = models.CharField(max_length=180)
    body = models.TextField()
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="community_posts"
    )
    course = models.ForeignKey(
        Course,
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="community_posts",
    )
    is_published = models.BooleanField(default=False)
    is_pinned = models.BooleanField(default=False)

    class Meta:
        ordering = ["-is_pinned", "-created_at"]
        indexes = [models.Index(fields=["is_published", "-created_at"])]

    def __str__(self):
        return self.title
