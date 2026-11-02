"""The frozen paper an attempt was actually sat on.

An attempt must stay reviewable and its score must stay true even after the
provider edits or deletes the question bank — a paper is a historical record,
not a view over today's rows. So when an attempt starts, everything needed to
grade it and to show it back to the student is copied into
``QuizAttempt.paper_snapshot``:

* quiz-level policy (marks default, negative default, pass threshold, timing,
  release policy),
* every question: id, prompt, type, topic, marks, negative marks, explanation,
  and the position it occupied,
* every choice: id, text, correctness and position.

Both grading and result review read *this* and never the live ``Question`` or
``Choice`` rows. The live rows are still used when the paper is being edited by
its owner; they are simply not what a past attempt means.

Ids are kept so the API can still speak in the ids the client was shown, and
``question_snapshot_id``/``selected_choice_ids`` on ``AttemptAnswer`` keep an
answer readable after its question row is gone.
"""

from decimal import Decimal

from .models import Question, Quiz

#: Bumped when the payload shape changes. Older attempts without it are
#: reconstructed from the live bank on first read (they predate snapshots).
SNAPSHOT_VERSION = 1

ZERO = Decimal("0.00")


def decimal_str(value):
    """Store money as a string: JSON floats lose the last paisa."""
    if value is None:
        return None
    return str(Decimal(value).quantize(Decimal("0.01")))


def build_paper(quiz, questions, question_ids=None):
    """Return the immutable paper for ``quiz`` as JSON-ready data.

    ``question_ids`` is the order the paper was served in (shuffled when the
    quiz asks for it); it defaults to the questions' natural order.
    """
    by_id = {question.id: question for question in questions}
    order = list(question_ids) if question_ids is not None else [q.id for q in questions]
    entries = []
    for position, question_id in enumerate(order):
        question = by_id.get(question_id)
        if question is None:
            continue
        choices = sorted(
            question.choices.all(), key=lambda choice: (choice.position, choice.id)
        )
        entries.append(
            {
                "id": question.id,
                "position": position,
                "prompt": question.prompt,
                "question_type": question.question_type,
                "topic": question.topic,
                "difficulty": question.difficulty,
                "marks": decimal_str(question.marks),
                "negative_marks": decimal_str(question.negative_marks),
                "explanation": question.explanation,
                "choices": [
                    {
                        "id": choice.id,
                        "text": choice.text,
                        "position": choice.position,
                        "is_correct": bool(choice.is_correct),
                    }
                    for choice in choices
                ],
            }
        )
    return {
        "version": SNAPSHOT_VERSION,
        "quiz": {
            "id": quiz.id,
            "title": quiz.title,
            "marks_per_question": decimal_str(quiz.marks_per_question),
            "negative_marks_per_wrong": decimal_str(quiz.negative_marks_per_wrong),
            "pass_threshold_percent": decimal_str(quiz.pass_threshold_percent),
            "timing_mode": quiz.timing_mode,
            "duration_minutes": quiz.duration_minutes,
            "shuffle_questions": quiz.shuffle_questions,
            "shuffle_options": quiz.shuffle_options,
            "result_release_policy": quiz.result_release_policy,
        },
        "questions": entries,
    }


def legacy_paper(quiz):
    """Rebuild a paper for an attempt that predates snapshots.

    Such an attempt has ``question_order`` but no snapshot. The best available
    paper is the live bank; the caller re-sequences it to the recorded order.
    """
    questions = list(quiz.questions.all().prefetch_related("choices"))
    return build_paper(quiz, questions)


def paper_for(attempt):
    """The paper for ``attempt``, falling back for pre-snapshot attempts."""
    snapshot = getattr(attempt, "paper_snapshot", None) or {}
    if snapshot.get("questions") or snapshot.get("quiz"):
        return snapshot
    paper = legacy_paper(attempt.quiz)
    order = getattr(attempt, "question_order", None) or []
    if order:
        paper = resequence(paper, order)
    return paper


def resequence(paper, order):
    """Return ``paper`` with its questions ordered as ``order`` says."""
    by_id = {entry["id"]: entry for entry in paper["questions"]}
    entries = [by_id[qid] for qid in order if qid in by_id]
    entries.extend(entry for entry in paper["questions"] if entry["id"] not in set(order))
    for position, entry in enumerate(entries):
        entry = dict(entry)
        entry["position"] = position
        entries[position] = entry
    return {**paper, "questions": entries}


def questions_of(paper):
    return {entry["id"]: entry for entry in paper.get("questions", [])}


def quiz_policy(paper):
    return paper.get("quiz", {})


def choice_ids_for(question_entry):
    return {choice["id"] for choice in question_entry.get("choices", [])}


def correct_choice_ids(question_entry):
    return {
        choice["id"] for choice in question_entry.get("choices", []) if choice.get("is_correct")
    }


def marks_for(question_entry, policy):
    """Per-question marks, falling back to the paper's default."""
    value = question_entry.get("marks")
    if value is None:
        value = policy.get("marks_per_question")
    return Decimal(value) if value is not None else ZERO


def negative_marks_for(question_entry, policy):
    value = question_entry.get("negative_marks")
    if value is None:
        value = policy.get("negative_marks_per_wrong")
    return Decimal(value) if value is not None else ZERO


def choice_is_correct(question_entry, chosen):
    """Score one answer against the frozen key.

    Single-choice and true/false need exactly the one right option;
    multiple-choice needs exactly the right set. Partial credit is not part of
    the spec, so an over-selected or under-selected multi-choice answer is
    wrong rather than half right.
    """
    if not chosen:
        return False
    expected = correct_choice_ids(question_entry)
    if question_entry.get("question_type") == Question.QuestionType.MULTIPLE_CHOICE:
        return set(chosen) == expected
    return len(set(chosen)) == 1 and set(chosen) == expected


def review_rows(attempt):
    """The released answer sheet for ``attempt``, from the frozen paper.

    One row per question on the paper — including questions the provider has
    since deleted — carrying the prompt, the options as they were, the key, the
    explanation and whether this student got it right.
    """
    from . import grading  # local import: grading imports this module

    paper = paper_for(attempt)
    questions = questions_of(paper)
    answers = {
        (answer.question_snapshot_id or answer.question_id): answer
        for answer in attempt.answers.all()
    }

    rows = []
    for question_id in attempt.question_order or [entry["id"] for entry in paper.get("questions", [])]:
        entry = questions.get(question_id)
        if entry is None:
            continue
        answer = answers.get(question_id)
        chosen = grading.chosen_ids(answer) if answer is not None else set()
        rows.append(
            {
                "id": answer.id if answer is not None else None,
                "question": question_id,
                "prompt": entry.get("prompt", ""),
                "question_type": entry.get("question_type", ""),
                "explanation": entry.get("explanation", ""),
                "selected_choices": [
                    {"id": choice["id"], "text": choice["text"]}
                    for choice in entry.get("choices", [])
                    if choice["id"] in chosen
                ],
                "correct_choices": [
                    {"id": choice["id"], "text": choice["text"]}
                    for choice in entry.get("choices", [])
                    if choice.get("is_correct")
                ],
                "answered": bool(answer.answered) if answer is not None else False,
                "marked_for_review": bool(answer.marked_for_review) if answer is not None else False,
                "is_correct": choice_is_correct(entry, chosen),
            }
        )
    return rows


def public_paper(attempt):
    """The frozen paper as the student may see it: no key, no explanations.

    Served on the attempt so the player renders what this student was actually
    given. ``is_correct`` and ``explanation`` are dropped: the key and the
    worked solution are disclosed only through a released result, and putting
    them on a payload a student can fetch mid-test would hand the answers out
    with the paper.
    """
    paper = paper_for(attempt)
    return {
        "quiz": quiz_policy(paper),
        "questions": [
            {
                "id": entry["id"],
                "position": entry.get("position", 0),
                "prompt": entry.get("prompt", ""),
                "question_type": entry.get("question_type", ""),
                "topic": entry.get("topic", ""),
                "marks": entry.get("marks"),
                "negative_marks": entry.get("negative_marks"),
                "choices": [
                    {
                        "id": choice["id"],
                        "text": choice["text"],
                        "position": choice.get("position", 0),
                    }
                    for choice in entry.get("choices", [])
                ],
            }
            for entry in paper.get("questions", [])
        ],
    }
