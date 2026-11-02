"""Response headers that are not Django's business.

``SecurityMiddleware`` sends the headers named in its own settings; the
Content-Security-Policy is not one of them, because a policy is specific to
what an application actually loads. Keeping it here rather than in a view means
it lands on API responses, admin pages and the static shell alike — a policy
that covers only ``*.html`` is a policy an injected script can step around by
being served from a path that skipped it.
"""

from __future__ import annotations

import logging
import re
import time
import uuid

from django.conf import settings

POLICY_HEADER = "Content-Security-Policy"
REPORT_ONLY_HEADER = "Content-Security-Policy-Report-Only"


class ContentSecurityPolicyMiddleware:
    """Attach the configured policy to every response.

    A view may opt out of the default by setting its own header, and a response
    that already carries one is left alone. ``CSP_REPORT_ONLY`` ships the same
    policy as ``Content-Security-Policy-Report-Only`` so a new rule can be
    watched before it is enforced.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        if response.has_header(POLICY_HEADER) or response.has_header(REPORT_ONLY_HEADER):
            return response
        policy = getattr(settings, "CONTENT_SECURITY_POLICY", "")
        if not policy:
            return response
        header = REPORT_ONLY_HEADER if getattr(settings, "CSP_REPORT_ONLY", False) else POLICY_HEADER
        response[header] = policy
        if not getattr(settings, "CSP_REPORT_ONLY", False):
            # Redundant with the policy's frame-ancestors, but older browsers
            # only understand this one.
            response.setdefault("X-Frame-Options", "DENY")
        return response


# --------------------------------------------------------------------------
# Request ids
# --------------------------------------------------------------------------

REQUEST_ID_HEADER = "X-Request-ID"
#: An upstream proxy may supply an id; accept only a boring one, so a header
#: cannot be used to inject newlines into a log line or a response.
_REQUEST_ID_RE = re.compile(r"^[A-Za-z0-9_-]{8,64}$")
request_logger = logging.getLogger("studyspace.requests")


def new_request_id() -> str:
    return uuid.uuid4().hex


class RequestIdMiddleware:
    """Give every request an id and put it on every response.

    A 500 in production is a line in a log nobody can tie to the user's report.
    With an id on the response (and in the message the browser is shown), the
    same string finds the server-side record. The id is logged with the status
    and the duration for errors, and echoed back unchanged when a client or a
    proxy supplies a valid one, so a trace can start at the edge.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        supplied = request.headers.get(REQUEST_ID_HEADER, "")
        request_id = supplied if _REQUEST_ID_RE.match(supplied or "") else new_request_id()
        request.request_id = request_id
        started = time.monotonic()
        try:
            response = self.get_response(request)
        except Exception:
            # Let Django's handler build the 500, but leave a record that ties
            # the traceback's id to the request.
            request_logger.exception(
                "request failed id=%s method=%s path=%s",
                request_id, request.method, request.path,
            )
            raise

        response[REQUEST_ID_HEADER] = request_id
        elapsed_ms = int((time.monotonic() - started) * 1000)
        if response.status_code >= 500:
            request_logger.error(
                "server error id=%s status=%s method=%s path=%s duration_ms=%s",
                request_id, response.status_code, request.method, request.path, elapsed_ms,
            )
        elif elapsed_ms >= 1000:
            request_logger.warning(
                "slow request id=%s status=%s method=%s path=%s duration_ms=%s",
                request_id, response.status_code, request.method, request.path, elapsed_ms,
            )
        return response
