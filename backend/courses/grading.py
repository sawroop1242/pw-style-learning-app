"""Attempt grading in one place.

Both the submit endpoint and the result serializer call this module, so a
learner can never be shown counts that disagree with the stored score.

Grading reads the **frozen paper** (``QuizAttempt.paper_snapshot``) and the
persisted answers — never the live question bank. That is what makes an attempt
a record rather than a view: editing the key, the marks or the options after a
student starts cannot change their paper, their score or their review.
"""

from collections import OrderedDict
from decimal import Decimal

from . import snapshot

ZERO = Decimal("0.00")
#: Label for questions whose chapter was never recorded. Grouped, never hidden:
#: a paper that is entirely untagged should say so rather than show nothing.
UNLABELLED = "Unlabelled"


def chosen_ids(answer):
    """The choice ids this answer recorded, from the attempt itself.

    ``selected_choice_ids`` is written at submit/autosave time from the frozen
    paper, so it survives both the live ``Choice`` rows and the m2m table. The
    m2m relation is still read as a fallback for rows written before the
    snapshot existed.
    """
    recorded = getattr(answer, "selected_choice_ids", None)
    if recorded:
        return {int(choice_id) for choice_id in recorded}
    cache = getattr(answer, "_prefetched_objects_cache", {})
    if "selected_choices" in cache:
        return {choice.id for choice in cache["selected_choices"]}
    return set(answer.selected_choices.values_list("id", flat=True))


#: Former name, kept because callers and older tests use it.
selected_ids = chosen_ids


def answer_is_correct(question_entry, chosen):
    """Score one answer against the frozen key."""
    return snapshot.choice_is_correct(question_entry, chosen)


def grade_attempt(attempt):
    """Score ``attempt`` from its frozen paper and persisted answers.

    Returns a dict with the score, the maximum achievable score (computed over
    every question in the snapshot, so an unanswered question still counts
    towards the denominator), answer counts, and a **per-topic** breakdown.

    The breakdown is keyed on the chapter (``Question.topic``), not the section
    the paper prints: "Physics: 12/20" says the paper was hard, "Kinematics:
    2/8" says which chapter to revise. Questions with no chapter are grouped
    under ``UNLABELLED`` and are shown, not guessed at.
    """
    paper = snapshot.paper_for(attempt)
    policy = snapshot.quiz_policy(paper)
    questions = snapshot.questions_of(paper)

    answers = {
        (answer.question_snapshot_id or answer.question_id): answer
        for answer in attempt.answers.all()
    }

    score = ZERO
    max_score = ZERO
    correct = incorrect = unanswered = marked = 0
    topics = OrderedDict()

    # The denominator follows the attempt snapshot, not the submitted payload
    # and not whatever the question bank looks like today.
    for question_id in attempt.question_order or [entry["id"] for entry in paper.get("questions", [])]:
        answer = answers.get(question_id)
        question_entry = questions.get(question_id)
        if question_entry is None:
            continue
        question_marks = snapshot.marks_for(question_entry, policy)
        max_score += question_marks

        topic = question_entry.get("topic") or UNLABELLED
        bucket = topics.setdefault(
            topic,
            {"topic": topic, "correct": 0, "incorrect": 0, "unanswered": 0,
             "score": ZERO, "max_score": ZERO},
        )
        bucket["max_score"] += question_marks

        chosen = chosen_ids(answer) if answer is not None else set()
        if answer is not None and answer.marked_for_review:
            marked += 1

        if not chosen:
            unanswered += 1
            bucket["unanswered"] += 1
            continue

        if snapshot.choice_is_correct(question_entry, chosen):
            correct += 1
            bucket["correct"] += 1
            score += question_marks
            bucket["score"] += question_marks
        else:
            incorrect += 1
            bucket["incorrect"] += 1
            penalty = snapshot.negative_marks_for(question_entry, policy)
            score -= penalty
            bucket["score"] -= penalty

    # Exam scoring never reports a negative total; the per-question negative
    # marks still reduce the raw sum before this floor is applied.
    if score < 0:
        score = ZERO

    return {
        "score": score.quantize(Decimal("0.01")),
        "max_score": max_score.quantize(Decimal("0.01")),
        "correct": correct,
        "incorrect": incorrect,
        "unanswered": unanswered,
        "marked_for_review": marked,
        "topics": list(topics.values()),
    }


def ensure_answer_rows(attempt, questions):
    """Create the answer rows an attempt needs, without dropping saved ones."""
    from .models import AttemptAnswer  # local import: avoid a models cycle

    existing = set(
        AttemptAnswer.objects.filter(attempt=attempt).values_list(
            "question_snapshot_id", flat=True
        )
    )
    missing = [q for q in questions if q.id not in existing]
    if missing:
        AttemptAnswer.objects.bulk_create(
            [
                AttemptAnswer(
                    attempt=attempt,
                    question=q,
                    question_snapshot_id=q.id,
                    selected_choice_ids=[],
                )
                for q in missing
            ],
            ignore_conflicts=True,
        )
