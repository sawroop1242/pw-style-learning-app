"""Admin forms whose credential fields are write-only.

Django renders a model field's value into its widget. For an encrypted secret
that would put ciphertext on screen — harmless, but confusing — and for a
replacement token the field must start empty. Both credential inputs are
therefore ordinary ``CharField``s with a password widget and
``render_value=False``: the page never echoes what is stored, and leaving them
blank keeps the stored token untouched.
"""

from __future__ import annotations

from django import forms
from django.core.exceptions import ValidationError

from .models import ACCOUNT_ID_RE, ACCESS_KEY_RE, R2Account, R2Bucket

SECRET_WIDGET = forms.PasswordInput(
    render_value=False,
    attrs={"autocomplete": "new-password", "spellcheck": "false"},
)


class R2AccountAdminForm(forms.ModelForm):
    access_key_id = forms.CharField(
        required=False,
        label="Access key id",
        widget=SECRET_WIDGET,
        help_text="From the R2 API token Cloudflare shows once, at creation time.",
    )
    secret_access_key = forms.CharField(
        required=False,
        label="Secret access key",
        widget=SECRET_WIDGET,
        help_text="Stored encrypted. It is never displayed again, not even to a main admin.",
    )

    class Meta:
        model = R2Account
        # `owner` is here so a main admin can hand an account to a sub-admin;
        # the admin's `get_exclude` removes it for everyone else.
        fields = ("name", "account_id", "owner", "is_active")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if "owner" in self.fields:
            # The person adding an account is its owner unless a main admin
            # says otherwise; save_model() fills in the requester when this is
            # left blank, so an empty picker is not an error.
            self.fields["owner"].required = False
        if self.instance.pk and self.instance.has_credentials():
            hint = self.instance.access_key_hint or "stored"
            note = (
                f"A token is already stored ({hint}). Leave both boxes empty to keep "
                "it, or paste a new pair to replace it."
            )
            self.fields["access_key_id"].help_text = note
            self.fields["secret_access_key"].help_text = note

    def clean(self):
        cleaned = super().clean()
        access = (cleaned.get("access_key_id") or "").strip()
        secret = (cleaned.get("secret_access_key") or "").strip()

        if access or secret:
            if not (access and secret):
                raise ValidationError(
                    "Paste both the access key id and the secret access key — "
                    "Cloudflare issues them as a pair."
                )
            if not ACCESS_KEY_RE.match(access):
                self.add_error(
                    "access_key_id",
                    "An R2 access key id is 32 letters and digits. Copy it again "
                    "from the token Cloudflare created.",
                )
        elif not (self.instance.pk and self.instance.has_credentials()):
            raise ValidationError(
                "Paste the access key id and secret access key for this Cloudflare account."
            )

        account_id = (cleaned.get("account_id") or "").strip().lower()
        if account_id and not ACCOUNT_ID_RE.match(account_id):
            self.add_error(
                "account_id",
                "A Cloudflare account id is 32 hexadecimal characters.",
            )
        return cleaned

    def save(self, commit=True):
        account = super().save(commit=False)
        access = (self.cleaned_data.get("access_key_id") or "").strip()
        secret = (self.cleaned_data.get("secret_access_key") or "").strip()
        if access and secret:
            account.set_credentials(access, secret)
        if commit:
            account.save()
            self.save_m2m()
        return account


class R2BucketForm(forms.ModelForm):
    """Bucket metadata only — the model's ``save`` enforces the default rules."""

    class Meta:
        model = R2Bucket
        fields = "__all__"
