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

from django.core.exceptions import PermissionDenied

from accounts.models import Role
from .models import Course, CourseAccessGrant, Quiz

__all__ = [
    "role_of",
    "is_main_admin",
    "is_staff_role",
    "owner_of",
    "is_owner",
    "may_manage",
    "check_manage",
    "granted_course_ids",
    "is_enrolled",
    "can_access_course",
    "can_consume_course",
    "can_access_quiz",
    "can_read_media",
]

#: The foreign keys that lead from a resource to the user who owns it. A
#: question reaches its owner through ``quiz``; a choice through ``question``;
#: a PDF through ``folder``. Order matters only for objects that have more than
#: one parent (a lesson has both course and folder, and they agree).
PARENT_ATTRS = ("course", "series", "quiz", "question", "folder")

#: A cycle in the data would otherwise recurse forever. The real chains are at
#: most Choice -> Question -> Quiz -> Course, so four steps is generous.
MAX_OWNER_DEPTH = 5


def role_of(user):
    """Return the application role for ``user`` or ``None`` when anonymous.

    A Django superuser is a main admin even without a profile role, matching
    ``accounts.roles``. The two modules used to disagree: a superuser could get
    through ``IsSubAdminOrMainAdmin`` (which asks ``accounts.roles``) and then be
    refused by the ownership check here (which only read ``Profile.role``).

    Deliberately *not* ``is_staff``: sub-admins carry the Django staff flag for
    the admin site, so treating it as admin here would erase every tenant
    boundary this module exists to enforce.
    """
    if user is None or not getattr(user, "is_authenticated", False):
        return None
    if getattr(user, "is_superuser", False):
        return Role.MAIN_ADMIN
    profile = getattr(user, "profile", None)
    return profile.role if profile is not None else None


def is_main_admin(user):
    return role_of(user) == Role.MAIN_ADMIN


def is_staff_role(user):
    return role_of(user) in {Role.SUB_ADMIN, Role.MAIN_ADMIN}


def owner_of(obj, depth=0):
    """The user who owns ``obj``, following its parent chain.

    One function for every resource, because the chain differs per model and a
    hand-written copy per endpoint is how a tenant boundary develops holes: a
    choice is only "owned" through ``question -> quiz -> course|series``, and a
    check that stops at the first missing ``owner`` attribute says no to its
    own owner (and, worse, a check written the other way round says yes to
    everybody).
    """
    if obj is None or depth > MAX_OWNER_DEPTH:
        return None
    owner = getattr(obj, "owner", None)
    if owner is not None:
        return owner
    for attr in PARENT_ATTRS:
        parent = getattr(obj, attr, None)
        if parent is None:
            continue
        found = owner_of(parent, depth + 1)
        if found is not None:
            return found
    return None


def is_owner(user, obj):
    """True when ``user`` owns ``obj`` — directly or through its parents."""
    if user is None or not getattr(user, "is_authenticated", False):
        return False
    owner = owner_of(obj)
    return owner is not None and owner == user


def may_manage(user, obj):
    """May ``user`` write ``obj``: a main admin, or the tenant who owns it."""
    if obj is None:
        return False
    if is_main_admin(user):
        return True
    return is_owner(user, obj)


def check_manage(user, obj, message):
    """Refuse the write unless ``user`` may manage ``obj``.

    Raises Django's ``PermissionDenied``, which DRF renders as a 403 — the same
    answer the object permission gives, so a client sees one behaviour whether
    the refusal came from the URL or from a parent id in the body.
    """
    if not may_manage(user, obj):
        raise PermissionDenied(message)
    return obj


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


def is_enrolled(user, course):
    """True when ``user`` holds an active grant — i.e. joined the batch.

    Free batches are not auto-granted: a learner who never enrolled should not
    find the batch in "my batches", and its recordings should not open just
    because the price is zero. Enrolment is one POST (`/courses/{id}/enroll/`)
    for a free batch; a paid one needs an access code from staff.
    """
    if course is None or user is None:
        return False
    if not getattr(user, "is_authenticated", False):
        return False
    return CourseAccessGrant.objects.filter(
        user=user, course=course, revoked_at__isnull=True
    ).exists()


def can_consume_course(user, course):
    """May this caller open the recordings, notes and PDFs of ``course``?

    This is the enrolment gate, and it applies to free batches too. Staff keep
    their own content; a learner needs a grant.
    """
    if course is None:
        return False
    if is_main_admin(user):
        return True
    if not course.is_published:
        return is_owner(user, course)
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
    """Media URLs are withheld unless the caller joined the batch.

    Separate from ``can_access_course`` on purpose: a published free batch is
    still readable at catalogue level, and a free test stays attemptable
    without an account, but the recordings and PDFs need enrolment.
    """
    return can_consume_course(user, course)
