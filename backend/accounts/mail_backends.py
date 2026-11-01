"""Send reset mail through a provider's HTTPS API instead of SMTP.

SMTP needs a host, a port, an encryption mode, a username and an app password,
and some hosting networks block outbound port 587 entirely. Brevo and Resend
accept the same message over HTTPS with one API key: one secret instead of
five, and it works from any network that can reach the internet.

Both providers must know the sender before they will deliver:

* Brevo — verify a single address in the dashboard (a Gmail address is enough),
  then that address may send to anyone on the free plan.
* Resend — verify a whole domain; until then it only delivers to the address
  that owns the account. Fine for testing, not for students.

Configure with environment variables only. Nothing here reads a key from source:

    BREVO_API_KEY=xkeysib-…
    DEFAULT_FROM_EMAIL=StudySpace <you@gmail.com>

`accounts.checks` reports a missing key at build time, and
`manage.py check_email --to you@example.com` proves the key works.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request

from django.conf import settings
from django.core.mail.backends.base import BaseEmailBackend
from django.core.mail.message import EmailMultiAlternatives
from django.utils.encoding import force_str


class EmailBackendError(RuntimeError):
    """The provider refused the message.

    The text is safe to log: it carries the provider's status code and its own
    error message, never the API key or the code that was being sent.
    """


class ProbeUnavailable(EmailBackendError):
    """The read-only check was refused but sending may still work.

    Resend keys can be created with "sending access" only; those keys get a 401
    on `/domains` and a 200 on `/emails`. Treating that as a broken deployment
    would tell the operator to fix something that is not broken.
    """


class _ApiEmailBackend(BaseEmailBackend):
    """Shared plumbing: build one JSON request per message, post it, report.

    Deliberately built on `urllib` from the standard library — adding a HTTP
    client to requirements.txt would slow every deploy for two calls a day.
    """

    api_url = ""
    probe_url = ""
    key_setting = ""
    provider = ""

    def __init__(self, fail_silently=False, **kwargs):
        super().__init__(fail_silently=fail_silently)
        self.api_key = getattr(settings, self.key_setting, "") or ""
        self.api_key = self.api_key.strip()
        self.timeout = getattr(settings, "EMAIL_TIMEOUT", None) or 10
        self.probe_note = ""

    # -- connection protocol ------------------------------------------------
    def open(self):
        """Validate the key with one cheap authenticated request.

        Django never calls this on its own for a plain `send_mail`; it exists so
        `manage.py check_email` has something to prove before it spends a
        message, and so a wrong key fails with "401" instead of a shrug.
        """
        if not self.api_key:
            raise EmailBackendError(
                f"{self.key_setting} is empty, so {self.provider} cannot be used."
            )
        self.probe_note = ""
        try:
            self._request(self.probe_url, method="GET", probe=True)
        except ProbeUnavailable as error:
            # A send-only key. Nothing is wrong, but the key cannot be read
            # back, so the honest answer is "send a real message to be sure".
            self.probe_note = str(error)
        return True

    def close(self):
        return None

    # -- sending ------------------------------------------------------------
    def send_messages(self, email_messages):
        if not email_messages:
            return 0
        sent = 0
        for message in email_messages:
            try:
                self._send(message)
            except Exception:
                if not self.fail_silently:
                    raise
            else:
                sent += 1
        return sent

    def _send(self, message):
        if getattr(message, "attachments", None):
            raise EmailBackendError(
                f"{self.provider} backend sends text only; this message carries "
                "attachments."
            )
        body = force_str(message.body)
        html = None
        if isinstance(message, EmailMultiAlternatives):
            for content, mimetype in message.alternatives:
                if mimetype == "text/html":
                    html = force_str(content)
                    break
        self._request(
            self.api_url,
            method="POST",
            payload=self.build_payload(message, body, html),
        )

    # -- provider-specific bits --------------------------------------------
    def build_payload(self, message, body, html):
        raise NotImplementedError

    # -- HTTP ---------------------------------------------------------------
    def _headers(self):
        return {}

    def _request(self, url, *, method="POST", payload=None, probe=False):
        data = None
        headers = {
            "Accept": "application/json",
            "User-Agent": "StudySpace mailer",
            **self._headers(),
        }
        if payload is not None:
            data = json.dumps(payload).encode("utf-8")
            headers["Content-Type"] = "application/json"
        request = urllib.request.Request(url, data=data, headers=headers, method=method)
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                return response.status, response.read().decode("utf-8", "replace")
        except urllib.error.HTTPError as error:
            detail = error.read().decode("utf-8", "replace")[:300]
            message = (
                f"{self.provider} refused the request (HTTP {error.code}): {detail}"
            )
            if probe and error.code in (401, 403):
                raise ProbeUnavailable(message) from None
            raise EmailBackendError(message) from None
        except urllib.error.URLError as error:
            raise EmailBackendError(
                f"could not reach {self.provider} ({error.reason})"
            ) from None
        except OSError as error:  # timeouts surface as plain OSError
            raise EmailBackendError(
                f"could not reach {self.provider} ({type(error).__name__}: {error})"
            ) from None


def split_sender(value):
    """`StudySpace <a@b>` -> ("StudySpace", "a@b"); `a@b` -> ("", "a@b")."""
    from email.utils import parseaddr

    name, address = parseaddr(value or "")
    return name, address or (value or "").strip()


class BrevoEmailBackend(_ApiEmailBackend):
    api_url = "https://api.brevo.com/v3/smtp/email"
    probe_url = "https://api.brevo.com/v3/account"
    key_setting = "BREVO_API_KEY"
    provider = "Brevo"

    def _headers(self):
        return {"api-key": self.api_key}

    def build_payload(self, message, body, html):
        name, address = split_sender(message.from_email or settings.DEFAULT_FROM_EMAIL)
        payload = {
            "sender": {"email": address, "name": name or "StudySpace"},
            "to": [{"email": address} for address in message.to],
            "subject": force_str(message.subject),
            "textContent": body,
        }
        if message.cc:
            payload["cc"] = [{"email": address} for address in message.cc]
        if message.bcc:
            payload["bcc"] = [{"email": address} for address in message.bcc]
        if message.reply_to:
            payload["replyTo"] = {"email": message.reply_to[0]}
        if html:
            payload["htmlContent"] = html
        return payload


class ResendEmailBackend(_ApiEmailBackend):
    api_url = "https://api.resend.com/emails"
    probe_url = "https://api.resend.com/domains"
    key_setting = "RESEND_API_KEY"
    provider = "Resend"

    def _headers(self):
        return {"Authorization": f"Bearer {self.api_key}"}

    def build_payload(self, message, body, html):
        payload = {
            "from": message.from_email or settings.DEFAULT_FROM_EMAIL,
            "to": list(message.to),
            "subject": force_str(message.subject),
            "text": body,
        }
        if message.cc:
            payload["cc"] = list(message.cc)
        if message.bcc:
            payload["bcc"] = list(message.bcc)
        if message.reply_to:
            payload["reply_to"] = list(message.reply_to)
        if html:
            payload["html"] = html
        return payload
