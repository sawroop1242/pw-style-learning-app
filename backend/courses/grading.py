"""Attempt grading in one place.

Both the submit endpoint and the result serializer call this module, so a
learner can never be shown counts that disagree with the stored score. Grading
always reads the persisted answers and the frozen ``question_order`` snapshot,
never the request payload.
"""

from collections import OrderedDict
from decimal import Decimal

from .models import AttemptAnswer, Question

ZERO = Decimal("0.00")
UNSECTIONED = "Unsectioned"


def marks_for(question, quiz):
    return question.marks if question.marks is not None else quiz.marks_per_question


def negative_marks_for(question, quiz):
    if question.negative_marks is not None:
        return question.negative_marks
    return quiz.negative_marks_per_wrong


def selected_ids(answer):
    """Selected choice IDs for ``answer``, using the prefetch cache if warm."""
    cache = getattr(answer, "_prefetched_objects_cache", {})
    if "selected_choices" in cache:
        return {choice.id for choice in cache["selected_choices"]}
    return set(answer.selected_choices.values_list("id", flat=True))


def correct_ids(question):
    cache = getattr(question, "_prefetched_objects_cache", {})
    if "choices" in cache:
        return {choice.id for choice in cache["choices"] if choice.is_correct}
    return set(question.choices.filter(is_correct=True).values_list("id", flat=True))


def answer_is_correct(question, chosen):
    """Single-choice/true-false need exactly the right option; multi-choice
    needs the exact set (no partial credit unless a future spec adds it)."""
    expected = correct_ids(question)
    if not chosen:
        return False
    if question.question_type == Question.QuestionType.MULTIPLE_CHOICE:
        return chosen == expected
    return len(chosen) == 1 and chosen == expected


def grade_attempt(attempt):
    """Score ``attempt`` from its persisted answers.

    Returns a dict with the score, the maximum achievable score (computed over
    every question in the snapshot, so an unanswered question still counts
    towards the denominator), answer counts, and a per-topic breakdown.
    """
    quiz = attempt.quiz
    answers = list(
        attempt.answers.select_related("question")
        .prefetch_related("selected_choices", "question__choices")
        .order_by("question__position", "question_id")
    )
    by_question = {answer.question_id: answer for answer in answers}

    score = ZERO
    max_score = ZERO
    correct = incorrect = unanswered = marked = 0
    sections = OrderedDict()
    correct_ids_by_question = {
        question_id: correct_ids(answer.question) for question_id, answer in by_question.items()
    }

    # The denominator follows the attempt snapshot, not the submitted payload.
    for question_id in attempt.question_order or []:
        answer = by_question.get(question_id)
        if answer is None:
            continue
        question = answer.question
        question_marks = marks_for(question, quiz)
        max_score += question_marks

        section = question.topic or UNSECTIONED
        bucket = sections.setdefault(
            section,
            {"section": section, "correct": 0, "incorrect": 0, "unanswered": 0,
             "score": ZERO, "max_score": ZERO},
        )
        bucket["max_score"] += question_marks

        chosen = selected_ids(answer)
        if answer.marked_for_review:
            marked += 1

        if not chosen:
            unanswered += 1
            bucket["unanswered"] += 1
            continue

        if chosen == correct_ids_by_question.get(question_id, set()) or answer_is_correct(question, chosen):
            correct += 1
            bucket["correct"] += 1
            score += question_marks
            bucket["score"] += question_marks
        else:
            incorrect += 1
            bucket["incorrect"] += 1
            penalty = negative_marks_for(question, quiz)
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
        "sections": list(sections.values()),
    }


def ensure_answer_rows(attempt, questions):
    """Create the answer rows an attempt needs, without dropping saved ones."""
    existing = set(
        AttemptAnswer.objects.filter(attempt=attempt).values_list("question_id", flat=True)
    )
    missing = [q for q in questions if q.id not in existing]
    if missing:
        AttemptAnswer.objects.bulk_create(
            [AttemptAnswer(attempt=attempt, question=q) for q in missing],
            ignore_conflicts=True,
        )
