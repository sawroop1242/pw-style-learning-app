"""Who may open the staff console, and who is a tenant owner.

The API has its own copy of these rules in ``courses.policy`` (where anonymous
callers are the normal case). These helpers answer the console's question,
which is slightly different: a Django superuser counts as an administrator even
without a profile role, because ``createsuperuser`` does not set one.
"""

from .models import Role

__all__ = ["user_role", "is_main_admin", "is_staff_role"]


def user_role(user):
    profile = getattr(user, "profile", None)
    return profile.role if profile else None


def is_main_admin(user) -> bool:
    if user is None or not getattr(user, "is_authenticated", False):
        return False
    return bool(user.is_superuser) or user_role(user) == Role.MAIN_ADMIN


def is_staff_role(user) -> bool:
    if user is None or not getattr(user, "is_authenticated", False):
        return False
    return bool(user.is_superuser) or user_role(user) in {Role.MAIN_ADMIN, Role.SUB_ADMIN}
