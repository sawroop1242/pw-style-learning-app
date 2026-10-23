from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import AuthViewSet, CustomTokenObtainPairView, CustomTokenRefreshView

# JWT token endpoints
urlpatterns = [
    path("token/", CustomTokenObtainPairView.as_view(), name="token_obtain_pair"),
    path("token/refresh/", CustomTokenRefreshView.as_view(), name="token_refresh"),
]

# Auth endpoints (register, logout, me, change-password, forgot-password,
# verify-otp, resend-otp). DRF derives the route from the method name, which
# would expose `forgot_password`; the explicit `url_path` on each action keeps
# the public contract dashed.
router = DefaultRouter()
router.register("auth", AuthViewSet, basename="auth")
urlpatterns += router.urls

# Deprecated underscore aliases, kept so an older client does not break after
# the paths were normalised. Remove once nothing calls them.
#
# The decorator's `permission_classes`/`throttle_classes` are applied by the
# router as initkwargs; passing them again here keeps the alias guarded by the
# same authentication and throttling as the canonical route.
_ACTION_INITKWARGS = ("permission_classes", "throttle_classes", "authentication_classes")


def _legacy_view(action_name: str):
    action = getattr(AuthViewSet, action_name)
    initkwargs = {
        key: value for key, value in action.kwargs.items() if key in _ACTION_INITKWARGS
    }
    return AuthViewSet.as_view({"post": action_name}, **initkwargs)


urlpatterns += [
    path(
        "auth/forgot_password/",
        _legacy_view("forgot_password"),
        name="auth-forgot-password-legacy",
    ),
    path(
        "auth/verify_otp/",
        _legacy_view("verify_otp"),
        name="auth-verify-otp-legacy",
    ),
    path(
        "auth/resend_otp/",
        _legacy_view("resend_otp"),
        name="auth-resend-otp-legacy",
    ),
    path(
        "auth/change_password/",
        _legacy_view("change_password"),
        name="auth-change-password-legacy",
    ),
]
