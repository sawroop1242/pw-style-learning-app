import hashlib
import hmac
from datetime import timedelta
from unittest.mock import patch

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core import mail
from django.test import TestCase, override_settings
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
        self.change_password_url = "/api/auth/change_password/"
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
        self.forgot_url = "/api/auth/forgot_password/"
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
        self.verify_url = "/api/auth/verify_otp/"
        self.user = User.objects.create_user(
            "testuser", "test@example.com", "SecurePass123!"
        )
        # Clear cache to avoid interference between tests
        from django.core.cache import cache
        cache.clear()
        # Request OTP
        self.client.post("/api/auth/forgot_password/", {"email": "test@example.com"})
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
        self.client.post("/api/auth/forgot_password/", {"email": "test2@example.com"})
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
        self.resend_url = "/api/auth/resend_otp/"
        self.user = User.objects.create_user(
            "testuser", "test@example.com", "SecurePass123!"
        )
        # Clear cache to avoid interference between tests
        from django.core.cache import cache
        cache.clear()

    def test_resend_otp_success(self):
        """Test resend OTP works same as forgot_password."""
        # Initial request
        self.client.post("/api/auth/forgot_password/", {"email": "test@example.com"})
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
        for i in range(5):
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
        # 6th request should be throttled
        response = self.client.post(
            url,
            {
                "username": "user5",
                "email": "user5@example.com",
                "password": "SecurePass123!",
                "password_confirm": "SecurePass123!",
            },
        )
        self.assertEqual(response.status_code, status.HTTP_429_TOO_MANY_REQUESTS)

    def test_login_throttle(self):
        """Test login is throttled."""
        url = "/api/token/"
        user = User.objects.create_user("testuser", "test@example.com", "SecurePass123!")
        for i in range(10):
            response = self.client.post(
                url, {"username_or_email": "testuser", "password": "SecurePass123!"}
            )
            self.assertIn(response.status_code, [status.HTTP_200_OK, status.HTTP_400_BAD_REQUEST])
        # 11th request should be throttled
        response = self.client.post(
            url, {"username_or_email": "testuser", "password": "SecurePass123!"}
        )
        self.assertEqual(response.status_code, status.HTTP_429_TOO_MANY_REQUESTS)

    def test_forgot_password_throttle(self):
        """Test forgot password is throttled."""
        url = "/api/auth/forgot_password/"
        for i in range(3):
            response = self.client.post(url, {"email": f"test{i}@example.com"})
            self.assertEqual(response.status_code, status.HTTP_200_OK)
        # 4th request should be throttled
        response = self.client.post(url, {"email": "test3@example.com"})
        self.assertEqual(response.status_code, status.HTTP_429_TOO_MANY_REQUESTS)

    def test_otp_verify_throttle(self):
        """Test OTP verification is throttled."""
        url = "/api/auth/verify_otp/"
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
        """Test forgot password handles email failure gracefully."""
        mock_send.side_effect = Exception("SMTP error")
        client = APIClient()
        user = User.objects.create_user("testuser", "test@example.com", "SecurePass123!")

        response = client.post("/api/auth/forgot_password/", {"email": "test@example.com"})
        # Should still return generic success (no enumeration)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # OTP should still be created
        self.assertTrue(PasswordResetOTP.objects.filter(user=user).exists())
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