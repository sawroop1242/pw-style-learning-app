"""Single source of truth for "may this user see this?" decisions.

Every public read or write path calls one of the helpers below instead of
re-deriving ownership rules inline. Keeping the rules in one module is what
makes the "paid content never leaks" guarantee testable in one place.

Rules
-----
* Staff (sub-admin / main admin) may always read content they own; a main
  admin may read everything.
* A published free course is readable by anyone, including anonymous users.
* A published paid course is readable by anonymous users only at the
  catalogue level (title, price, curriculum titles). Media URLs, protected
  PDF locations, quiz questions and test content require an active grant.
* Draft or unpublished content is readable by its owner and the main admin
  only, and never by other staff members.
"""

from accounts.models import Role
from .models import Course, CourseAccessGrant, Quiz

__all__ = [
    "role_of",
    "is_main_admin",
    "is_staff_role",
    "is_owner",
    "granted_course_ids",
    "can_access_course",
    "can_access_quiz",
    "can_read_media",
]


def role_of(user):
    """Return the application role for ``user`` or ``None`` when anonymous."""
    if user is None or not getattr(user, "is_authenticated", False):
        return None
    profile = getattr(user, "profile", None)
    return profile.role if profile is not None else None


def is_main_admin(user):
    return role_of(user) == Role.MAIN_ADMIN


def is_staff_role(user):
    return role_of(user) in {Role.SUB_ADMIN, Role.MAIN_ADMIN}


def is_owner(user, obj):
    """True when ``user`` owns ``obj`` (course, series, or a child of one)."""
    if user is None or not getattr(user, "is_authenticated", False):
        return False
    owner = getattr(obj, "owner", None)
    if owner is not None:
        return owner == user
    # Lessons, folders, PDFs and quizzes inherit ownership from their course.
    for attr in ("course", "series"):
        parent = getattr(obj, attr, None)
        if parent is not None and getattr(parent, "owner", None) == user:
            return True
    folder = getattr(obj, "folder", None)
    if folder is not None:
        return getattr(getattr(folder, "course", None), "owner", None) == user
    quiz = getattr(obj, "quiz", None)
    if quiz is not None:
        return is_owner(user, quiz)
    return False


def granted_course_ids(user):
    """Active paid-course grants for ``user``; empty set when anonymous."""
    if user is None or not getattr(user, "is_authenticated", False):
        return set()
    return set(
        CourseAccessGrant.objects.filter(user=user, revoked_at__isnull=True)
        .values_list("course_id", flat=True)
    )


def can_access_course(user, course):
    """Full learning access to a course (media, PDFs, paid lessons).

    The cheap, unambiguous checks run first so a free course never has to
    touch ``course.owner`` (which would cost a query per row in list views).
    """
    if course is None:
        return False
    if is_main_admin(user):
        return True
    if not course.is_published:
        # Unpublished content is owner-only; other staff must not see it.
        return is_owner(user, course)
    if course.pricing_mode == Course.PricingMode.FREE:
        return True
    if is_owner(user, course):
        return True
    if user is None or not getattr(user, "is_authenticated", False):
        return False
    return CourseAccessGrant.objects.filter(
        user=user, course=course, revoked_at__isnull=True
    ).exists()


def can_access_quiz(user, quiz):
    """Full access to a quiz, including its questions."""
    if quiz is None:
        return False
    if is_main_admin(user):
        return True
    if not quiz.is_published:
        return is_owner(user, quiz)
    if quiz.course_id is not None:
        return can_access_course(user, quiz.course)
    if quiz.series_id is not None:
        return bool(quiz.series.is_published)
    # A quiz attached to neither a course nor a series has no audience.
    return is_owner(user, quiz)


def can_read_media(user, course):
    """Media URLs are withheld unless the caller may consume the course."""
    return can_access_course(user, course)
