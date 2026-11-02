"""Small pieces of markup shared by more than one app's admin.

A status is a status wherever it appears: the console shows the same green for a
published batch, a connected bucket and a finished import, so a colour means one
thing across thirty screens. Keeping the markup in one function is what makes
that true; copying a span into three admins is how a fourth one comes out grey.
"""

from __future__ import annotations

from django.utils.html import format_html

#: kind → the meaning it carries in staff/admin.css.
KINDS = {"ok", "warn", "bad", "info", "muted"}


def pill(label: str, kind: str = "muted") -> str:
    """A status chip. ``kind`` is one of :data:`KINDS`."""
    if kind not in KINDS:
        kind = "muted"
    return format_html('<span class="ss-pill ss-pill--{}">{}</span>', kind, label)
