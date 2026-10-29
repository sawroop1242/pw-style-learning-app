"""Seed a small catalogue so the front end can be exercised against the real API.

The bundled fixtures in ``frontend/assets/js/data.js`` keep the preview useful
when the API is unreachable, but they cannot prove that a page renders *live*
data. This command creates enough real rows for that: published courses with
folders, lessons and chapter PDFs, plus test series, timed quizzes, questions
and choices.

Design notes
------------
* **Idempotent.** Every row is keyed by a stable slug or title, so running the
  command twice updates rather than duplicates.
* **Removable.** Everything it creates has a ``demo-`` slug prefix; ``--clear``
  deletes exactly those rows and nothing else.
* **No dead links.** One known-good embed URL is attached to the first lesson
  of a free batch and of a paid batch; every other lesson carries no
  ``video_url``. The paid one stays out of the public payload, so the lock path
  is exercised against the same URL the free one serves.
* **Sit-able anonymously, without breaking the paywall.** A test is readable
  when it hangs off a published series (or a published *free* course). The
  demo therefore attaches the SSC CGL mock to its free course and keeps the
  rest on their series, so no paid paper is published. Paid-course media stays
  locked in the public payload, which is the behaviour worth seeing.

Usage::

    python manage.py seed_demo          # create or refresh the demo rows
    python manage.py seed_demo --clear  # remove them
"""

from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from courses.models import (
    Choice,
    CommunityPost,
    Course,
    CourseFaculty,
    CourseFolder,
    Lesson,
    PdfResource,
    Question,
    Quiz,
    TestSeries,
)

User = get_user_model()

SLUG_PREFIX = "demo-"

# --------------------------------------------------------------------------
# A real, playable recording. Attached to the first lesson of a *free* batch so
# an anonymous visitor can open the player and watch it, and to the first
# lesson of a *paid* batch where the same URL must stay locked in the public
# payload. Using one URL for both is the point: the difference is the grant,
# not the media.
# --------------------------------------------------------------------------

DEMO_VIDEO_URL = "https://embed.vcdn.me/embed/28c4af9f-d817-460a-80ab-9a09f8c47c69"

LESSON_VIDEOS = {
    ("demo-ssc-cgl-2026", "Series and analogy"): DEMO_VIDEO_URL,
    ("demo-class-10-science", "Types of reactions"): DEMO_VIDEO_URL,
    ("demo-jee-main-2027", "Units, dimensions and errors"): DEMO_VIDEO_URL,
}

# --------------------------------------------------------------------------
# Faculty and notices. Names are invented for this project — no real teacher
# is referenced, and no photograph is borrowed. A batch page that lists
# "Faculty: none" is a screen with a feature missing, not a design choice.
# --------------------------------------------------------------------------

FACULTY = {
    "demo-jee-main-2027": [
        ("Dr. Meera Kulkarni", "Physics", "Twelve years of JEE coaching; writes the weekly problem sets."),
        ("Anil Bhatt", "Mathematics", "Focuses on calculus and coordinate geometry shortcuts."),
    ],
    "demo-neet-2027-biology": [
        ("Dr. Ritu Sharma", "Biology", "NCERT-first teaching with diagram-heavy revision."),
    ],
    "demo-ssc-cgl-2026": [
        ("Vikas Yadav", "Reasoning", "Pattern-based reasoning drills for tier 1 and tier 2."),
        ("Neha Goel", "Quantitative Aptitude", "Speed maths and accuracy practice."),
    ],
    "demo-bank-po-2026": [
        ("Sandeep Rao", "Quantitative Aptitude", "Data interpretation and arithmetic for bank exams."),
    ],
    "demo-class-10-science": [
        ("Priya Nair", "Science", "Board-exam preparation with practical demonstrations."),
    ],
    "demo-gate-cs-2027": [
        ("Arjun Menon", "Computer Science", "Algorithms, operating systems and GATE problem patterns."),
    ],
}

ANNOUNCEMENTS = [
    (
        "Mock test schedule for this fortnight",
        "Two full-length papers are open this week. Both are timed, scored on the "
        "server, and the solution review unlocks the moment you submit.",
        True,
    ),
    (
        "Chapter PDFs are live",
        "Formula sheets and revision notes for the published chapters are in "
        "Downloads. They stay available offline once opened.",
        False,
    ),
]

# --------------------------------------------------------------------------
# Catalogue content. Every title, topic and question here is written for this
# project; nothing is copied from another platform.
# --------------------------------------------------------------------------

COURSES = [
    {
        "slug": "demo-jee-main-2027",
        "title": "JEE Main 2027 Complete Batch",
        "subject": "Physics",
        "description": (
            "A full-year physics-first batch for JEE Main: mechanics through modern "
            "physics, weekly problem sets and a mock every fortnight."
        ),
        "pricing_mode": Course.PricingMode.PAID,
        "price": Decimal("4499.00"),
        "telegram_handle": "@studyspace_access",
        "folders": [
            {
                "title": "Mechanics",
                "lessons": [
                    ("Units, dimensions and errors", 52),
                    ("Kinematics in one dimension", 64),
                    ("Newton's laws and friction", 71),
                ],
            },
            {
                "title": "Modern Physics",
                "lessons": [
                    ("Photoelectric effect", 48),
                    ("Bohr model and spectra", 55),
                ],
            },
        ],
        "pdfs": ["Mechanics formula sheet", "Modern physics revision notes"],
    },
    {
        "slug": "demo-neet-2027-biology",
        "title": "NEET 2027 Biology Booster",
        "subject": "Biology",
        "description": (
            "NCERT-anchored biology with diagram drills, assertion-reason practice "
            "and a chapter test after every unit."
        ),
        "pricing_mode": Course.PricingMode.PAID,
        "price": Decimal("3499.00"),
        "telegram_handle": "@studyspace_access",
        "folders": [
            {
                "title": "Cell Biology",
                "lessons": [
                    ("Cell structure and organelles", 58),
                    ("Cell cycle and division", 62),
                ],
            },
            {
                "title": "Human Physiology",
                "lessons": [("Breathing and exchange of gases", 66)],
            },
        ],
        "pdfs": ["Cell biology diagram bank"],
    },
    {
        "slug": "demo-ssc-cgl-2026",
        "title": "SSC CGL 2026 Foundation",
        "subject": "Reasoning",
        "description": (
            "Tier 1 and Tier 2 preparation with daily reasoning sets, English "
            "vocabulary drills and section-wise mocks."
        ),
        "pricing_mode": Course.PricingMode.FREE,
        "price": Decimal("0.00"),
        "folders": [
            {
                "title": "General Intelligence",
                "lessons": [
                    ("Series and analogy", 41),
                    ("Coding-decoding", 38),
                    ("Syllogism", 44),
                ],
            },
            {
                "title": "English",
                "lessons": [("Error spotting", 36)],
            },
        ],
        "pdfs": ["Reasoning practice set 1"],
    },
    {
        "slug": "demo-bank-po-2026",
        "title": "Bank PO 2026 Prelims",
        "subject": "English",
        "description": (
            "Prelims-focused bank batch: quant shortcuts, reasoning puzzles and "
            "reading comprehension under time pressure."
        ),
        "pricing_mode": Course.PricingMode.PAID,
        "price": Decimal("1999.00"),
        "telegram_handle": "@studyspace_access",
        "folders": [
            {
                "title": "Quantitative Aptitude",
                "lessons": [
                    ("Percentage and ratio", 47),
                    ("Time, speed and distance", 53),
                ],
            }
        ],
        "pdfs": ["Quant shortcut sheet"],
    },
    {
        "slug": "demo-class-10-science",
        "title": "Class 10 Science Crash Course",
        "subject": "Chemistry",
        "description": (
            "Board exam revision in six weeks: every chapter summarised, plus "
            "previous-year questions worked out step by step."
        ),
        "pricing_mode": Course.PricingMode.FREE,
        "price": Decimal("0.00"),
        "folders": [
            {
                "title": "Chemical Reactions",
                "lessons": [
                    ("Types of reactions", 34),
                    ("Balancing equations", 39),
                ],
            },
            {
                "title": "Light",
                "lessons": [("Reflection and refraction", 42)],
            },
        ],
        "pdfs": ["Class 10 science revision map"],
    },
    {
        "slug": "demo-gate-cs-2027",
        "title": "GATE CS 2027",
        "subject": "Computer",
        "description": (
            "Computer science for GATE: algorithms, operating systems, databases "
            "and theory, with a subject test every week."
        ),
        "pricing_mode": Course.PricingMode.PAID,
        "price": Decimal("5999.00"),
        "telegram_handle": "@studyspace_access",
        "folders": [
            {
                "title": "Algorithms",
                "lessons": [
                    ("Asymptotic analysis", 61),
                    ("Greedy and dynamic programming", 74),
                ],
            },
            {
                "title": "Databases",
                "lessons": [("Normalisation and indexing", 68)],
            },
        ],
        "pdfs": ["Algorithms cheat sheet"],
    },
]

SERIES = [
    {
        "slug": "demo-jee-mocks",
        "title": "JEE Main Mock Series 2027",
        "subject": "Physics",
        "description": "Full-length JEE Main mocks with the real exam interface and section-wise analysis.",
        "tests": [
            {
                "title": "JEE Main Full Mock #12",
                "duration": 180,
                "marks": 4,
                "negative": 1,
                "topics": ["Physics", "Chemistry", "Mathematics"],
                "questions": [
                    (
                        "Physics",
                        "A body of mass 2 kg moves with a velocity of 3 m/s. What is its kinetic energy?",
                        ["4.5 J", "9 J", "18 J", "36 J"],
                        1,
                        "Kinetic energy is ½mv². With m = 2 kg and v = 3 m/s it is ½ × 2 × 9 = 9 J.",
                    ),
                    (
                        "Physics",
                        "The SI unit of electric flux is:",
                        ["N·m²/C", "V/m", "C/m²", "N/C"],
                        0,
                        "Flux Φ = E·A, so the unit is (N/C)·m² = N·m²/C.",
                    ),
                    (
                        "Chemistry",
                        "Which element has the highest first ionisation enthalpy?",
                        ["Na", "Mg", "Al", "Si"],
                        3,
                        "Ionisation enthalpy rises across a period, so silicon is highest of the four.",
                    ),
                    (
                        "Chemistry",
                        "The hybridisation of carbon in benzene is:",
                        ["sp³", "sp²", "sp", "sp³d"],
                        1,
                        "Each carbon in benzene forms three σ bonds and one π bond, so it is sp².",
                    ),
                    (
                        "Mathematics",
                        "If f(x) = x² − 4x + 4, the number of distinct real roots of f(x) = 0 is:",
                        ["0", "1", "2", "Infinite"],
                        1,
                        "The discriminant is 16 − 16 = 0, giving one repeated real root at x = 2.",
                    ),
                    (
                        "Mathematics",
                        "The value of ∫₀¹ 2x dx is:",
                        ["1", "2", "0.5", "4"],
                        0,
                        "∫₀¹ 2x dx = [x²]₀¹ = 1.",
                    ),
                ],
            },
            {
                "title": "JEE Main Sectional — Mechanics",
                "duration": 45,
                "marks": 4,
                "negative": 1,
                "topics": ["Physics"],
                "questions": [
                    (
                        "Physics",
                        "A block slides down a frictionless incline of 30°. With g = 10 m/s², its acceleration along the incline is:",
                        ["2.5 m/s²", "5 m/s²", "8.7 m/s²", "10 m/s²"],
                        1,
                        "The along-incline component is g·sinθ = 10 × 0.5 = 5 m/s².",
                    ),
                    (
                        "Physics",
                        "A body moves in a circle at constant speed. Which quantity stays constant?",
                        ["Velocity", "Acceleration", "Speed", "Momentum"],
                        2,
                        "Speed is the magnitude of velocity; direction, velocity, acceleration and momentum all change.",
                    ),
                    (
                        "Physics",
                        "The work done by a force perpendicular to displacement is:",
                        ["Maximum", "Minimum but non-zero", "Zero", "Negative"],
                        2,
                        "W = F·s·cosθ and cos 90° = 0, so no work is done.",
                    ),
                ],
            },
        ],
    },
    {
        "slug": "demo-ssc-mocks",
        "title": "SSC CGL Tier I Mocks",
        "subject": "Reasoning",
        "description": "Tier I pattern mocks with reasoning, quant, English and general awareness sections.",
        "course": "demo-ssc-cgl-2026",
        "tests": [
            {
                "title": "SSC CGL Tier I — Full Mock 4",
                "duration": 60,
                "marks": 2,
                "negative": 0.5,
                "topics": ["Reasoning", "English"],
                "questions": [
                    (
                        "Reasoning",
                        "Find the next term: 2, 6, 12, 20, 30, ?",
                        ["36", "40", "42", "44"],
                        2,
                        "Differences are 4, 6, 8, 10, 12, so the next term is 30 + 12 = 42.",
                    ),
                    (
                        "Reasoning",
                        "If CAT is coded as 3-1-20, how is DOG coded?",
                        ["4-15-7", "4-14-7", "3-15-7", "4-15-8"],
                        0,
                        "Each letter is replaced by its alphabet position: D = 4, O = 15, G = 7.",
                    ),
                    (
                        "English",
                        "Choose the correctly spelt word.",
                        ["Occassion", "Ocassion", "Occasion", "Ocasion"],
                        2,
                        "The correct spelling takes a double c and a single s.",
                    ),
                ],
            }
        ],
    },
    {
        "slug": "demo-neet-mocks",
        "title": "NEET Biology Sectionals",
        "subject": "Biology",
        "description": "Chapter-level biology tests with explanations for every option.",
        "tests": [
            {
                "title": "NEET Biology — Cell Biology",
                "duration": 30,
                "marks": 4,
                "negative": 1,
                "topics": ["Biology"],
                "questions": [
                    (
                        "Biology",
                        "Which organelle is the primary site of ATP synthesis in a eukaryotic cell?",
                        ["Ribosome", "Mitochondrion", "Golgi body", "Lysosome"],
                        1,
                        "Oxidative phosphorylation happens on the inner mitochondrial membrane.",
                    ),
                    (
                        "Biology",
                        "DNA replication in a eukaryotic cell occurs during:",
                        ["G1 phase", "S phase", "G2 phase", "M phase"],
                        1,
                        "DNA is duplicated in the synthesis (S) phase of interphase.",
                    ),
                    (
                        "Biology",
                        "The fluid mosaic model describes the structure of the:",
                        ["Cell wall", "Plasma membrane", "Nucleolus", "Ribosome"],
                        1,
                        "The model describes proteins floating in a phospholipid bilayer.",
                    ),
                ],
            }
        ],
    },
    {
        "slug": "demo-bank-mocks",
        "title": "Bank PO Prelims Mocks",
        "subject": "English",
        "description": "Prelims mocks with quant and English, scored the way the real exam scores.",
        "tests": [
            {
                "title": "Bank PO Prelims — Mock 7",
                "duration": 60,
                "marks": 1,
                "negative": 0.25,
                "topics": ["Quantitative Aptitude", "English"],
                "questions": [
                    (
                        "Quantitative Aptitude",
                        "A sum doubles in 8 years at simple interest. What is the annual rate?",
                        ["10%", "12.5%", "15%", "8%"],
                        1,
                        "Simple interest equal to the principal over 8 years means rate × 8 = 100, so 12.5%.",
                    ),
                    (
                        "Quantitative Aptitude",
                        "The ratio of 45 minutes to 2 hours is:",
                        ["3 : 8", "3 : 4", "2 : 5", "1 : 3"],
                        0,
                        "2 hours is 120 minutes, and 45 : 120 reduces to 3 : 8.",
                    ),
                    (
                        "English",
                        "Pick the synonym of 'diligent'.",
                        ["Careless", "Hard-working", "Lazy", "Hasty"],
                        1,
                        "Diligent means showing steady, careful effort.",
                    ),
                ],
            }
        ],
    },
]


class Command(BaseCommand):
    help = "Create or refresh a demo catalogue (courses, series, quizzes) for local testing."

    def add_arguments(self, parser):
        parser.add_argument(
            "--clear",
            action="store_true",
            help="Delete the demo rows instead of creating them.",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        if options["clear"]:
            self._clear()
            return

        courses = self._courses()
        series, tests = self._series(courses)
        faculty, notices = self._faculty_and_notices()

        self.stdout.write(
            self.style.SUCCESS(
                f"Demo catalogue ready — {courses} courses, {series} test series, "
                f"{tests} tests, {faculty} faculty rows, {notices} announcements."
            )
        )
        self.stdout.write(
            "Quizzes sit on published free courses (or public series), so an anonymous "
            "visitor can open the paper."
        )

    # ------------------------------------------------------------------ #

    def _faculty_and_notices(self):
        """Faculty rows and two platform announcements.

        Announcements need an author. This command does not create accounts, so
        it uses (or creates) one clearly-named system author with an unusable
        password: it owns demo notices and nothing else, and cannot be signed
        into.
        """
        faculty_count = CourseFaculty.objects.filter(
            course__slug__startswith=SLUG_PREFIX
        ).count()

        author, created = User.objects.get_or_create(
            username="studyspace_demo_team",
            defaults={"email": "demo@studyspace.example"},
        )
        if created:
            author.set_unusable_password()
            author.save(update_fields=["password"])

        notice_count = 0
        for index, (title, body, pinned) in enumerate(ANNOUNCEMENTS, start=1):
            CommunityPost.objects.update_or_create(
                title=title,
                defaults={
                    "body": body,
                    "author": author,
                    "is_published": True,
                    "is_pinned": pinned and index == 1,
                    "course": None,
                },
            )
            notice_count += 1

        return faculty_count, notice_count

    def _clear(self):
        """Delete only rows this command owns — the ``demo-`` slug prefix.

        Quizzes, folders, lessons, PDFs, questions and choices all cascade from
        a course or a series, so two deletes are enough. A quiz is removed when
        *either* parent is a demo row, so the filter covers both.
        """
        courses = Course.objects.filter(slug__startswith=SLUG_PREFIX)
        series = TestSeries.objects.filter(slug__startswith=SLUG_PREFIX)
        quiz_filter = Q(series__in=series) | Q(course__in=courses)

        course_count = courses.count()
        series_count = series.count()
        quiz_count = Quiz.objects.filter(quiz_filter).distinct().count()

        notice_count = CommunityPost.objects.filter(title__in=[a[0] for a in ANNOUNCEMENTS]).count()

        Quiz.objects.filter(quiz_filter).delete()
        courses.delete()
        series.delete()
        CommunityPost.objects.filter(title__in=[a[0] for a in ANNOUNCEMENTS]).delete()

        # The system author exists only to own those notices.
        User.objects.filter(username="studyspace_demo_team", community_posts__isnull=True).delete()

        self.stdout.write(
            self.style.SUCCESS(
                f"Removed demo data — {course_count} courses, {series_count} test series, "
                f"{quiz_count} tests, {notice_count} announcements."
            )
        )

    def _courses(self):
        for position, spec in enumerate(COURSES, start=1):
            course, _ = Course.objects.update_or_create(
                slug=spec["slug"],
                defaults={
                    "title": spec["title"],
                    "description": spec["description"],
                    "subject": spec["subject"],
                    "pricing_mode": spec["pricing_mode"],
                    "price": spec["price"],
                    "currency": "INR",
                    "telegram_handle": spec.get("telegram_handle", ""),
                    "is_published": True,
                    "position": position,
                },
            )
            course.full_clean()

            folder_titles = []
            for folder_position, folder_spec in enumerate(spec["folders"], start=1):
                folder, _ = CourseFolder.objects.update_or_create(
                    course=course,
                    title=folder_spec["title"],
                    defaults={"position": folder_position},
                )
                folder_titles.append(folder)
                for lesson_position, (title, minutes) in enumerate(
                    folder_spec["lessons"], start=1
                ):
                    Lesson.objects.update_or_create(
                        course=course,
                        folder=folder,
                        title=title,
                        defaults={
                            "duration_minutes": minutes,
                            "position": lesson_position,
                            "is_published": True,
                            "video_url": LESSON_VIDEOS.get((spec["slug"], title), ""),
                        },
                    )

            for faculty_position, (name, subject, bio) in enumerate(
                FACULTY.get(spec["slug"], []), start=1
            ):
                CourseFaculty.objects.update_or_create(
                    course=course,
                    name=name,
                    defaults={
                        "subject": subject,
                        "bio": bio,
                        "position": faculty_position,
                    },
                )

            # Chapter PDFs live in the first folder; protected, so the public
            # payload carries the lock rather than a URL that would 404.
            first_folder = folder_titles[0]
            for pdf_position, title in enumerate(spec["pdfs"], start=1):
                PdfResource.objects.update_or_create(
                    folder=first_folder,
                    title=title,
                    defaults={
                        "file_url": f"https://files.studyspace.example/{spec['slug']}/{pdf_position}.pdf",
                        "position": pdf_position,
                        "is_published": True,
                        "is_protected": True,
                    },
                )

        return len(COURSES)

    def _series(self, _courses):
        course_by_slug = {
            course.slug: course
            for course in Course.objects.filter(slug__startswith=SLUG_PREFIX)
        }
        test_count = 0

        for spec in SERIES:
            series, _ = TestSeries.objects.update_or_create(
                slug=spec["slug"],
                defaults={
                    "title": spec["title"],
                    "description": spec["description"],
                    "subject": spec["subject"],
                    "is_published": True,
                },
            )

            for test_spec in spec["tests"]:
                quiz, _ = Quiz.objects.update_or_create(
                    series=series,
                    title=test_spec["title"],
                    defaults={
                        "course": course_by_slug.get(spec.get("course")),
                        "description": (
                            f"{len(test_spec['questions'])} questions · "
                            f"{test_spec['duration']} minutes · "
                            f"+{test_spec['marks']} for a correct answer, "
                            f"−{test_spec['negative']} for a wrong one."
                        ),
                        "instructions": (
                            "The paper is timed. Every question is scored on the server; "
                            "an expired timer submits the attempt automatically."
                        ),
                        "timing_mode": Quiz.TimingMode.TIMED,
                        "duration_minutes": test_spec["duration"],
                        "marks_per_question": Decimal(str(test_spec["marks"])),
                        "negative_marks_per_wrong": Decimal(str(test_spec["negative"])),
                        "result_release_policy": Quiz.ResultReleasePolicy.IMMEDIATE,
                        "shuffle_questions": False,
                        "is_published": True,
                        "opens_at": timezone.now() - timedelta(days=1),
                    },
                )

                for position, (topic, prompt, options, correct, explanation) in enumerate(
                    test_spec["questions"], start=1
                ):
                    question, _ = Question.objects.update_or_create(
                        quiz=quiz,
                        position=position,
                        defaults={
                            "prompt": prompt,
                            "explanation": explanation,
                            "question_type": Question.QuestionType.SINGLE_CHOICE,
                            "topic": topic,
                            "difficulty": Question.Difficulty.MEDIUM,
                        },
                    )
                    for choice_position, text in enumerate(options):
                        Choice.objects.update_or_create(
                            question=question,
                            position=choice_position,
                            defaults={
                                "text": text,
                                "is_correct": choice_position == correct,
                            },
                        )
                test_count += 1

        return len(SERIES), test_count
