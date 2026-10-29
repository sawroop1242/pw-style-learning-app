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


def build_cards(app_list, request, site=admin.site):
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
            rows.append(_row(model_key, model, request, site))
        if rows:
            cards.append({"key": key, "title": title, "blurb": blurb, "models": rows})

    leftovers = [
        _row(model_key, model, request, site)
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


def _row(model_key, model, request, site):
    app_label, model_name = model_key.split(".")
    count = None
    try:
        model_class = apps.get_model(app_label, model_name)
        count = _count(site.get_model_admin(model_class), request)
    except (LookupError, admin.sites.NotRegistered, PermissionDenied):
        count = None
    return {
        "key": model_key,
        "name": model["name"],
        "url": model["admin_url"],
        "add_url": model.get("add_url"),
        "count": count,
    }


@register.simple_tag(takes_context=True)
def workflow_cards(context, app_list):
    """``{% workflow_cards app_list as cards %}``"""
    return build_cards(app_list, context.get("request"))
