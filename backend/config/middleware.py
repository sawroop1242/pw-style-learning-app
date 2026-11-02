"""Response headers that are not Django's business.

``SecurityMiddleware`` sends the headers named in its own settings; the
Content-Security-Policy is not one of them, because a policy is specific to
what an application actually loads. Keeping it here rather than in a view means
it lands on API responses, admin pages and the static shell alike — a policy
that covers only ``*.html`` is a policy an injected script can step around by
being served from a path that skipped it.
"""

from __future__ import annotations

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
