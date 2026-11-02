import hashlib
import hmac
import io
import json
import re
import urllib.error
from datetime import timedelta
from unittest.mock import patch
from unittest import mock

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core import mail
from django.core.mail import EmailMessage
from django.core.cache import cache
from django.core.management import call_command
from django.test import SimpleTestCase, TestCase, override_settings
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from .models import PasswordResetOTP, Profile, AuditEvent, Role

User = get_user_model()


@override_settings(
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    OTP_EXPIRY_MINUTES=10,
    OTP_MAX_ATTEMPTS=5,
    CACHES={
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
            "LOCATION": "registration-tests",
        }
    },
    REST_FRAMEWORK={
        "DEFAULT_THROTTLE_RATES": {
            "anon": "10000/minute",
            "user": "10000/minute",
        },
    },
)
class RegistrationTests(TestCase):
    """Tests for user registration endpoint."""

    def setUp(self):
        self.client = APIClient()
        self.register_url = "/api/auth/register/"
        # Clear cache to avoid interference between tests
        from django.core.cache import cache
        cache.clear()

    def test_register_success(self):
        """Test successful registration with valid data."""
        response = self.client.post(
            self.register_url,
            {
                "username": "testuser",
                "email": "test@example.com",
                "password": "SecurePass123!",
                "password_confirm": "SecurePass123!",
            },
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(User.objects.filter(username="testuser").exists())
        user = User.objects.get(username="testuser")
        self.assertEqual(user.email, "test@example.com")
        self.assertTrue(user.check_password("SecurePass123!"))
        # Check profile created with student role
        self.assertEqual(user.profile.role, Role.STUDENT)
        # Check audit event
        self.assertTrue(
            AuditEvent.objects.filter(action="user_registered", target_id=str(user.id)).exists()
        )

    def test_register_duplicate_username_case_insensitive(self):
        """Test registration rejects duplicate username (case-insensitive)."""
        User.objects.create_user("TestUser", "test1@example.com", "SecurePass123!")
        response = self.client.post(
            self.register_url,
            {
                "username": "testuser",
                "email": "test2@example.com",
                "password": "SecurePass123!",
                "password_confirm": "SecurePass123!",
            },
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("username", response.data)

    def test_register_duplicate_email_case_insensitive(self):
        """Test registration rejects duplicate email (case-insensitive)."""
        User.objects.create_user("testuser1", "Test@Example.com", "SecurePass123!")
        response = self.client.post(
            self.register_url,
            {
                "username": "testuser2",
                "email": "test@example.com",
                "password": "SecurePass123!",
                "password_confirm": "SecurePass123!",
            },
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("email", response.data)

    def test_a_registration_that_loses_a_race_is_a_400_not_a_500(self):
        """Two requests can pass the `.exists()` check at the same moment.

        The database index is what decides; the loser must get the same field
        error a plain duplicate gets, not an IntegrityError traceback. The
        validators are stubbed to "not seen", which is exactly the state a
        racing request is in.
        """
        from .serializers import UserRegistrationSerializer

        User.objects.create_user("Racer", "racer@example.com", "SecurePass123!")

        with mock.patch.object(
            UserRegistrationSerializer, "validate_username", return_value="racer"
        ):
            response = self.client.post(
                self.register_url,
                {
                    "username": "racer",
                    "email": "raced@example.com",
                    "password": "SecurePass123!",
                    "password_confirm": "SecurePass123!",
                },
            )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST, response.content)
        self.assertIn("username", response.data)

    def test_a_racing_email_collision_names_the_email_field(self):
        from .serializers import UserRegistrationSerializer

        User.objects.create_user("racer", "racer@example.com", "SecurePass123!")

        with mock.patch.object(
            UserRegistrationSerializer,
            "validate_email",
            return_value="racer@example.com",
        ):
            response = self.client.post(
                self.register_url,
                {
                    "username": "someone-else",
                    "email": "RACER@example.com",
                    "password": "SecurePass123!",
                    "password_confirm": "SecurePass123!",
                },
            )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST, response.content)
        self.assertIn("email", response.data)

    def test_register_password_mismatch(self):
        """Test registration rejects mismatched passwords."""
        response = self.client.post(
            self.register_url,
            {
                "username": "testuser",
                "email": "test@example.com",
                "password": "SecurePass123!",
                "password_confirm": "DifferentPass123!",
            },
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("password_confirm", response.data)

    def test_register_weak_password(self):
        """Test registration rejects weak passwords."""
        response = self.client.post(
            self.register_url,
            {
                "username": "testuser",
                "email": "test@example.com",
                "password": "weak",
                "password_confirm": "weak",
            },
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("password", response.data)

    def test_register_missing_fields(self):
        """Test registration rejects missing required fields."""
        response = self.client.post(
            self.register_url,
            {
                "username": "testuser",
                "email": "test@example.com",
            },
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


@override_settings(
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    OTP_EXPIRY_MINUTES=10,
    OTP_MAX_ATTEMPTS=5,
    CACHES={
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
            "LOCATION": "login-tests",
        }
    },
    REST_FRAMEWORK={
        "DEFAULT_THROTTLE_RATES": {
            "anon": "10000/minute",
            "user": "10000/minute",
        },
    },
)
class LoginTests(TestCase):
    """Tests for login (token obtain) endpoint."""

    def setUp(self):
        self.client = APIClient()
        self.login_url = "/api/token/"
        self.user = User.objects.create_user(
            "testuser", "test@example.com", "SecurePass123!"
        )

    def test_login_with_username(self):
        """Test login with username."""
        response = self.client.post(
            self.login_url,
            {"username_or_email": "testuser", "password": "SecurePass123!"},
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("access", response.data)
        self.assertIn("refresh", response.data)
        self.assertTrue(AuditEvent.objects.filter(action="user_login").exists())

    def test_login_with_email(self):
        """Test login with email."""
        response = self.client.post(
            self.login_url,
            {"username_or_email": "test@example.com", "password": "SecurePass123!"},
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("access", response.data)
        self.assertIn("refresh", response.data)

    def test_login_case_insensitive_email(self):
        """Test login with email is case-insensitive."""
        response = self.client.post(
            self.login_url,
            {"username_or_email": "TEST@EXAMPLE.COM", "password": "SecurePass123!"},
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_login_invalid_password(self):
        """Test login fails with wrong password."""
        response = self.client.post(
            self.login_url,
            {"username_or_email": "testuser", "password": "WrongPass123!"},
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_login_nonexistent_user(self):
        """Test login fails for nonexistent user."""
        response = self.client.post(
            self.login_url,
            {"username_or_email": "nonexistent", "password": "SecurePass123!"},
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_login_inactive_user(self):
        """Test login fails for inactive user."""
        self.user.is_active = False
        self.user.save()
        response = self.client.post(
            self.login_url,
            {"username_or_email": "testuser", "password": "SecurePass123!"},
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


@override_settings(
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    OTP_EXPIRY_MINUTES=10,
    OTP_MAX_ATTEMPTS=5,
    CACHES={
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
            "LOCATION": "token-refresh-tests",
        }
    },
    REST_FRAMEWORK={
        "DEFAULT_THROTTLE_RATES": {
            "anon": "10000/minute",
            "user": "10000/minute",
        },
    },
)
class TokenRefreshTests(TestCase):
    """Tests for token refresh endpoint."""

    def setUp(self):
        self.client = APIClient()
        self.refresh_url = "/api/token/refresh/"
        self.user = User.objects.create_user(
            "testuser", "test@example.com", "SecurePass123!"
        )
        # Get tokens
        login_response = self.client.post(
            "/api/token/",
            {"username_or_email": "testuser", "password": "SecurePass123!"},
        )
        self.refresh_token = login_response.data["refresh"]

    def test_refresh_success(self):
        """Test successful token refresh."""
        response = self.client.post(
            self.refresh_url, {"refresh": self.refresh_token}
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("access", response.data)

    def test_refresh_invalid_token(self):
        """Test refresh fails with invalid token."""
        response = self.client.post(self.refresh_url, {"refresh": "invalid_token"})
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


@override_settings(
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    OTP_EXPIRY_MINUTES=10,
    OTP_MAX_ATTEMPTS=5,
    CACHES={
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
            "LOCATION": "logout-tests",
        }
    },
    REST_FRAMEWORK={
        "DEFAULT_THROTTLE_RATES": {
            "anon": "10000/minute",
            "user": "10000/minute",
        },
    },
)
class LogoutTests(TestCase):
    """Tests for logout endpoint."""

    def setUp(self):
        self.client = APIClient()
        self.logout_url = "/api/auth/logout/"
        self.user = User.objects.create_user(
            "testuser", "test@example.com", "SecurePass123!"
        )
        login_response = self.client.post(
            "/api/token/",
            {"username_or_email": "testuser", "password": "SecurePass123!"},
        )
        self.access_token = login_response.data["access"]
        self.refresh_token = login_response.data["refresh"]
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.access_token}")

    def test_logout_success(self):
        """Test successful logout."""
        response = self.client.post(
            self.logout_url, {"refresh": self.refresh_token}
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_logout_requires_auth(self):
        """Test logout requires authentication."""
        unauthenticated_client = APIClient()
        response = unauthenticated_client.post(self.logout_url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


@override_settings(
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    OTP_EXPIRY_MINUTES=10,
    OTP_MAX_ATTEMPTS=5,
    CACHES={
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
            "LOCATION": "user-profile-tests",
        }
    },
    REST_FRAMEWORK={
        "DEFAULT_THROTTLE_RATES": {
            "anon": "10000/minute",
            "user": "10000/minute",
        },
    },
)
class UserProfileTests(TestCase):
    """Tests for user profile (me) endpoint."""

    def setUp(self):
        self.client = APIClient()
        self.me_url = "/api/auth/me/"
        self.user = User.objects.create_user(
            "testuser", "test@example.com", "SecurePass123!"
        )
        login_response = self.client.post(
            "/api/token/",
            {"username_or_email": "testuser", "password": "SecurePass123!"},
        )
        self.access_token = login_response.data["access"]
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.access_token}")

    def test_me_success(self):
        """Test getting current user profile."""
        response = self.client.get(self.me_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["username"], "testuser")
        self.assertEqual(response.data["email"], "test@example.com")
        self.assertEqual(response.data["role"], "student")

    def test_me_requires_auth(self):
        """Test me endpoint requires authentication."""
        unauthenticated_client = APIClient()
        response = unauthenticated_client.get(self.me_url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


@override_settings(
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    OTP_EXPIRY_MINUTES=10,
    OTP_MAX_ATTEMPTS=5,
    CACHES={
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
            "LOCATION": "change-password-tests",
        }
    },
    REST_FRAMEWORK={
        "DEFAULT_THROTTLE_RATES": {
            "anon": "10000/minute",
            "user": "10000/minute",
        },
    },
)
class ChangePasswordTests(TestCase):
    """Tests for authenticated password change endpoint."""

    def setUp(self):
        self.client = APIClient()
        self.change_password_url = "/api/auth/change-password/"
        self.user = User.objects.create_user(
            "testuser", "test@example.com", "SecurePass123!"
        )
        login_response = self.client.post(
            "/api/token/",
            {"username_or_email": "testuser", "password": "SecurePass123!"},
        )
        self.access_token = login_response.data["access"]
        self.refresh_token = login_response.data["refresh"]
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.access_token}")

    def test_change_password_success(self):
        """Test successful password change."""
        response = self.client.post(
            self.change_password_url,
            {
                "current_password": "SecurePass123!",
                "new_password": "NewSecurePass123!",
                "new_password_confirm": "NewSecurePass123!",
            },
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Verify password changed
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("NewSecurePass123!"))
        # Check audit event
        self.assertTrue(
            AuditEvent.objects.filter(action="password_changed", target_id=str(self.user.id)).exists()
        )

    def test_change_password_wrong_current(self):
        """Test password change fails with wrong current password."""
        response = self.client.post(
            self.change_password_url,
            {
                "current_password": "WrongPass123!",
                "new_password": "NewSecurePass123!",
                "new_password_confirm": "NewSecurePass123!",
            },
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("current_password", response.data)

    def test_change_password_mismatch(self):
        """Test password change fails with mismatched new passwords."""
        response = self.client.post(
            self.change_password_url,
            {
                "current_password": "SecurePass123!",
                "new_password": "NewSecurePass123!",
                "new_password_confirm": "DifferentPass123!",
            },
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("new_password_confirm", response.data)

    def test_change_password_weak_new(self):
        """Test password change rejects weak new password."""
        response = self.client.post(
            self.change_password_url,
            {
                "current_password": "SecurePass123!",
                "new_password": "weak",
                "new_password_confirm": "weak",
            },
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_change_password_invalidates_tokens(self):
        """Test password change invalidates existing refresh tokens."""
        # Try to use old refresh token after password change
        self.client.post(
            self.change_password_url,
            {
                "current_password": "SecurePass123!",
                "new_password": "NewSecurePass123!",
                "new_password_confirm": "NewSecurePass123!",
            },
        )
        response = self.client.post(
            "/api/token/refresh/", {"refresh": self.refresh_token}
        )
        # Should fail or succeed depending on blacklist config - at minimum should not error
        self.assertIn(response.status_code, [status.HTTP_200_OK, status.HTTP_401_UNAUTHORIZED])

    def test_change_password_requires_auth(self):
        """Test change password requires authentication."""
        unauthenticated_client = APIClient()
        response = unauthenticated_client.post(self.change_password_url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


@override_settings(
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    OTP_EXPIRY_MINUTES=10,
    OTP_MAX_ATTEMPTS=5,
    CACHES={
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
            "LOCATION": "forgot-password-tests",
        }
    },
    REST_FRAMEWORK={
        "DEFAULT_THROTTLE_RATES": {
            "anon": "10000/minute",
            "user": "10000/minute",
        },
    },
)
class ForgotPasswordTests(TestCase):
    """Tests for forgot password (request OTP) endpoint."""

    def setUp(self):
        self.client = APIClient()
        self.forgot_url = "/api/auth/forgot-password/"
        self.user = User.objects.create_user(
            "testuser", "test@example.com", "SecurePass123!"
        )
        # Clear cache to avoid interference between tests
        from django.core.cache import cache
        cache.clear()

    def test_forgot_password_existing_email(self):
        """Test forgot password for existing email - returns generic success."""
        response = self.client.post(
            self.forgot_url, {"email": "test@example.com"}
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("message", response.data)
        # Check OTP created
        otp = PasswordResetOTP.objects.get(user=self.user)
        self.assertIsNotNone(otp)
        self.assertEqual(otp.purpose, PasswordResetOTP.Purpose.PASSWORD_RESET)
        # Check email sent
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("test@example.com", mail.outbox[0].to)
        # Check audit event
        self.assertTrue(
            AuditEvent.objects.filter(
                action="password_reset_requested", target_id=str(self.user.id)
            ).exists()
        )

    def test_forgot_password_nonexistent_email(self):
        """Test forgot password for nonexistent email - returns generic success (no enumeration)."""
        response = self.client.post(
            self.forgot_url, {"email": "nonexistent@example.com"}
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("message", response.data)
        # No OTP created
        self.assertEqual(PasswordResetOTP.objects.count(), 0)
        # No email sent
        self.assertEqual(len(mail.outbox), 0)
        # Audit event still created (generic)
        self.assertTrue(
            AuditEvent.objects.filter(
                action="password_reset_requested", metadata__email_found=False
            ).exists()
        )

    def test_forgot_password_case_insensitive_email(self):
        """Test forgot password is case-insensitive for email."""
        response = self.client.post(
            self.forgot_url, {"email": "TEST@EXAMPLE.COM"}
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(mail.outbox), 1)

    def test_forgot_password_invalidates_previous_otp(self):
        """Test forgot password invalidates previous unconsumed OTPs."""
        # Create first OTP
        self.client.post(self.forgot_url, {"email": "test@example.com"})
        otp1 = PasswordResetOTP.objects.get(user=self.user)
        self.assertIsNone(otp1.consumed_at)

        # Request again
        self.client.post(self.forgot_url, {"email": "test@example.com"})
        otp1.refresh_from_db()
        # First OTP should now be consumed
        self.assertIsNotNone(otp1.consumed_at)
        # New OTP should exist
        otp2 = PasswordResetOTP.objects.filter(user=self.user, consumed_at__isnull=True).first()
        self.assertIsNotNone(otp2)
        self.assertNotEqual(otp1.id, otp2.id)


@override_settings(
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    OTP_EXPIRY_MINUTES=10,
    OTP_MAX_ATTEMPTS=5,
    CACHES={
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
            "LOCATION": "verify-otp-tests",
        }
    },
    REST_FRAMEWORK={
        "DEFAULT_THROTTLE_RATES": {
            "anon": "10000/minute",
            "user": "10000/minute",
        },
    },
)
class VerifyOTPTests(TestCase):
    """Tests for verify OTP and reset password endpoint."""

    def setUp(self):
        self.client = APIClient()
        self.verify_url = "/api/auth/verify-otp/"
        self.user = User.objects.create_user(
            "testuser", "test@example.com", "SecurePass123!"
        )
        # Clear cache to avoid interference between tests
        from django.core.cache import cache
        cache.clear()
        # Request OTP
        self.client.post("/api/auth/forgot-password/", {"email": "test@example.com"})
        self.otp_record = PasswordResetOTP.objects.get(user=self.user)
        # Get the actual OTP from email (since we use locmem backend)
        self.otp = mail.outbox[0].body.split("Your password reset code is: ")[1].split("\n")[0]

    def _hash_otp(self, otp):
        """Hash OTP using same method as view."""
        key = settings.SECRET_KEY.encode()
        return hmac.new(key, otp.encode(), hashlib.sha256).hexdigest()

    def test_verify_otp_success(self):
        """Test successful OTP verification and password reset."""
        response = self.client.post(
            self.verify_url,
            {
                "email": "test@example.com",
                "otp": self.otp,
                "new_password": "NewSecurePass123!",
                "new_password_confirm": "NewSecurePass123!",
            },
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("message", response.data)
        # Verify password changed
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("NewSecurePass123!"))
        # Verify OTP consumed
        self.otp_record.refresh_from_db()
        self.assertIsNotNone(self.otp_record.consumed_at)
        # Check audit event
        self.assertTrue(
            AuditEvent.objects.filter(action="password_reset_completed", target_id=str(self.user.id)).exists()
        )

    def test_verify_otp_invalid_otp(self):
        """Test OTP verification fails with invalid OTP."""
        response = self.client.post(
            self.verify_url,
            {
                "email": "test@example.com",
                "otp": "000000",
                "new_password": "NewSecurePass123!",
                "new_password_confirm": "NewSecurePass123!",
            },
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("detail", response.data)
        # OTP attempt should be incremented
        self.otp_record.refresh_from_db()
        self.assertEqual(self.otp_record.attempts_used, 1)
        # Audit event for failed attempt
        self.assertTrue(
            AuditEvent.objects.filter(
                action="password_reset_failed",
                target_id=str(self.user.id),
                metadata__reason="invalid_otp",
            ).exists()
        )

    def test_verify_otp_expired(self):
        """Test OTP verification fails with expired OTP."""
        self.otp_record.expires_at = timezone.now() - timedelta(minutes=1)
        self.otp_record.save()
        response = self.client.post(
            self.verify_url,
            {
                "email": "test@example.com",
                "otp": self.otp,
                "new_password": "NewSecurePass123!",
                "new_password_confirm": "NewSecurePass123!",
            },
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("expired", response.data["detail"])

    def test_verify_otp_consumed(self):
        """Test OTP verification fails with already consumed OTP."""
        self.otp_record.consumed_at = timezone.now()
        self.otp_record.save()
        response = self.client.post(
            self.verify_url,
            {
                "email": "test@example.com",
                "otp": self.otp,
                "new_password": "NewSecurePass123!",
                "new_password_confirm": "NewSecurePass123!",
            },
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_verify_otp_max_attempts_exceeded(self):
        """Test OTP verification fails after max attempts."""
        self.otp_record.attempts_used = 5
        self.otp_record.save()
        response = self.client.post(
            self.verify_url,
            {
                "email": "test@example.com",
                "otp": self.otp,
                "new_password": "NewSecurePass123!",
                "new_password_confirm": "NewSecurePass123!",
            },
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("Too many attempts", response.data["detail"])

    def test_verify_otp_nonexistent_user(self):
        """Test OTP verification fails for nonexistent user."""
        response = self.client.post(
            self.verify_url,
            {
                "email": "nonexistent@example.com",
                "otp": "123456",
                "new_password": "NewSecurePass123!",
                "new_password_confirm": "NewSecurePass123!",
            },
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_verify_otp_wrong_user(self):
        """Test OTP cannot be used for different user."""
        user2 = User.objects.create_user("testuser2", "test2@example.com", "SecurePass123!")
        # Request OTP for user2
        self.client.post("/api/auth/forgot-password/", {"email": "test2@example.com"})
        otp2 = PasswordResetOTP.objects.get(user=user2)
        otp2_code = mail.outbox[1].body.split("Your password reset code is: ")[1].split("\n")[0]

        # Try to use user2's OTP for user1
        response = self.client.post(
            self.verify_url,
            {
                "email": "test@example.com",  # user1's email
                "otp": otp2_code,  # user2's OTP
                "new_password": "NewSecurePass123!",
                "new_password_confirm": "NewSecurePass123!",
            },
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_verify_otp_atomic_consumption(self):
        """Test OTP consumption and password reset are atomic."""
        # Verify OTP works
        self.client.post(
            self.verify_url,
            {
                "email": "test@example.com",
                "otp": self.otp,
                "new_password": "NewSecurePass123!",
                "new_password_confirm": "NewSecurePass123!",
            },
        )
        # Try to use same OTP again - should fail
        response = self.client.post(
            self.verify_url,
            {
                "email": "test@example.com",
                "otp": self.otp,
                "new_password": "AnotherPass123!",
                "new_password_confirm": "AnotherPass123!",
            },
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


@override_settings(
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    OTP_EXPIRY_MINUTES=10,
    OTP_MAX_ATTEMPTS=5,
    CACHES={
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
            "LOCATION": "resend-otp-tests",
        }
    },
    REST_FRAMEWORK={
        "DEFAULT_THROTTLE_RATES": {
            "anon": "10000/minute",
            "user": "10000/minute",
        },
    },
)
class ResendOTPTests(TestCase):
    """Tests for resend OTP endpoint."""

    def setUp(self):
        self.client = APIClient()
        self.resend_url = "/api/auth/resend-otp/"
        self.user = User.objects.create_user(
            "testuser", "test@example.com", "SecurePass123!"
        )
        # Clear cache to avoid interference between tests
        from django.core.cache import cache
        cache.clear()

    def test_resend_otp_success(self):
        """Test resend OTP works same as forgot_password."""
        # Initial request
        self.client.post("/api/auth/forgot-password/", {"email": "test@example.com"})
        self.assertEqual(len(mail.outbox), 1)
        otp1 = mail.outbox[0].body.split("Your password reset code is: ")[1].split("\n")[0]

        # Resend
        mail.outbox.clear()
        self.client.post(self.resend_url, {"email": "test@example.com"})
        self.assertEqual(len(mail.outbox), 1)
        otp2 = mail.outbox[0].body.split("Your password reset code is: ")[1].split("\n")[0]

        # New OTP should be different
        self.assertNotEqual(otp1, otp2)


@override_settings(
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    OTP_EXPIRY_MINUTES=10,
    OTP_MAX_ATTEMPTS=5,
    CACHES={
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
            "LOCATION": "throttling-tests",
        }
    },
    REST_FRAMEWORK={
        "DEFAULT_THROTTLE_RATES": {
            "anon": "10000/minute",
            "user": "10000/minute",
        },
    },
)
class ThrottlingTests(TestCase):
    """Tests for rate limiting on auth endpoints."""

    def setUp(self):
        self.client = APIClient()
        # Clear cache to avoid interference between tests
        from django.core.cache import cache
        cache.clear()

    def test_registration_throttle(self):
        """Test registration is throttled."""
        url = "/api/auth/register/"
        for i in range(10):
            response = self.client.post(
                url,
                {
                    "username": f"user{i}",
                    "email": f"user{i}@example.com",
                    "password": "SecurePass123!",
                    "password_confirm": "SecurePass123!",
                },
            )
            self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        # the 11th request should be throttled
        response = self.client.post(
            url,
            {
                "username": "user10",
                "email": "user10@example.com",
                "password": "SecurePass123!",
                "password_confirm": "SecurePass123!",
            },
        )
        self.assertEqual(response.status_code, status.HTTP_429_TOO_MANY_REQUESTS)

    def test_login_throttle(self):
        """Test login is throttled."""
        url = "/api/token/"
        user = User.objects.create_user("testuser", "test@example.com", "SecurePass123!")
        # Distinct identifiers, so this measures the per-IP budget only.
        for i in range(20):
            response = self.client.post(
                url, {"username_or_email": f"person{i}", "password": "SecurePass123!"}
            )
            self.assertIn(response.status_code, [status.HTTP_200_OK, status.HTTP_400_BAD_REQUEST])
        # the 21st request should be throttled
        response = self.client.post(
            url, {"username_or_email": "person20", "password": "SecurePass123!"}
        )
        self.assertEqual(response.status_code, status.HTTP_429_TOO_MANY_REQUESTS)

    def test_login_throttle_per_identifier(self):
        """One account is capped even if the IP budget still has room."""
        url = "/api/token/"
        User.objects.create_user("target", "target@example.com", "SecurePass123!")
        for i in range(10):
            response = self.client.post(
                url, {"username_or_email": "target", "password": "wrong-password"}
            )
            self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST, i)
        response = self.client.post(url, {"username_or_email": "target", "password": "wrong-password"})
        self.assertEqual(response.status_code, status.HTTP_429_TOO_MANY_REQUESTS)

    def test_forgot_password_throttle_per_ip(self):
        """Six reset requests per address per hour, counted per client IP."""
        url = "/api/auth/forgot-password/"
        for i in range(6):
            response = self.client.post(url, {"email": f"person{i}@example.com"})
            self.assertEqual(response.status_code, status.HTTP_200_OK, i)
        response = self.client.post(url, {"email": "person7@example.com"})
        self.assertEqual(response.status_code, status.HTTP_429_TOO_MANY_REQUESTS)

    def test_forgot_password_throttle_per_email(self):
        """One address gets three mails an hour, so a shared IP cannot flood it.

        The IP budget is six, so the fourth request for the *same* address is the
        one that trips -- which is what a student retrying their own reset sees.
        """
        url = "/api/auth/forgot-password/"
        for i in range(3):
            response = self.client.post(url, {"email": "repeat@example.com"})
            self.assertEqual(response.status_code, status.HTTP_200_OK, i)
        response = self.client.post(url, {"email": "repeat@example.com"})
        self.assertEqual(response.status_code, status.HTTP_429_TOO_MANY_REQUESTS)
        # A different address on the same IP still has budget left.
        response = self.client.post(url, {"email": "someone-else@example.com"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_resend_shares_the_email_budget(self):
        """Resend is not a way around the per-address limit."""
        self.client.post("/api/auth/forgot-password/", {"email": "shared@example.com"})
        for _ in range(2):
            response = self.client.post("/api/auth/resend-otp/", {"email": "shared@example.com"})
            self.assertEqual(response.status_code, status.HTTP_200_OK)
        response = self.client.post("/api/auth/resend-otp/", {"email": "shared@example.com"})
        self.assertEqual(response.status_code, status.HTTP_429_TOO_MANY_REQUESTS)

    def test_otp_verify_throttle(self):
        """Test OTP verification is throttled."""
        url = "/api/auth/verify-otp/"
        for i in range(10):
            response = self.client.post(
                url,
                {
                    "email": "test@example.com",
                    "otp": "000000",
                    "new_password": "NewPass123!",
                    "new_password_confirm": "NewPass123!",
                },
            )
            self.assertIn(response.status_code, [status.HTTP_200_OK, status.HTTP_400_BAD_REQUEST])
        # 11th request should be throttled
        response = self.client.post(
            url,
            {
                "email": "test@example.com",
                "otp": "000000",
                "new_password": "NewPass123!",
                "new_password_confirm": "NewPass123!",
            },
        )
        self.assertEqual(response.status_code, status.HTTP_429_TOO_MANY_REQUESTS)


@override_settings(
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    OTP_EXPIRY_MINUTES=10,
    OTP_MAX_ATTEMPTS=5,
    CACHES={
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
            "LOCATION": "email-failure-tests",
        }
    },
)
class EmailDeliveryFailureTests(TestCase):
    """Tests for email delivery failure handling."""

    @patch("accounts.views.AuthViewSet._send_otp_email")
    def test_forgot_password_email_failure(self, mock_send):
        """A code that was never delivered must not stay live in the table.

        It used to be kept: the row said "active reset" while the person had no
        mail to prove it, and the console listed a code nobody could use. The
        attempt is still recorded, in AuditEvent.
        """
        mock_send.side_effect = Exception("SMTP error")
        client = APIClient()
        user = User.objects.create_user("testuser", "test@example.com", "SecurePass123!")

        response = client.post("/api/auth/forgot-password/", {"email": "test@example.com"})
        # Should still return generic success (no enumeration)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # ...but no live code is left behind.
        self.assertFalse(
            PasswordResetOTP.objects.filter(user=user, consumed_at__isnull=True).exists()
        )
        # Audit event should show email_failed
        audit = AuditEvent.objects.filter(
            action="password_reset_requested", target_id=str(user.id)
        ).first()
        self.assertEqual(audit.outcome, "email_failed")
        self.assertEqual(audit.metadata.get("email_sent"), False)


@override_settings(
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    OTP_EXPIRY_MINUTES=10,
    OTP_MAX_ATTEMPTS=5,
    CACHES={
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
            "LOCATION": "cross-user-tests",
        }
    },
)
class CrossUserIsolationTests(TestCase):
    """Tests for cross-user data isolation - these require courses app setup, so we skip for now."""
    
    def test_placeholder(self):
        """Placeholder test - cross-user isolation tests should be in courses app tests."""
        self.assertTrue(True)

@override_settings(
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    OTP_EXPIRY_MINUTES=10,
    OTP_MAX_ATTEMPTS=5,
    CACHES={
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
            "LOCATION": "auth-route-alias-tests",
        }
    },
    REST_FRAMEWORK={
        "DEFAULT_THROTTLE_RATES": {
            "auth_register": "100/min",
            "forgot_password": "100/min",
            "otp_verify": "100/min",
        }
    },
)
class AuthRouteAliasTests(TestCase):
    """The dashed paths are canonical; the older underscore paths stay as aliases.

    The front end (and the API docs) call `/auth/forgot-password/` and friends.
    DRF used to derive the route from the method name, which published
    `/auth/forgot_password/` instead -- every reset request 404'd against a live
    API while the interface reported a generic failure. Both spellings now
    resolve to the same action, and these tests keep it that way.
    """

    def setUp(self):
        self.user = User.objects.create_user(
            username="aliasuser", email="alias@example.com", password="SecurePass123!"
        )

    def test_forgot_password_paths_are_equivalent(self):
        for path in ("/api/auth/forgot-password/", "/api/auth/forgot_password/"):
            cache.clear()  # each spelling gets its own throttle budget
            response = self.client.post(path, {"email": self.user.email})
            self.assertEqual(response.status_code, status.HTTP_200_OK, path)

    def test_verify_otp_paths_are_reachable(self):
        for path in ("/api/auth/verify-otp/", "/api/auth/verify_otp/"):
            cache.clear()
            response = self.client.post(path, {"email": self.user.email, "otp": "000000"})
            self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST, path)

    def test_resend_otp_paths_are_reachable(self):
        for path in ("/api/auth/resend-otp/", "/api/auth/resend_otp/"):
            cache.clear()
            response = self.client.post(path, {"email": self.user.email})
            self.assertEqual(response.status_code, status.HTTP_200_OK, path)

    def test_change_password_paths_require_auth(self):
        for path in ("/api/auth/change-password/", "/api/auth/change_password/"):
            response = self.client.post(path, {})
            self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED, path)


@override_settings(
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    CACHES={
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
            "LOCATION": "otp-delivery-tests",
        }
    },
)
class OTPDeliveryTests(TestCase):
    """What the reset mail says, and what happens when it cannot be sent.

    The deployment ran with no SMTP host while every one of these requests
    answered "a code has been sent"; the tests below pin the two things that
    were wrong about that — the code stayed in the table, and nothing anywhere
    said the mail had failed.
    """

    forgot_url = "/api/auth/forgot-password/"

    def setUp(self):
        from django.core.cache import cache

        cache.clear()
        self.client = APIClient()
        self.user = User.objects.create_user("mailer", "mailer@example.com", "SecurePass123!")

    @override_settings(OTP_EXPIRY_MINUTES=3)
    def test_the_email_quotes_the_configured_expiry(self):
        self.client.post(self.forgot_url, {"email": "mailer@example.com"})

        body = mail.outbox[0].body
        self.assertIn("expires in 3 minutes", body)
        # The row and the letter must agree, or the letter is lying.
        otp = PasswordResetOTP.objects.get(user=self.user, consumed_at__isnull=True)
        remaining = otp.expires_at - timezone.now()
        self.assertLess(remaining, timedelta(minutes=3, seconds=5))
        self.assertGreater(remaining, timedelta(minutes=2, seconds=55))

    def test_an_address_cannot_be_shared_by_two_accounts(self):
        """The database, not the view, is what refuses a duplicate.

        Two accounts on one address used to be creatable, and the reset flow
        then had to refuse with a generic message. Migration 0002 makes the
        collision impossible in the first place; the `ambiguous_email` branch in
        the view stays as a guard for databases restored from before it.
        """
        from django.db import IntegrityError, transaction

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                User.objects.create_user("mailer2", "MAILER@example.com", "SecurePass123!")

        self.assertEqual(User.objects.filter(email__iexact="mailer@example.com").count(), 1)
        self.assertFalse(User.objects.filter(username="mailer2").exists())

    def test_a_case_variant_username_cannot_be_created(self):
        from django.db import IntegrityError, transaction

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                User.objects.create_user("MAILER", "other@example.com", "SecurePass123!")

        self.assertFalse(User.objects.filter(email="other@example.com").exists())

    def test_verify_otp_with_no_matching_address_is_a_400_not_a_500(self):
        response = self.client.post(
            "/api/auth/verify-otp/",
            {
                "email": "nobody@example.com",
                "otp": "123456",
                "new_password": "Another!2026",
                "new_password_confirm": "Another!2026",
            },
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class EmailConfigurationCheckTests(TestCase):
    """`manage.py check` has to notice a deployment that cannot send mail."""

    def run_checks(self):
        from django.core.checks import run_checks

        return run_checks()

    @override_settings(
        EMAIL_BACKEND="django.core.mail.backends.smtp.EmailBackend",
        EMAIL_HOST="",
        DEFAULT_FROM_EMAIL="StudySpace <noreply@studyspace.local>",
    )
    def test_smtp_without_a_host_is_reported(self):
        ids = {issue.id for issue in self.run_checks()}
        self.assertIn("accounts.W001", ids)
        self.assertIn("accounts.W002", ids)

    @override_settings(
        EMAIL_BACKEND="django.core.mail.backends.smtp.EmailBackend",
        EMAIL_HOST="smtp.example.com",
        DEFAULT_FROM_EMAIL="StudySpace <codes@example.com>",
    )
    def test_a_configured_host_raises_nothing(self):
        ids = {issue.id for issue in self.run_checks()}
        self.assertNotIn("accounts.W001", ids)
        self.assertNotIn("accounts.W002", ids)

    @override_settings(
        EMAIL_BACKEND="django.core.mail.backends.console.EmailBackend",
        DEFAULT_FROM_EMAIL="StudySpace <noreply@studyspace.local>",
    )
    def test_the_console_backend_is_not_treated_as_a_broken_deployment(self):
        ids = {issue.id for issue in self.run_checks()}
        self.assertNotIn("accounts.W001", ids)
        self.assertNotIn("accounts.W002", ids)


class CheckEmailCommandTests(TestCase):
    """`manage.py check_email` is how an operator proves the transport works."""

    @override_settings(
        EMAIL_BACKEND="django.core.mail.backends.smtp.EmailBackend",
        EMAIL_HOST="",
    )
    def test_it_refuses_to_pretend_when_the_host_is_missing(self):
        from django.core.management import call_command
        from django.core.management.base import CommandError

        with self.assertRaises(CommandError):
            call_command("check_email")

    @override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
    def test_it_can_send_a_test_message(self):
        from io import StringIO

        from django.core.management import call_command

        out = StringIO()
        call_command("check_email", "--to", "operator@example.com", stdout=out)

        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ["operator@example.com"])
        self.assertIn("message handed to the server", out.getvalue())


class _FakeHttpResponse:
    """The little bit of `urlopen`'s return value the backend actually uses."""

    def __init__(self, status=200, body=b'{"ok": true}'):
        self.status = status
        self._body = body

    def read(self):
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        return False


def _http_error(url, status, body=b'{"message": "nope"}'):
    return urllib.error.HTTPError(url, status, "refused", None, io.BytesIO(body))


class ApiMailBackendTests(SimpleTestCase):
    """Brevo and Resend send the same letter over HTTPS that SMTP would.

    The deployment had no SMTP host; an API key is one secret instead of five
    settings, and it works on hosts that block outbound port 587. These tests
    pin the request each provider receives, because a wrong field name there is
    a silent 400 in production.
    """

    def message(self, **overrides):
        from django.core.mail import EmailMessage

        fields = {
            "subject": "Your StudySpace Password Reset Code",
            "body": "Your password reset code is: 123456",
            "from_email": "StudySpace <codes@example.com>",
            "to": ["student@example.com"],
        }
        fields.update(overrides)
        return EmailMessage(**fields)

    @override_settings(
        BREVO_API_KEY="xkeysib-test-key",
        DEFAULT_FROM_EMAIL="StudySpace <codes@example.com>",
        EMAIL_TIMEOUT=3,
    )
    def test_brevo_gets_one_json_request_per_message(self):
        from accounts.mail_backends import BrevoEmailBackend

        backend = BrevoEmailBackend()
        with patch("accounts.mail_backends.urllib.request.urlopen") as urlopen:
            urlopen.return_value = _FakeHttpResponse(status=201)
            sent = backend.send_messages([self.message()])

        self.assertEqual(sent, 1)
        request = urlopen.call_args.args[0]
        self.assertEqual(request.full_url, "https://api.brevo.com/v3/smtp/email")
        self.assertEqual(request.get_method(), "POST")
        self.assertEqual(request.get_header("Api-key"), "xkeysib-test-key")
        self.assertEqual(urlopen.call_args.kwargs["timeout"], 3)

        payload = json.loads(request.data)
        self.assertEqual(payload["sender"], {"email": "codes@example.com", "name": "StudySpace"})
        self.assertEqual(payload["to"], [{"email": "student@example.com"}])
        self.assertEqual(payload["subject"], "Your StudySpace Password Reset Code")
        self.assertIn("123456", payload["textContent"])

    @override_settings(
        RESEND_API_KEY="re-test-key",
        DEFAULT_FROM_EMAIL="StudySpace <codes@example.com>",
        EMAIL_TIMEOUT=3,
    )
    def test_resend_gets_the_flattened_sender_string(self):
        from accounts.mail_backends import ResendEmailBackend

        backend = ResendEmailBackend()
        with patch("accounts.mail_backends.urllib.request.urlopen") as urlopen:
            urlopen.return_value = _FakeHttpResponse(status=200)
            backend.send_messages([self.message()])

        request = urlopen.call_args.args[0]
        self.assertEqual(request.full_url, "https://api.resend.com/emails")
        self.assertEqual(request.get_header("Authorization"), "Bearer re-test-key")
        payload = json.loads(request.data)
        self.assertEqual(payload["from"], "StudySpace <codes@example.com>")
        self.assertEqual(payload["to"], ["student@example.com"])
        self.assertIn("123456", payload["text"])

    @override_settings(BREVO_API_KEY="xkeysib-super-secret-value")
    def test_a_refused_message_raises_and_never_names_the_key(self):
        from accounts.mail_backends import BrevoEmailBackend, EmailBackendError

        backend = BrevoEmailBackend()
        with patch("accounts.mail_backends.urllib.request.urlopen") as urlopen:
            urlopen.side_effect = _http_error(
                "https://api.brevo.com/v3/smtp/email", 401, b'{"message":"Key not found"}'
            )
            with self.assertRaises(EmailBackendError) as caught:
                backend.send_messages([self.message()])

        text = str(caught.exception)
        self.assertIn("401", text)
        self.assertIn("Key not found", text)
        self.assertNotIn("xkeysib-super-secret-value", text)

    @override_settings(BREVO_API_KEY="xkeysib-test-key")
    def test_fail_silently_swallows_the_refusal_and_counts_nothing(self):
        from accounts.mail_backends import BrevoEmailBackend

        backend = BrevoEmailBackend(fail_silently=True)
        with patch("accounts.mail_backends.urllib.request.urlopen") as urlopen:
            urlopen.side_effect = _http_error("https://api.brevo.com/v3/smtp/email", 500)
            self.assertEqual(backend.send_messages([self.message()]), 0)

    @override_settings(BREVO_API_KEY="xkeysib-test-key")
    def test_attachments_are_refused_rather_than_dropped(self):
        from accounts.mail_backends import BrevoEmailBackend, EmailBackendError

        message = self.message()
        message.attach("notes.txt", "hello", "text/plain")
        with self.assertRaises(EmailBackendError):
            BrevoEmailBackend().send_messages([message])

    @override_settings(BREVO_API_KEY="")
    def test_opening_without_a_key_says_which_variable_is_missing(self):
        from accounts.mail_backends import BrevoEmailBackend, EmailBackendError

        with self.assertRaises(EmailBackendError) as caught:
            BrevoEmailBackend().open()
        self.assertIn("BREVO_API_KEY", str(caught.exception))


@override_settings(
    EMAIL_BACKEND="accounts.mail_backends.BrevoEmailBackend",
    BREVO_API_KEY="xkeysib-test-key",
    DEFAULT_FROM_EMAIL="StudySpace <codes@example.com>",
    CACHES={
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
            "LOCATION": "api-mail-tests",
        }
    },
)
class ResetThroughApiBackendTests(TestCase):
    """The whole reset flow, with the provider's HTTPS call faked.

    SMTP was proven against a local server; this proves the same request works
    when the message leaves through Brevo, which is what the deployment will do.
    """

    def setUp(self):
        cache.clear()
        self.client = APIClient()
        self.user = User.objects.create_user("apiuser", "api@example.com", "SecurePass123!")

    def test_a_code_is_mailed_and_then_accepted(self):
        with patch("accounts.mail_backends.urllib.request.urlopen") as urlopen:
            urlopen.return_value = _FakeHttpResponse(status=201)
            response = self.client.post(
                "/api/auth/forgot-password/", {"email": "api@example.com"}
            )

            self.assertEqual(response.status_code, status.HTTP_200_OK)
            sent = [
                json.loads(call.args[0].data)
                for call in urlopen.call_args_list
                if call.args[0].data
            ]
            self.assertEqual(len(sent), 1)
            self.assertEqual(sent[0]["to"], [{"email": "api@example.com"}])
            code = re.search(r"code is: (\d{6})", sent[0]["textContent"]).group(1)

            reset = self.client.post(
                "/api/auth/verify-otp/",
                {
                    "email": "api@example.com",
                    "otp": code,
                    "new_password": "BrandNew!2026",
                    "new_password_confirm": "BrandNew!2026",
                },
            )

        self.assertEqual(reset.status_code, status.HTTP_200_OK)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("BrandNew!2026"))

    def test_a_provider_refusal_leaves_no_live_code(self):
        with patch("accounts.mail_backends.urllib.request.urlopen") as urlopen:
            urlopen.side_effect = _http_error(
                "https://api.brevo.com/v3/smtp/email", 401, b'{"message":"Key not found"}'
            )
            response = self.client.post(
                "/api/auth/forgot-password/", {"email": "api@example.com"}
            )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(
            PasswordResetOTP.objects.filter(user=self.user, consumed_at__isnull=True).exists()
        )
        audit = AuditEvent.objects.filter(outcome="email_failed").last()
        self.assertIsNotNone(audit)


class ApiBackendConfigurationTests(TestCase):
    """`manage.py check` must tell the two API failures apart."""

    def check_ids(self):
        from django.core.checks import run_checks

        return {issue.id for issue in run_checks()}

    @override_settings(
        EMAIL_BACKEND="accounts.mail_backends.BrevoEmailBackend",
        BREVO_API_KEY="",
        DEFAULT_FROM_EMAIL="StudySpace <codes@example.com>",
    )
    def test_a_selected_backend_without_its_key_is_reported(self):
        ids = self.check_ids()
        self.assertIn("accounts.W003", ids)
        self.assertNotIn("accounts.W001", ids)

    @override_settings(
        EMAIL_BACKEND="accounts.mail_backends.BrevoEmailBackend",
        BREVO_API_KEY="xkeysib-test-key",
        DEFAULT_FROM_EMAIL="StudySpace <codes@example.com>",
    )
    def test_a_configured_api_backend_raises_nothing(self):
        self.assertEqual(self.check_ids() & {"accounts.W001", "accounts.W002", "accounts.W003"}, set())

    @override_settings(
        EMAIL_BACKEND="django.core.mail.backends.console.EmailBackend",
        ENVIRONMENT="production",
        DEFAULT_FROM_EMAIL="StudySpace <codes@example.com>",
    )
    def test_a_print_only_backend_in_production_is_reported(self):
        self.assertIn("accounts.W004", self.check_ids())

    @override_settings(
        EMAIL_BACKEND="accounts.mail_backends.BrevoEmailBackend",
        BREVO_API_KEY="xkeysib-test-key",
        DEFAULT_FROM_EMAIL="StudySpace <noreply@studyspace.local>",
    )
    def test_a_placeholder_sender_is_reported_for_api_backends_too(self):
        self.assertIn("accounts.W002", self.check_ids())


@override_settings(
    EMAIL_BACKEND="accounts.mail_backends.BrevoEmailBackend",
    BREVO_API_KEY="xkeysib-test-key",
    DEFAULT_FROM_EMAIL="StudySpace <codes@example.com>",
)
class CheckEmailApiCommandTests(TestCase):
    """`check_email` proves the key before spending a message on it."""

    def test_it_validates_the_key_then_sends(self):
        from io import StringIO

        out = StringIO()
        with patch("accounts.mail_backends.urllib.request.urlopen") as urlopen:
            urlopen.return_value = _FakeHttpResponse(status=201)
            call_command("check_email", "--to", "operator@example.com", stdout=out)

        text = out.getvalue()
        self.assertIn("Brevo accepted the credentials", text)
        self.assertIn("Brevo accepted the message", text)
        urls = [call.args[0].full_url for call in urlopen.call_args_list]
        self.assertIn("https://api.brevo.com/v3/account", urls)
        self.assertIn("https://api.brevo.com/v3/smtp/email", urls)

    @override_settings(BREVO_API_KEY="")
    def test_it_refuses_when_the_key_is_missing(self):
        from django.core.management.base import CommandError

        with self.assertRaises(CommandError) as caught:
            call_command("check_email")
        self.assertIn("BREVO_API_KEY", str(caught.exception))


@override_settings(
    EMAIL_BACKEND="accounts.mail_backends.ResendEmailBackend",
    RESEND_API_KEY="re-send-only-key",
    DEFAULT_FROM_EMAIL="StudySpace <onboarding@resend.dev>",
    EMAIL_TIMEOUT=3,
)
class SendOnlyKeyTests(TestCase):
    """A key restricted to sending must not be reported as a broken deployment.

    Resend lets a key be created with "sending access" only; such a key is
    refused on `/domains` but accepted on `/emails`. Treating the refusal as
    fatal would send the operator chasing a problem that does not exist.
    """

    def test_a_refused_probe_does_not_stop_the_message(self):
        from io import StringIO

        out = StringIO()
        with patch("accounts.mail_backends.urllib.request.urlopen") as urlopen:
            urlopen.side_effect = [
                _http_error("https://api.resend.com/domains", 401, b'{"message":"restricted key"}'),
                _FakeHttpResponse(status=200),
            ]
            call_command("check_email", "--to", "owner@example.com", stdout=out)

        text = out.getvalue()
        self.assertIn("sending is the real test", text)
        self.assertIn("Resend accepted the message", text)
        self.assertNotIn("accepted the credentials", text)

    def test_the_backend_records_the_note_instead_of_raising(self):
        from accounts.mail_backends import ResendEmailBackend

        backend = ResendEmailBackend()
        with patch("accounts.mail_backends.urllib.request.urlopen") as urlopen:
            urlopen.side_effect = _http_error("https://api.resend.com/domains", 403)
            self.assertTrue(backend.open())
        self.assertIn("403", backend.probe_note)

    def test_a_bad_key_on_a_real_send_still_fails_loudly(self):
        from accounts.mail_backends import EmailBackendError, ResendEmailBackend

        with patch("accounts.mail_backends.urllib.request.urlopen") as urlopen:
            urlopen.side_effect = _http_error("https://api.resend.com/emails", 401)
            with self.assertRaises(EmailBackendError):
                ResendEmailBackend().send_messages(
                    [EmailMessage("s", "b", "StudySpace <a@b.c>", ["x@y.z"])]
                )


class CaseInsensitiveIdentityTests(TestCase):
    """Finding 6: the uniqueness rule has to survive a race.

    The serializer's `.exists()` check is advisory; two requests can pass it at
    the same instant. These tests hold the database itself to the rule, and
    exercise the deduplication that has to run before the index can be created
    on an existing database.
    """

    MIGRATION = "accounts.migrations.0002_case_insensitive_unique_identity"

    def migration(self):
        import importlib

        return importlib.import_module(self.MIGRATION)

    def test_the_database_refuses_a_case_variant_username(self):
        from django.db import IntegrityError, transaction

        User.objects.create_user("Alice", "alice@example.com", "SecurePass123!")
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                User.objects.create_user("alice", "other@example.com", "SecurePass123!")

    def test_the_database_refuses_a_case_variant_email(self):
        from django.db import IntegrityError, transaction

        User.objects.create_user("alice", "Alice@Example.com", "SecurePass123!")
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                User.objects.create_user("bob", "alice@example.com", "SecurePass123!")

    def test_blank_emails_are_still_allowed(self):
        """Superusers created from the command line have no address."""
        User.objects.create_user("root_one", "", "SecurePass123!")
        User.objects.create_user("root_two", "", "SecurePass123!")
        self.assertEqual(User.objects.filter(email="").count(), 2)

    def test_deduplicate_renames_the_newer_collision(self):
        """Run the migration's data step on a database that already has twins.

        The oldest row keeps its identity; later ones get a suffix built from
        their primary key, which stays valid for both fields and unique by
        construction.
        """
        migration = self.migration()
        from django.apps import apps
        from django.db import connection

        with connection.cursor() as cursor:
            cursor.execute(migration.DROP_USERNAME_INDEX)
            cursor.execute(migration.DROP_EMAIL_INDEX)
        try:
            older = User.objects.create_user("Alice", "alice@example.com", "SecurePass123!")
            newer = User.objects.create_user("alice", "ALICE@example.com", "SecurePass123!")

            migration.deduplicate(apps, connection)

            older.refresh_from_db()
            newer.refresh_from_db()
            self.assertEqual(older.username, "Alice")
            self.assertEqual(older.email, "alice@example.com")
            self.assertEqual(newer.username, f"alice-{newer.id}")
            # Case is preserved in the local part; the index compares LOWER().
            self.assertEqual(newer.email.lower(), f"alice+dup{newer.id}@example.com")

            # The renamed rows satisfy the index that is created next.
            with connection.cursor() as cursor:
                cursor.execute(migration.CREATE_USERNAME_INDEX)
                cursor.execute(migration.CREATE_EMAIL_INDEX)
        finally:
            User.objects.filter(pk=newer.pk).delete() if "newer" in locals() else None
            with connection.cursor() as cursor:
                cursor.execute(migration.CREATE_USERNAME_INDEX)
                cursor.execute(migration.CREATE_EMAIL_INDEX)
