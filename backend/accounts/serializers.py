from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

from .models import PasswordResetOTP

User = get_user_model()


class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    """Accept username or email for login."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["username_or_email"] = serializers.CharField()
        self.fields.pop("username", None)
        self.fields.pop("password", None)
        self.fields["password"] = serializers.CharField(
            write_only=True, style={"input_type": "password"}
        )

    def validate(self, attrs):
        username_or_email = attrs.get("username_or_email")
        password = attrs.get("password")

        if not username_or_email or not password:
            raise serializers.ValidationError(
                "Must include 'username_or_email' and 'password'."
            )

        # Case-insensitive lookup. `first()` rather than `get()`: the database
        # index added in migration 0002 makes duplicates impossible from now
        # on, but a database restored from before it must answer "wrong
        # password" rather than a 500 from MultipleObjectsReturned.
        user = None
        if "@" in username_or_email:
            user = User.objects.filter(email__iexact=username_or_email).order_by("id").first()
        if user is None:
            user = User.objects.filter(username__iexact=username_or_email).order_by("id").first()

        if user is None or not user.check_password(password):
            raise serializers.ValidationError(
                "No active account found with the given credentials."
            )

        if not user.is_active:
            raise serializers.ValidationError("User account is disabled.")

        # Use Django's authenticate with the actual username
        from django.contrib.auth import authenticate
        authenticated_user = authenticate(username=user.username, password=password)
        if authenticated_user is None:
            raise serializers.ValidationError(
                "No active account found with the given credentials."
            )

        # Use the actual username for parent validation
        attrs["username"] = authenticated_user.username
        self.user = authenticated_user
        
        # Call parent validate to generate tokens (using username field)
        data = super().validate(attrs)
        
        return data


class UserRegistrationSerializer(serializers.ModelSerializer):
    """Registration serializer with unique username/email and password validation."""

    email = serializers.EmailField(required=True)
    password = serializers.CharField(
        write_only=True, style={"input_type": "password"}
    )
    password_confirm = serializers.CharField(
        write_only=True, style={"input_type": "password"}
    )

    class Meta:
        model = User
        fields = ["username", "email", "password", "password_confirm"]
        extra_kwargs = {
            "username": {"required": True},
        }

    def validate_username(self, value):
        """Normalize and validate username uniqueness case-insensitively."""
        normalized = value.strip()
        if not normalized:
            raise serializers.ValidationError("Username cannot be empty.")
        if User.objects.filter(username__iexact=normalized).exists():
            raise serializers.ValidationError("A user with that username already exists.")
        return normalized

    def validate_email(self, value):
        """Normalize and validate email uniqueness case-insensitively."""
        normalized = value.strip().lower()
        if User.objects.filter(email__iexact=normalized).exists():
            raise serializers.ValidationError(
                "A user with that email address already exists."
            )
        return normalized

    def validate_password(self, value):
        """Validate password against Django's configured validators."""
        validate_password(value)
        return value

    def validate(self, attrs):
        """Validate password confirmation."""
        if attrs["password"] != attrs["password_confirm"]:
            raise serializers.ValidationError({"password_confirm": "Passwords do not match."})
        return attrs

    def create(self, validated_data):
        """Create the account, answering a race with a validation error.

        The uniqueness checks in ``validate_username``/``validate_email`` are a
        courtesy: two requests can pass them at the same moment, and the
        database index is what actually decides. Without this, the loser of
        that race would get a 500 for doing nothing wrong.
        """
        validated_data.pop("password_confirm")
        try:
            user = User.objects.create_user(
                username=validated_data["username"],
                email=validated_data["email"],
                password=validated_data["password"],
            )
        except IntegrityError as error:
            raise serializers.ValidationError(self._collision_message(error)) from error
        # Ensure profile is created with student role
        from .models import Profile
        Profile.objects.get_or_create(user=user)
        return user

    @staticmethod
    def _collision_message(error):
        """Turn an index violation into the field-level message a form shows."""
        detail = str(error).lower()
        if "email" in detail:
            return {"email": "A user with that email address already exists."}
        if "username" in detail:
            return {"username": "A user with that username already exists."}
        return "An account with those details already exists."


class UserProfileSerializer(serializers.ModelSerializer):
    """Serializer for user profile (read-only)."""

    role = serializers.CharField(source="profile.role", read_only=True)

    class Meta:
        model = User
        fields = ["id", "username", "email", "date_joined", "role"]
        read_only_fields = fields


class ChangePasswordSerializer(serializers.Serializer):
    """Authenticated password change."""

    current_password = serializers.CharField(
        write_only=True, style={"input_type": "password"}
    )
    new_password = serializers.CharField(
        write_only=True, style={"input_type": "password"}
    )
    new_password_confirm = serializers.CharField(
        write_only=True, style={"input_type": "password"}
    )

    def validate_new_password(self, value):
        validate_password(value)
        return value

    def validate(self, attrs):
        if attrs["new_password"] != attrs["new_password_confirm"]:
            raise serializers.ValidationError(
                {"new_password_confirm": "Passwords do not match."}
            )
        return attrs


class ForgotPasswordSerializer(serializers.Serializer):
    """Forgot password request - accepts email only."""

    email = serializers.EmailField(required=True)

    def validate_email(self, value):
        return value.strip().lower()


class VerifyOTPSerializer(serializers.Serializer):
    """Verify OTP and reset password."""

    email = serializers.EmailField(required=True)
    otp = serializers.CharField(required=True, min_length=6, max_length=6)
    new_password = serializers.CharField(
        write_only=True, style={"input_type": "password"}
    )
    new_password_confirm = serializers.CharField(
        write_only=True, style={"input_type": "password"}
    )

    def validate_email(self, value):
        return value.strip().lower()

    def validate_new_password(self, value):
        validate_password(value)
        return value

    def validate(self, attrs):
        if attrs["new_password"] != attrs["new_password_confirm"]:
            raise serializers.ValidationError(
                {"new_password_confirm": "Passwords do not match."}
            )
        return attrs