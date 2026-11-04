"""The batch outline: its sections and classes, in the order a student meets them.

A batch is an ordered thing. "Kinematics" comes after "Units and measurement",
and a class sits in a section. The console expressed that order as a column of
`position` integers in two separate tables: to move a class from third to first
you read the numbers, decide what the other numbers should become, and type
them all again. Every one of those edits is a chance to leave two rows claiming
the same position — an order the database accepts and nobody can predict.

This module holds the order as a whole: read it, hand it to a screen, and write
it back only if the whole thing arrived intact. Anything else is refused with a
message a person can act on, because a reorder that half-applies is worse than
one that does not apply at all.

The rules:

* the payload names **every** section of the batch exactly once, in order;
* it names **every** class of the batch exactly once, inside one section (or in
  the trailing "no section" bucket);
* a class may move between sections — that is the drag a teacher expects — and
  its `position` is rewritten to the index it landed on;
* the save carries the revision it was built from, so two people arranging the
  same batch cannot silently overwrite each other.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass

from django.db import transaction
from django.utils import timezone

from .models import CourseFolder, Lesson

#: Where a class lives when no section has claimed it. Sections have a foreign
#: key; the bucket does not exist in the database and is never saved as one.
NO_SECTION = None


class OutlineError(Exception):
    """A save that must be refused, with the status and code the screen shows.

    The console answers with a message rather than a traceback: an outline page
    is a work surface, and the person in it needs to know whether to reload the
    page or fix one row.
    """

    def __init__(self, message: str, *, code: str = "invalid", status: int = 400):
        super().__init__(message)
        self.message = message
        self.code = code
        self.status = status


@dataclass(frozen=True)
class OutlineSection:
    """One row of the outline screen: a section and the classes inside it."""

    folder: CourseFolder | None
    title: str
    lessons: list

    @property
    def is_loose(self) -> bool:
        return self.folder is None

    @property
    def folder_id(self):
        return self.folder.pk if self.folder else None


def build_outline(course) -> list[OutlineSection]:
    """Every section of the batch, in order, with its classes attached.

    Two queries regardless of how many sections the batch has: the screen draws
    a class list per section, and a query per section is how a 20-section batch
    turns into 21 round trips.
    """
    folders = list(course.folders.order_by("position", "id"))
    lessons = list(course.lessons.order_by("position", "id"))
    by_folder: dict[int, list] = {}
    loose: list = []
    for lesson in lessons:
        if lesson.folder_id is None:
            loose.append(lesson)
        else:
            by_folder.setdefault(lesson.folder_id, []).append(lesson)
    sections = [
        OutlineSection(folder=folder, title=folder.title, lessons=by_folder.get(folder.pk, []))
        for folder in folders
    ]
    if loose:
        sections.append(OutlineSection(folder=None, title="No section", lessons=loose))
    return sections


def revision_of(sections: list[OutlineSection]) -> str:
    """A short fingerprint of this exact order.

    Built from ids rather than timestamps: renaming a class does not invalidate
    somebody's work in progress, but moving one does. Two editors who loaded the
    same order share a revision; whoever saves first changes it.
    """
    payload = [[section.folder_id, [lesson.pk for lesson in section.lessons]] for section in sections]
    blob = json.dumps(payload, separators=(",", ":")).encode()
    return hashlib.sha1(blob).hexdigest()[:16]


def _as_int(value, *, field: str) -> int:
    # `bool` is an `int` in Python, and `True` must not be read as id 1.
    if isinstance(value, bool) or not isinstance(value, int):
        raise OutlineError(
            f"{field} in that order was not a number. Reload the page and try again."
        )
    return value


def _read_sections(payload) -> list[tuple[int | None, list[int]]]:
    """The payload as `[(folder_id | None, [lesson_id, ...]), ...]`."""
    if not isinstance(payload, dict):
        raise OutlineError("That request was not readable. Reload the page and try again.")
    raw_sections = payload.get("sections")
    if not isinstance(raw_sections, list):
        raise OutlineError(
            "That order did not name any sections. Reload the page and try again."
        )

    read: list[tuple[int | None, list[int]]] = []
    seen_folders: set[int | None] = set()
    for index, raw in enumerate(raw_sections, start=1):
        if not isinstance(raw, dict):
            raise OutlineError(f"Section {index} in that order was not readable.")
        folder = raw.get("folder")
        folder_id = None if folder is None else _as_int(folder, field=f"Section {index}")
        lessons = raw.get("lessons", [])
        if not isinstance(lessons, list):
            raise OutlineError(f"Section {index} in that order did not carry a list of classes.")
        read.append(
            (
                folder_id,
                [_as_int(value, field=f"A class in section {index}") for value in lessons],
            )
        )
        if folder_id in seen_folders:
            raise OutlineError("That order named the same section twice. Reload the page and try again.")
        seen_folders.add(folder_id)
    return read


def _validate_against_course(course, read: list[tuple[int | None, list[int]]]) -> None:
    """Refuse an order that does not describe *this* batch, completely.

    The check is deliberately an equality, not a subset: a payload missing a
    class would otherwise quietly leave that class at its old position, which is
    how an outline ends up with two "position 1" rows.
    """
    folder_ids = set(course.folders.values_list("pk", flat=True))
    named_folders = {folder for folder, _ in read if folder is not None}
    if named_folders != folder_ids:
        raise OutlineError(
            "Those sections no longer match this batch — somebody added or removed one. "
            "Reload the page to see the current outline.",
            code="stale",
        )

    lesson_ids = set(course.lessons.values_list("pk", flat=True))
    named_lessons = [lesson for _, lessons in read for lesson in lessons]
    if len(named_lessons) != len(set(named_lessons)):
        raise OutlineError("That order listed the same class twice. Reload the page and try again.")
    if set(named_lessons) != lesson_ids:
        raise OutlineError(
            "Those classes no longer match this batch — somebody added or removed one. "
            "Reload the page to see the current outline.",
            code="stale",
        )


def apply_order(course, payload) -> list[OutlineSection]:
    """Write this order to the batch, or refuse it and change nothing.

    The revision in the payload is compared inside the transaction, so a second
    editor's save either applies to the order they saw or is refused — never
    applied on top of a different one.
    """
    read = _read_sections(payload)
    revision = payload.get("revision")

    with transaction.atomic():
        current = build_outline(course)
        if revision is not None and revision != revision_of(current):
            raise OutlineError(
                "Someone else changed this outline while you were arranging it. "
                "Reload the page to see their order before saving yours.",
                code="conflict",
                status=409,
            )
        _validate_against_course(course, read)

        # Lock what is about to move: a concurrent save waits here rather than
        # interleaving two sets of positions.
        folders = {folder.pk: folder for folder in CourseFolder.objects.select_for_update().filter(course=course)}
        lessons = {lesson.pk: lesson for lesson in Lesson.objects.select_for_update().filter(course=course)}

        now = timezone.now()
        folder_rows = []
        lesson_rows = []
        folder_position = 0
        for folder_id, lesson_ids in read:
            if folder_id is not None:
                # The "no section" bucket is not a row in the database, so it
                # takes no number: the sections after it still count 0, 1, 2.
                folder = folders[folder_id]
                folder.position = folder_position
                folder.updated_at = now
                folder_rows.append(folder)
                folder_position += 1
            for position, lesson_id in enumerate(lesson_ids):
                lesson = lessons[lesson_id]
                lesson.folder_id = folder_id
                lesson.position = position
                lesson.updated_at = now
                lesson_rows.append(lesson)

        if folder_rows:
            CourseFolder.objects.bulk_update(folder_rows, ["position", "updated_at"])
        if lesson_rows:
            Lesson.objects.bulk_update(lesson_rows, ["folder", "position", "updated_at"])

    return build_outline(course)


def describe_outline(sections: list[OutlineSection]) -> dict:
    """The outline as the screen's JSON contract (used by the save response)."""
    return {
        "revision": revision_of(sections),
        "sections": [
            {
                "folder": section.folder_id,
                "title": section.title,
                "lessons": [{"id": lesson.pk, "title": lesson.title} for lesson in section.lessons],
            }
            for section in sections
        ],
    }
