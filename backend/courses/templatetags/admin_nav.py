"""Group the admin index into the jobs a content editor actually does.

Django's index lists every registered model under its app, alphabetically. That
is fine for three models and useless for twenty-five: "Lessons" sat between
"Csv import jobs" and "Notes", and nothing told you which of the twenty-five
you needed in order to publish a class.

So the models are described once, here, as workflows — batches, tests, access,
messages, learner data, people — and the index template draws one card per
workflow. A model that is not listed still appears, in a final "Everything
else" card: adding a model to the admin must never make it vanish from the
index.

Counts come from the *registered admin's* queryset, not from `Model.objects`,
so a sub-admin sees the number of rows they may actually open rather than a
total they cannot reach.
"""

from django import template
from django.apps import apps
from django.contrib import admin
from django.core.exceptions import PermissionDenied

register = template.Library()

#: (key, card title, one line of help, [models as "app_label.model_name"])
WORKFLOWS = [
    (
        "content",
        "Batches and lessons",
        "What a learner opens: the batch, its folders, the classes and the notes.",
        [
            "courses.course",
            "courses.coursefolder",
            "courses.lesson",
            "courses.pdfresource",
            "courses.coursefaculty",
        ],
    ),
    (
        "tests",
        "Tests and questions",
        "A paper, its questions, and the bulk import when a CSV already exists.",
        [
            "courses.testseries",
            "courses.quiz",
            "courses.question",
            "courses.csvimportjob",
        ],
    ),
    (
        "access",
        "Access and enrolment",
        "Who may open a paid batch, and the codes that let them in.",
        ["courses.accesscode", "courses.courseaccessgrant"],
    ),
    (
        "storage",
        "Storage and media",
        "The Cloudflare R2 accounts and buckets that batch covers and note PDFs go into.",
        ["objectstore.r2account", "objectstore.r2bucket"],
    ),
    (
        "messages",
        "Announcements and reports",
        "Notices on the feed, and the questions a learner flagged.",
        ["courses.communitypost", "courses.questionreport"],
    ),
    (
        "learners",
        "Learner activity",
        "Attempts, saved notes, progress, bookmarks and study tasks.",
        [
            "courses.quizattempt",
            "courses.attemptanswer",
            "courses.note",
            "courses.progress",
            "courses.bookmark",
            "courses.revisionitem",
            "courses.studytask",
        ],
    ),
    (
        "people",
        "People and permissions",
        "Accounts, their role, and the audit trail.",
        [
            "auth.user",
            "auth.group",
            "accounts.profile",
            "accounts.passwordresetotp",
            "accounts.auditevent",
            "token_blacklist.outstandingtoken",
            "token_blacklist.blacklistedtoken",
        ],
    ),
]

FALLBACK_KEY = "other"
FALLBACK_TITLE = "Everything else"
FALLBACK_BLURB = "Models without a home in the cards above."


def _count(model_admin, request):
    """Rows this user may open, or ``None`` when the model cannot be counted."""
    try:
        return model_admin.get_queryset(request).count()
    except (PermissionDenied, AttributeError, TypeError):
        return None


def build_cards(app_list, request, site=admin.site, with_counts=True):
    """Turn Django's ``app_list`` into the workflow cards the index renders.

    ``app_list`` is already permission-filtered, so nothing is invented here: a
    model the user may not see never reaches this function, and a card whose
    models are all invisible is dropped rather than shown empty.
    """
    seen = {}
    for app in app_list:
        for model in app["models"]:
            key = f"{app['app_label']}.{model['object_name'].lower()}"
            seen[key] = model

    cards = []
    placed = set()
    for key, title, blurb, model_keys in WORKFLOWS:
        rows = []
        for model_key in model_keys:
            model = seen.get(model_key)
            if model is None:
                continue
            placed.add(model_key)
            rows.append(_row(model_key, model, request, site, with_counts))
        if rows:
            cards.append({"key": key, "title": title, "blurb": blurb, "models": rows})

    leftovers = [
        _row(model_key, model, request, site, with_counts)
        for model_key, model in seen.items()
        if model_key not in placed
    ]
    if leftovers:
        cards.append(
            {
                "key": FALLBACK_KEY,
                "title": FALLBACK_TITLE,
                "blurb": FALLBACK_BLURB,
                "models": leftovers,
            }
        )
    return cards


def _row(model_key, model, request, site, with_counts=True):
    app_label, model_name = model_key.split(".")
    count = None
    if with_counts:
        try:
            model_class = apps.get_model(app_label, model_name)
            count = _count(site.get_model_admin(model_class), request)
        except (LookupError, admin.sites.NotRegistered, PermissionDenied):
            count = None
    return {
        "key": model_key,
        "name": model["name"],
        # The model's own name, so the rail can draw the right glyph and the
        # theme can colour a row without matching on translated text.
        "model_name": model_name,
        "slug": app_label.lower(),
        "url": model["admin_url"],
        "add_url": model.get("add_url"),
        "count": count,
        # The sidebar highlights the row for the page being edited.
        "is_current": bool(model["admin_url"]) and model["admin_url"] in request.path,
    }


#: The four numbers a content editor checks before starting work. Each is a
#: model that already appears in ``app_list``; a tile the user may not open is
#: never rendered, so the row never shows a zero standing in for "no access".
STAT_TILES = [
    ("courses.course", "Batches", "on the catalogue"),
    ("courses.lesson", "Lessons", "in every batch"),
    ("courses.quiz", "Tests", "papers and mock series"),
    ("courses.quizattempt", "Attempts", "started by learners"),
]


@register.simple_tag(takes_context=True)
def console_stats(context, app_list):
    """``{% console_stats app_list as stats %}`` — the tiles on the home page."""
    request = context.get("request")
    visible = {}
    for app in app_list:
        for model in app["models"]:
            visible[f"{app['app_label']}.{model['object_name'].lower()}"] = model

    tiles = []
    for model_key, label, hint in STAT_TILES:
        model = visible.get(model_key)
        if model is None or not model["admin_url"]:
            continue
        try:
            model_class = apps.get_model(*model_key.split("."))
            count = _count(admin.site.get_model_admin(model_class), request)
        except (LookupError, admin.sites.NotRegistered, PermissionDenied):
            count = None
        if count is None:
            continue
        tiles.append(
            {"label": label, "hint": hint, "count": count, "url": model["admin_url"]}
        )
    return tiles


@register.simple_tag(takes_context=True)
def workflow_cards(context, app_list):
    """``{% workflow_cards app_list as cards %}`` — the console home."""
    return build_cards(app_list, context.get("request"), with_counts=True)


@register.simple_tag(takes_context=True)
def workflow_groups(context, app_list):
    """The same grouping for the navigation rail, without the row counts.

    Counting every model on every admin page would be twenty-five queries for
    a number nobody reads in the sidebar.
    """
    return build_cards(app_list, context.get("request"), with_counts=False)


@register.simple_tag
def email_delivery_problem():
    """A sentence for the console home when reset mail cannot be delivered.

    Returns "" when the transport looks usable, so the template can ask
    ``{% if problem %}`` without a second setting lookup of its own.
    """
    from accounts.checks import delivery_problem

    return delivery_problem() or ""
