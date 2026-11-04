"""Weak-topic analysis — P3.

The feature is one sentence long: *tell a learner which chapters are costing
them marks, computed from papers they actually sat*. These tests are written
against the two ways that sentence can become a lie:

1. **Reading the live question bank.** A chapter renamed or deleted after a
   paper was sat must not move the learner's numbers, because the numbers were
   measured against the paper that was served.
2. **Ranking noise.** A single guessed question is not a weakness, an
   unanswered chapter is not 0% accurate, and a chapter with no marked answers
   must sit at the bottom rather than the top of "worst first".

Everything else here guards the shape of the payload the profile screen reads.
"""

from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase
from rest_framework.test import APIClient

from accounts.models import Role
from courses import insights
from courses.models import Choice, Course, Question, Quiz, QuizAttempt

User = get_user_model()


class InsightsData(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner = User.objects.create_user(
            username="provider", email="p@example.com", password="TestPass123!", is_staff=True
        )
        cls.owner.profile.role = Role.SUB_ADMIN
        cls.owner.profile.save()
        cls.course = Course.objects.create(
            title="Batch", slug="batch", owner=cls.owner, is_published=True
        )
        cls.quiz = Quiz.objects.create(
            course=cls.course,
            title="Paper",
            is_published=True,
            marks_per_question=Decimal("4.00"),
            negative_marks_per_wrong=Decimal("1.00"),
            result_release_policy=Quiz.ResultReleasePolicy.IMMEDIATE,
        )
        cls.learner = User.objects.create_user(
            username="learner", email="l@example.com", password="TestPass123!"
        )
        cls.other = User.objects.create_user(
            username="other", email="o@example.com", password="TestPass123!"
        )
        cls.answers = {}

        def question(prompt, section, topic, position):
            item = Question.objects.create(
                quiz=cls.quiz, prompt=prompt, section=section, topic=topic,
                position=position, question_type=Question.QuestionType.SINGLE_CHOICE,
            )
            right = Choice.objects.create(question=item, text="right", is_correct=True, position=1)
            wrong = Choice.objects.create(question=item, text="wrong", is_correct=False, position=2)
            cls.answers[item.id] = {"right": right.id, "wrong": wrong.id}
            return item

        cls.k1 = question("Kinematics one", "Physics", "Kinematics", 1)
        cls.k2 = question("Kinematics two", "Physics", "Kinematics", 2)
        cls.k3 = question("Kinematics three", "Physics", "Kinematics", 3)
        cls.thermo = question("Thermodynamics one", "Physics", "Thermodynamics", 4)
        cls.blank = question("No chapter", "Physics", "", 5)

    def setUp(self):
        # Attempts are rate-limited per account and the counter lives in the
        # cache, which outlives a rolled-back test. Clearing it keeps this
        # class's many starts from tripping the limit for the next test.
        cache.clear()
        self.client = APIClient()
        self.client.force_authenticate(self.learner)

    # -- helpers ---------------------------------------------------------
    def sit(self, user=None, marks=None, submit=True, quiz=None):
        """Sit a paper as ``user`` and return the attempt.

        ``marks`` maps question -> "right" | "wrong" | None (left blank).
        """
        client = APIClient()
        if user is not None:
            client.force_authenticate(user)
        quiz = quiz or self.quiz
        started = client.post("/api/quizzes/start/", {"quiz_id": quiz.id}, format="json")
        self.assertEqual(started.status_code, 201, started.content)
        body = started.json()
        if user is None:
            # A guest addresses their own attempt by the opaque token only.
            client.credentials(HTTP_X_ATTEMPT_TOKEN=body["guest_token"])
        if not submit:
            return QuizAttempt.objects.get(pk=body["id"])

        answers = []
        for item, key in (marks or {}).items():
            answers.append(
                {
                    "question_id": item.id,
                    "choice_ids": [self.answers[item.id][key]] if key else [],
                }
            )
        submitted = client.post(
            f"/api/quiz-attempts/{body['id']}/submit/", {"answers": answers}, format="json"
        )
        self.assertEqual(submitted.status_code, 200, submitted.content)
        return QuizAttempt.objects.get(pk=body["id"])

    def insights(self, client=None):
        return (client or self.client).get("/api/insights/topics/")

    def topics(self, payload=None):
        payload = payload if payload is not None else self.insights().json()
        return {row["topic"]: row for row in payload["topics"]}

    # -- access ----------------------------------------------------------
    def test_signed_out_callers_are_refused(self):
        response = self.insights(client=APIClient())
        self.assertEqual(response.status_code, 401)

    def test_a_learner_with_no_papers_gets_an_empty_but_valid_payload(self):
        response = self.insights()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            {
                "released_attempts": 0,
                "questions": 0,
                "topics": [],
                "focus": [],
                "rules": {"min_answered": insights.MIN_ANSWERED, "weak_below": insights.WEAK_BELOW},
            },
        )

    # -- the maths -------------------------------------------------------
    def test_accuracy_is_measured_on_answered_questions_only(self):
        self.sit(
            self.learner,
            {self.k1: "right", self.k2: "wrong", self.k3: "wrong"},
        )
        topics = self.topics()

        kinematics = topics["Kinematics"]
        self.assertEqual(kinematics["correct"], 1)
        self.assertEqual(kinematics["incorrect"], 2)
        self.assertEqual(kinematics["answered"], 3)
        self.assertEqual(kinematics["unanswered"], 0)
        self.assertEqual(kinematics["questions"], 3)
        self.assertEqual(kinematics["accuracy"], 33.3)
        self.assertEqual(kinematics["attempts"], 1)

    def test_an_unanswered_chapter_has_no_accuracy_and_is_not_called_weak(self):
        self.sit(self.learner, {self.thermo: None, self.blank: None})
        topics = self.topics()

        self.assertIsNone(topics["Thermodynamics"]["accuracy"])
        self.assertEqual(topics["Thermodynamics"]["unanswered"], 1)
        self.assertEqual(topics["Unlabelled"]["questions"], 1)
        self.assertEqual(self.insights().json()["focus"], [])

    def test_a_chapter_needs_three_marked_answers_before_it_can_be_a_weakness(self):
        self.sit(self.learner, {self.thermo: "wrong"})
        payload = self.insights().json()

        self.assertEqual(payload["topics"][0]["topic"], "Thermodynamics")
        self.assertEqual(payload["focus"], [], "one wrong guess is not a weakness")

    def test_the_focus_list_is_the_weakest_ranked_chapters_first(self):
        self.sit(self.learner, {self.k1: "wrong", self.k2: "wrong", self.k3: "wrong"})
        payload = self.insights().json()

        self.assertEqual([row["topic"] for row in payload["focus"]], ["Kinematics"])
        self.assertEqual(payload["focus"][0]["accuracy"], 0.0)

    def test_chapters_are_grouped_across_papers_and_across_spelling(self):
        other_paper = Quiz.objects.create(
            course=self.course,
            title="Paper 2",
            is_published=True,
            marks_per_question=Decimal("4.00"),
            result_release_policy=Quiz.ResultReleasePolicy.IMMEDIATE,
        )
        Question.objects.create(
            quiz=other_paper, prompt="More kinematics", section="Physics",
            topic="  kinematics ", position=1,
        )
        # A second paper's attempt is what proves the aggregation spans papers.
        question = other_paper.questions.get()
        right = Choice.objects.create(question=question, text="right", is_correct=True, position=1)
        Choice.objects.create(question=question, text="wrong", is_correct=False, position=2)
        self.answers[question.id] = {"right": right.id}
        self.sit(self.learner, {question: "right"}, quiz=other_paper)

        self.sit(self.learner, {self.k1: "right", self.k2: "right", self.k3: "wrong"})

        kinematics = [row for row in self.insights().json()["topics"] if row["topic"].strip().lower() == "kinematics"]
        self.assertEqual(len(kinematics), 1, "one chapter, however it was spelled")
        self.assertEqual(kinematics[0]["attempts"], 2)
        self.assertEqual(kinematics[0]["correct"], 3)
        self.assertEqual(kinematics[0]["incorrect"], 1)
        self.assertEqual(kinematics[0]["accuracy"], 75.0)

    def test_the_numbers_follow_the_frozen_paper_not_the_question_bank(self):
        self.sit(self.learner, {self.k1: "right", self.k2: "wrong", self.k3: "wrong"})
        before = self.topics()

        self.k1.topic = "Renamed chapter"
        self.k1.save(update_fields=["topic"])
        self.k2.delete()

        after = self.topics()
        self.assertEqual(after["Kinematics"]["questions"], 3)
        self.assertEqual(after["Kinematics"]["accuracy"], before["Kinematics"]["accuracy"])
        self.assertNotIn("Renamed chapter", after)

    # -- who is counted ---------------------------------------------------
    def test_only_released_results_are_counted(self):
        attempt = self.sit(self.learner, {self.k1: "right", self.k2: "right", self.k3: "right"})
        self.assertEqual(self.insights().json()["released_attempts"], 1)

        attempt.result_released_at = None
        attempt.save(update_fields=["result_released_at"])

        payload = self.insights().json()
        self.assertEqual(payload["released_attempts"], 0)
        self.assertEqual(payload["topics"], [])

    def test_other_learners_papers_are_not_in_this_learners_profile(self):
        self.sit(self.other, {self.k1: "wrong", self.k2: "wrong", self.k3: "wrong"})
        self.sit(self.learner, {self.k1: "right", self.k2: "right", self.k3: "right"})

        payload = self.insights().json()
        self.assertEqual(payload["released_attempts"], 1)
        self.assertEqual(self.topics(payload)["Kinematics"]["accuracy"], 100.0)

    def test_guest_attempts_are_never_pooled_into_a_profile(self):
        self.sit(user=None, marks={self.k1: "wrong", self.k2: "wrong", self.k3: "wrong"})
        payload = self.insights().json()

        self.assertEqual(payload["released_attempts"], 0)
        self.assertEqual(payload["topics"], [])

    def test_an_attempt_still_open_is_not_counted(self):
        self.sit(self.learner, marks={}, submit=False)
        self.assertEqual(self.insights().json()["released_attempts"], 0)

    # -- the result payload the player reads ------------------------------
    def test_the_result_payload_carries_a_topic_breakdown_with_accuracy(self):
        attempt = self.sit(
            self.learner, {self.k1: "right", self.k2: "wrong", self.k3: "wrong"}
        )
        payload = self.client.get(f"/api/quiz-attempts/{attempt.id}/result/").json()

        self.assertNotIn("section_breakdown", payload)
        rows = {row["topic"]: row for row in payload["topic_breakdown"]}
        self.assertEqual(rows["Kinematics"]["accuracy"], 33.3)
        self.assertEqual(rows["Kinematics"]["score"], "2.00")
        self.assertEqual(rows["Kinematics"]["max_score"], "12.00")

    def test_the_answer_sheet_names_the_section_and_the_chapter(self):
        attempt = self.sit(self.learner, {self.k1: "right"})
        rows = self.client.get(f"/api/quiz-attempts/{attempt.id}/result/").json()["answers_detail"]
        first = rows[0]

        self.assertEqual(first["section"], "Physics")
        self.assertEqual(first["topic"], "Kinematics")

    def test_the_exam_window_receives_both_labels(self):
        started = self.client.post("/api/quizzes/start/", {"quiz_id": self.quiz.id}, format="json")
        payload = started.json()
        question = payload["paper"]["questions"][0]

        self.assertEqual(question["section"], "Physics")
        self.assertEqual(question["topic"], "Kinematics")
