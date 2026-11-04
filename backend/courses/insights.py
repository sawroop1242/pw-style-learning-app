"""What a learner's marked papers say about them, chapter by chapter.

Why this module exists
----------------------
Every submitted attempt already stores, per question, whether it was right,
wrong or left blank — and ``Question.topic`` names the chapter. Nothing read
that back. The result screen shows one paper at a time, so a learner can see
they lost 6 marks in *Kinematics* today but not that Kinematics has cost them
marks in three papers running. That cross-paper view is the thing PW puts
behind "analysis", and it is the reason a result page is worth revisiting.

What it refuses to do
---------------------
* **No result that was not released.** Aggregating an unreleased paper would
  leak which chapters it contained, so only rows with ``result_released_at``
  are read.
* **No invented accuracy.** A chapter's accuracy is ``correct / (correct +
  incorrect)`` — answered questions only. A chapter that was skipped is shown
  with ``accuracy: None``, because "0% in Thermodynamics" and "never attempted
  Thermodynamics" are different facts.
* **No fragile ranking.** Calling a chapter weak after one guessed question is
  noise. A chapter needs ``MIN_ANSWERED`` marked answers before it can enter
  the focus list, and the threshold is returned in the payload so the screen
  can say *why* a chapter is not ranked yet.
* **No question bank reads.** Every number comes from the frozen paper of an
  attempt, so editing or deleting a question afterwards cannot rewrite history.

The aggregation is done here rather than in SQL on purpose: the marked state of
an answer depends on the frozen key, not on live rows, and ``grade_attempt``
already knows how to read it.
"""

from decimal import Decimal

from . import grading
from .models import QuizAttempt

ZERO = Decimal("0.00")

#: Marked answers a chapter needs before it can be called weak.
MIN_ANSWERED = 3

#: Accuracy below this reads as weak. Returned with the payload so the UI can
#: print the rule instead of asserting a judgement of its own.
WEAK_BELOW = 60.0

#: How many chapters the focus list names. More than three is a to-do list.
FOCUS_LIMIT = 3


def _key(topic):
    """Group chapters case- and space-insensitively, keep the first spelling."""
    collapsed = " ".join((topic or "").split())
    return collapsed.casefold()


def topic_insights(user):
    """Aggregate the signed-in learner's released attempts by chapter.

    Returns a payload shaped for the UI:

        {"released_attempts": 3, "questions": 42,
         "topics": [{"topic", "questions", "correct", "incorrect", "unanswered",
                     "answered", "accuracy", "score", "max_score", "attempts"}],
         "focus": [<up to FOCUS_LIMIT of the topics above, weakest first>],
         "rules": {"min_answered": 3, "weak_below": 60.0}}

    ``topics`` is every chapter that appeared on a released paper (including
    untagged questions, grouped under ``Unlabelled``), sorted by accuracy with
    the weakest first and unranked chapters last; ``focus`` is the subset that
    clears the threshold. Nothing is derived from attempts that never got a
    released result.
    """

    attempts = (
        QuizAttempt.objects.filter(
            user=user,
            status__in=[QuizAttempt.Status.SUBMITTED, QuizAttempt.Status.EXPIRED],
            result_released_at__isnull=False,
        )
        .prefetch_related("answers")
        .order_by("-submitted_at", "-id")
    )

    topics = {}
    released = 0
    questions = 0

    for attempt in attempts:
        graded = grading.grade_attempt(attempt)
        released += 1
        for bucket in graded["topics"]:
            questions += bucket["correct"] + bucket["incorrect"] + bucket["unanswered"]
            key = _key(bucket["topic"])
            row = topics.get(key)
            if row is None:
                row = topics[key] = {
                    "topic": bucket["topic"].strip() or grading.UNLABELLED,
                    "correct": 0,
                    "incorrect": 0,
                    "unanswered": 0,
                    "score": ZERO,
                    "max_score": ZERO,
                    "attempts": 0,
                }
            row["correct"] += bucket["correct"]
            row["incorrect"] += bucket["incorrect"]
            row["unanswered"] += bucket["unanswered"]
            row["score"] += bucket["score"]
            row["max_score"] += bucket["max_score"]
            row["attempts"] += 1

    rows = []
    for row in topics.values():
        answered = row["correct"] + row["incorrect"]
        accuracy = round(row["correct"] * 100.0 / answered, 1) if answered else None
        rows.append(
            {
                "topic": row["topic"],
                "questions": answered + row["unanswered"],
                "correct": row["correct"],
                "incorrect": row["incorrect"],
                "unanswered": row["unanswered"],
                "answered": answered,
                "accuracy": accuracy,
                "score": str(row["score"].quantize(Decimal("0.01"))),
                "max_score": str(row["max_score"].quantize(Decimal("0.01"))),
                "attempts": row["attempts"],
            }
        )

    # Weakest first; a chapter with no marked answer has no accuracy to sort by
    # and belongs at the end, not at 0%.
    rows.sort(
        key=lambda row: (
            row["accuracy"] is None,
            row["accuracy"] if row["accuracy"] is not None else 0,
            -row["answered"],
            row["topic"].casefold(),
        )
    )

    focus = [
        row
        for row in rows
        if row["accuracy"] is not None
        and row["answered"] >= MIN_ANSWERED
        and row["accuracy"] < WEAK_BELOW
    ][:FOCUS_LIMIT]

    return {
        "released_attempts": released,
        "questions": questions,
        "topics": rows,
        "focus": focus,
        "rules": {"min_answered": MIN_ANSWERED, "weak_below": WEAK_BELOW},
    }
