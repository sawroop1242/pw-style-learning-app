from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .views import (
    CustomTokenObtainPairView,
    CustomTokenRefreshView,
    AuthViewSet,
)

# JWT token endpoints
urlpatterns = [
    path("token/", CustomTokenObtainPairView.as_view(), name="token_obtain_pair"),
    path("token/refresh/", CustomTokenRefreshView.as_view(), name="token_refresh"),
]

# Auth endpoints (register, logout, me, change-password, forgot-password, verify-otp, resend-otp)
router = DefaultRouter()
router.register("auth", AuthViewSet, basename="auth")
urlpatterns += router.urls