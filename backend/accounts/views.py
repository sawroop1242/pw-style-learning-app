import logging
import secrets
import hashlib
import hmac
from datetime import timedelta
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.mail import send_mail
from django.db import transaction
from django.utils import timezone
from rest_framework import status, permissions, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.throttling import AnonRateThrottle, UserRateThrottle
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from .models import PasswordResetOTP, Profile, AuditEvent
from .serializers import (
    CustomTokenObtainPairSerializer,
    UserRegistrationSerializer,
    UserProfileSerializer,
    ChangePasswordSerializer,
    ForgotPasswordSerializer,
    VerifyOTPSerializer,
)

User = get_user_model()
logger = logging.getLogger(__name__)


class RegistrationThrottle(AnonRateThrottle):
    rate = "5/minute"


class LoginThrottle(AnonRateThrottle):
    rate = "10/minute"


class ForgotPasswordThrottle(AnonRateThrottle):
    rate = "3/hour"


class OTPThrottle(AnonRateThrottle):
    rate = "10/minute"


class CustomTokenObtainPairView(TokenObtainPairView):
    """Login endpoint accepting username or email."""

    serializer_class = CustomTokenObtainPairSerializer
    throttle_classes = [LoginThrottle]

    def post(self, request, *args, **kwargs):
        response = super().post(request, *args, **kwargs)
        if response.status_code == 200:
            # Get user from serializer
            serializer = self.get_serializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            user = serializer.user
            if user:
                AuditEvent.objects.create(
                    actor=user,
                    action="user_login",
                    target_type="user",
                    target_id=str(user.id),
                    outcome="success",
                )
        return response


class CustomTokenRefreshView(TokenRefreshView):
    """Token refresh endpoint."""

    throttle_classes = [AnonRateThrottle]


class AuthViewSet(viewsets.GenericViewSet):
    """Authentication endpoints: register, logout, profile, change-password, forgot-password, verify-otp."""

    permission_classes = [permissions.AllowAny]

    def get_throttles(self):
        if self.action == "register":
            return [RegistrationThrottle()]
        if self.action == "forgot_password":
            return [ForgotPasswordThrottle()]
        if self.action == "verify_otp":
            return [OTPThrottle()]
        if self.action == "resend_otp":
            return [ForgotPasswordThrottle()]
        return super().get_throttles()

    @action(detail=False, methods=["post"], throttle_classes=[RegistrationThrottle])
    def register(self, request):
        """Register a new user."""
        serializer = UserRegistrationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()

        # Log audit event
        AuditEvent.objects.create(
            actor=user,
            action="user_registered",
            target_type="user",
            target_id=str(user.id),
            outcome="success",
        )

        return Response(
            {
                "message": "Registration successful.",
                "user": UserProfileSerializer(user).data,
            },
            status=status.HTTP_201_CREATED,
        )

    @action(detail=False, methods=["post"], permission_classes=[permissions.IsAuthenticated])
    def logout(self, request):
        """Logout - blacklist refresh token if blacklist app is configured."""
        try:
            refresh_token = request.data.get("refresh")
            if refresh_token:
                token = RefreshToken(refresh_token)
                token.blacklist()
        except Exception:
            # Token blacklist may not be configured; ignore errors
            pass

        AuditEvent.objects.create(
            actor=request.user,
            action="user_logout",
            target_type="user",
            target_id=str(request.user.id),
            outcome="success",
        )

        return Response({"message": "Logged out successfully."})

    @action(detail=False, methods=["get"], permission_classes=[permissions.IsAuthenticated])
    def me(self, request):
        """Get current user profile."""
        serializer = UserProfileSerializer(request.user)
        return Response(serializer.data)

    @action(
        detail=False, methods=["post"], permission_classes=[permissions.IsAuthenticated]
    )
    def change_password(self, request):
        """Change password for authenticated user."""
        serializer = ChangePasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user = request.user
        if not user.check_password(serializer.validated_data["current_password"]):
            return Response(
                {"current_password": "Current password is incorrect."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        user.set_password(serializer.validated_data["new_password"])
        user.save()

        # Invalidate all refresh tokens for this user
        try:
            from rest_framework_simplejwt.token_blacklist.models import OutstandingToken

            OutstandingToken.objects.filter(user=user).delete()
        except Exception:
            # Blacklist app not configured; log but continue
            pass

        AuditEvent.objects.create(
            actor=user,
            action="password_changed",
            target_type="user",
            target_id=str(user.id),
            outcome="success",
        )

        return Response({"message": "Password changed successfully."})

    def _generate_otp(self):
        """Generate a cryptographically secure 6-digit OTP."""
        return f"{secrets.randbelow(1000000):06d}"

    def _hash_otp(self, otp):
        """Create HMAC hash of OTP using Django SECRET_KEY as key."""
        key = settings.SECRET_KEY.encode()
        return hmac.new(key, otp.encode(), hashlib.sha256).hexdigest()

    def _send_otp_email(self, user, otp):
        """Send OTP email to user."""
        subject = "Your StudySpace Password Reset Code"
        message = (
            f"Hello {user.username},\n\n"
            f"Your password reset code is: {otp}\n\n"
            f"This code expires in 10 minutes and can only be used once.\n"
            f"Do not share this code with anyone.\n\n"
            f"If you did not request this, please ignore this email.\n\n"
            f"— StudySpace Team"
        )
        from_email = getattr(settings, "DEFAULT_FROM_EMAIL", None)
        send_mail(subject, message, from_email, [user.email], fail_silently=False)

    @action(detail=False, methods=["post"], throttle_classes=[ForgotPasswordThrottle])
    def forgot_password(self, request):
        """Request password reset OTP. Always returns generic response."""
        serializer = ForgotPasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        email = serializer.validated_data["email"]

        # Always return success to prevent account enumeration
        response_data = {
            "message": "If an account with that email exists, a password reset code has been sent."
        }

        # Find user (case-insensitive)
        try:
            user = User.objects.get(email__iexact=email)
        except User.DoesNotExist:
            # Log audit for non-existent account attempt (without revealing)
            AuditEvent.objects.create(
                action="password_reset_requested",
                target_type="user",
                target_id=email,
                outcome="success",  # Generic success to prevent enumeration
                metadata={"email_found": False},
            )
            return Response(response_data)

        # Invalidate any existing unconsumed OTPs for this user/purpose
        PasswordResetOTP.objects.filter(
            user=user, purpose=PasswordResetOTP.Purpose.PASSWORD_RESET, consumed_at__isnull=True
        ).update(consumed_at=timezone.now())

        # Generate new OTP
        otp = self._generate_otp()
        otp_hash = self._hash_otp(otp)

        # Create OTP record (configurable expiry and max attempts)
        expires_at = timezone.now() + timedelta(minutes=getattr(settings, "OTP_EXPIRY_MINUTES", 10))
        PasswordResetOTP.objects.create(
            user=user,
            purpose=PasswordResetOTP.Purpose.PASSWORD_RESET,
            otp_hash=otp_hash,
            expires_at=expires_at,
            max_attempts=getattr(settings, "OTP_MAX_ATTEMPTS", 5),
        )

        # Send email
        try:
            self._send_otp_email(user, otp)
            email_sent = True
        except Exception as e:
            logger.error(f"Failed to send password reset email to {user.email}: {e}")
            email_sent = False
            # Still return generic success to prevent enumeration

        AuditEvent.objects.create(
            actor=user,
            action="password_reset_requested",
            target_type="user",
            target_id=str(user.id),
            outcome="success" if email_sent else "email_failed",
            metadata={"email_sent": email_sent},
        )

        return Response(response_data)

    @action(detail=False, methods=["post"], throttle_classes=[OTPThrottle])
    def verify_otp(self, request):
        """Verify OTP and reset password atomically."""
        serializer = VerifyOTPSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        email = serializer.validated_data["email"]
        otp = serializer.validated_data["otp"]
        new_password = serializer.validated_data["new_password"]

        # Find user
        try:
            user = User.objects.get(email__iexact=email)
        except User.DoesNotExist:
            return Response(
                {"detail": "Invalid or expired reset code."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Find active OTP
        try:
            otp_record = PasswordResetOTP.objects.get(
                user=user,
                purpose=PasswordResetOTP.Purpose.PASSWORD_RESET,
                consumed_at__isnull=True,
            )
        except PasswordResetOTP.DoesNotExist:
            AuditEvent.objects.create(
                actor=user,
                action="password_reset_failed",
                target_type="user",
                target_id=str(user.id),
                outcome="failed",
                metadata={"reason": "no_active_otp"},
            )
            return Response(
                {"detail": "Invalid or expired reset code."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Check expiry
        if otp_record.is_expired:
            AuditEvent.objects.create(
                actor=user,
                action="password_reset_failed",
                target_type="user",
                target_id=str(user.id),
                outcome="failed",
                metadata={"reason": "expired"},
            )
            return Response(
                {"detail": "Reset code has expired. Please request a new one."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Check attempts
        if otp_record.attempts_used >= otp_record.max_attempts:
            AuditEvent.objects.create(
                actor=user,
                action="password_reset_failed",
                target_type="user",
                target_id=str(user.id),
                outcome="failed",
                metadata={"reason": "max_attempts_exceeded"},
            )
            return Response(
                {"detail": "Too many attempts. Please request a new reset code."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Verify OTP (constant-time comparison)
        otp_hash = self._hash_otp(otp)
        if not hmac.compare_digest(otp_record.otp_hash, otp_hash):
            otp_record.attempts_used += 1
            otp_record.save(update_fields=["attempts_used"])

            AuditEvent.objects.create(
                actor=user,
                action="password_reset_failed",
                target_type="user",
                target_id=str(user.id),
                outcome="failed",
                metadata={"reason": "invalid_otp", "attempts": otp_record.attempts_used},
            )
            return Response(
                {"detail": "Invalid reset code."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # OTP valid - consume and reset password atomically
        with transaction.atomic():
            otp_record.consumed_at = timezone.now()
            otp_record.save(update_fields=["consumed_at"])

            user.set_password(new_password)
            user.save()

            # Invalidate all refresh tokens
            try:
                from rest_framework_simplejwt.token_blacklist.models import OutstandingToken

                OutstandingToken.objects.filter(user=user).delete()
            except Exception:
                pass

        AuditEvent.objects.create(
            actor=user,
            action="password_reset_completed",
            target_type="user",
            target_id=str(user.id),
            outcome="success",
        )

        return Response({"message": "Password has been reset successfully."})

    @action(detail=False, methods=["post"], throttle_classes=[ForgotPasswordThrottle])
    def resend_otp(self, request):
        """Resend OTP for password reset."""
        # Same logic as forgot_password - reuse the endpoint
        return self.forgot_password(request)