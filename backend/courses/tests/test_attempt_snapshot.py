"""A sat attempt is a record, not a view — audit finding 2.

The acceptance criterion is blunt: *editing or deleting a question after a
student starts a test cannot change that student's paper, score, answer sheet or
explanations, and a submitted attempt remains reviewable after the question bank
is revised.*

So these tests start an attempt, then deliberately vandalise the question bank
— change the prompt, move the correct option, change the marks, delete the whole
question — and assert the attempt still grades and reviews as it did before.
"""

from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from accounts.models import Role
from courses.models import Choice, Course, Question, Quiz, QuizAttempt

User = get_user_model()


class SnapshotData(TestCase):
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
            pass_threshold_percent=Decimal("50.00"),
        )
        cls.q1 = Question.objects.create(
            quiz=cls.quiz, prompt="2 + 2 = ?", question_type=Question.QuestionType.SINGLE_CHOICE,
            topic="Arithmetic", position=1, explanation="Two and two make four.",
        )
        cls.q1_right = Choice.objects.create(question=cls.q1, text="4", is_correct=True, position=1)
        cls.q1_wrong = Choice.objects.create(question=cls.q1, text="5", is_correct=False, position=2)

        cls.q2 = Question.objects.create(
            quiz=cls.quiz, prompt="Which are primes?", question_type=Question.QuestionType.MULTIPLE_CHOICE,
            topic="Number theory", position=2, marks=Decimal("2.00"),
        )
        cls.q2_a = Choice.objects.create(question=cls.q2, text="2", is_correct=True, position=1)
        cls.q2_b = Choice.objects.create(question=cls.q2, text="3", is_correct=True, position=2)
        cls.q2_c = Choice.objects.create(question=cls.q2, text="4", is_correct=False, position=3)

    def setUp(self):
        self.client = APIClient()

    def start(self):
        """Start as a guest and keep the token — the paper is addressed by it."""
        response = self.client.post("/api/quizzes/start/", {"quiz_id": self.quiz.id}, format="json")
        self.assertEqual(response.status_code, 201, response.content)
        body = response.json()
        self.client.credentials(HTTP_X_ATTEMPT_TOKEN=body["guest_token"])
        return body

    def submit(self, attempt_id, answers):
        return self.client.post(
            f"/api/quiz-attempts/{attempt_id}/submit/", {"answers": answers}, format="json"
        )

    def result(self, attempt_id):
        return self.client.get(f"/api/quiz-attempts/{attempt_id}/result/")


class AttemptSnapshotTests(SnapshotData):
    def test_start_freezes_the_whole_paper(self):
        payload = self.start()
        attempt = QuizAttempt.objects.get(pk=payload["id"])
        paper = attempt.paper_snapshot

        self.assertEqual(paper["version"], 1)
        self.assertEqual(paper["quiz"]["marks_per_question"], "4.00")
        self.assertEqual(paper["quiz"]["pass_threshold_percent"], "50.00")
        self.assertEqual([entry["id"] for entry in paper["questions"]], [self.q1.id, self.q2.id])
        first = paper["questions"][0]
        self.assertEqual(first["prompt"], "2 + 2 = ?")
        self.assertEqual(first["explanation"], "Two and two make four.")
        self.assertEqual(first["topic"], "Arithmetic")
        self.assertEqual(
            [(choice["text"], choice["is_correct"]) for choice in first["choices"]],
            [("4", True), ("5", False)],
        )

    def test_the_paper_endpoint_never_carries_the_key_or_the_solution(self):
        """Both are disclosed only through a released result.

        The attempt payload is fetchable mid-test, so an explanation here would
        ship the worked answer with the question.
        """
        payload = self.start()
        for question in payload["paper"]["questions"]:
            self.assertNotIn("explanation", question)
            for choice in question["choices"]:
                self.assertNotIn("is_correct", choice)

        unreleased = self.client.get(f"/api/quiz-attempts/{payload['id']}/")
        self.assertEqual(unreleased.status_code, 200, unreleased.content)
        self.assertNotIn("Two and two make four.", unreleased.content.decode())

    def test_editing_the_key_after_start_does_not_rescore(self):
        payload = self.start()
        attempt_id = payload["id"]

        # The provider changes the correct answer and both marks.
        self.q1_right.is_correct = False
        self.q1_right.save(update_fields=["is_correct"])
        self.q1_wrong.is_correct = True
        self.q1_wrong.save(update_fields=["is_correct"])
        self.q1.marks = Decimal("99.00")
        self.q1.save(update_fields=["marks"])

        response = self.submit(
            attempt_id, [{"question_id": self.q1.id, "choice_ids": [self.q1_right.id]}]
        )
        self.assertEqual(response.status_code, 200, response.content)
        body = response.json()
        # 4 marks for q1 + 0 for unanswered q2 (2 marks max) = 6 total.
        self.assertEqual(Decimal(body["score"]), Decimal("4.00"))
        self.assertEqual(Decimal(body["max_score"]), Decimal("6.00"))
        self.assertEqual(body["correct_count"], 1)
        self.assertEqual(body["incorrect_count"], 0)

    def test_rewording_the_prompt_does_not_rewrite_the_answer_sheet(self):
        payload = self.start()
        attempt_id = payload["id"]
        self.submit(attempt_id, [{"question_id": self.q1.id, "choice_ids": [self.q1_right.id]}])

        self.q1.prompt = "Something else entirely"
        self.q1.explanation = "A new explanation"
        self.q1.save(update_fields=["prompt", "explanation"])
        self.q1_right.text = "Forty"
        self.q1_right.save(update_fields=["text"])

        sheet = self.result(attempt_id).json()["answers_detail"]
        row = next(row for row in sheet if row["question"] == self.q1.id)
        self.assertEqual(row["prompt"], "2 + 2 = ?")
        self.assertEqual(row["explanation"], "Two and two make four.")
        self.assertEqual([choice["text"] for choice in row["selected_choices"]], ["4"])
        self.assertTrue(row["is_correct"])

    def test_deleting_a_question_keeps_the_score_and_the_answer_sheet(self):
        payload = self.start()
        attempt_id = payload["id"]
        self.submit(attempt_id, [{"question_id": self.q1.id, "choice_ids": [self.q1_right.id]}])

        self.q1.delete()

        result = self.result(attempt_id)
        self.assertEqual(result.status_code, 200, result.content)
        body = result.json()
        # The deleted question still counts for and against the score.
        self.assertEqual(Decimal(body["score"]), Decimal("4.00"))
        self.assertEqual(Decimal(body["max_score"]), Decimal("6.00"))

        sheet = body["answers_detail"]
        row = next(row for row in sheet if row["prompt"] == "2 + 2 = ?")
        self.assertTrue(row["is_correct"])
        self.assertEqual([choice["text"] for choice in row["selected_choices"]], ["4"])
        self.assertEqual(row["correct_choices"][0]["text"], "4")

        # And the answer row itself survived the cascade.
        attempt = QuizAttempt.objects.get(pk=attempt_id)
        self.assertEqual(attempt.answers.count(), 2)

    def test_deleting_the_whole_question_bank_keeps_the_attempt(self):
        payload = self.start()
        attempt_id = payload["id"]
        self.submit(
            attempt_id,
            [
                {"question_id": self.q1.id, "choice_ids": [self.q1_right.id]},
                {"question_id": self.q2.id, "choice_ids": [self.q2_a.id, self.q2_b.id]},
            ],
        )
        Question.objects.filter(quiz=self.quiz).delete()

        body = self.result(attempt_id).json()
        self.assertEqual(Decimal(body["score"]), Decimal("6.00"))
        self.assertEqual(Decimal(body["max_score"]), Decimal("6.00"))
        self.assertEqual(len(body["answers_detail"]), 2)

    def test_a_choice_added_after_start_is_not_a_valid_answer(self):
        payload = self.start()
        late = Choice.objects.create(question=self.q1, text="22", is_correct=True, position=3)

        response = self.submit(
            payload["id"], [{"question_id": self.q1.id, "choice_ids": [late.id]}]
        )
        self.assertEqual(response.status_code, 400, response.content)

    def test_autosave_refuses_a_choice_outside_the_frozen_paper(self):
        payload = self.start()
        late = Choice.objects.create(question=self.q1, text="22", is_correct=False, position=3)

        response = self.client.post(
            f"/api/quiz-attempts/{payload['id']}/autosave/",
            {"question_id": self.q1.id, "choice_ids": [late.id]},
            format="json",
        )
        self.assertEqual(response.status_code, 400, response.content)

    def test_a_deleted_option_cannot_be_submitted_later(self):
        payload = self.start()
        self.q1_wrong.delete()
        response = self.submit(
            payload["id"], [{"question_id": self.q1.id, "choice_ids": [self.q1_wrong.id]}]
        )
        self.assertEqual(response.status_code, 400, response.content)

    def test_the_pass_mark_is_the_one_frozen_at_start(self):
        payload = self.start()
        self.quiz.pass_threshold_percent = Decimal("99.00")
        self.quiz.save(update_fields=["pass_threshold_percent"])
        self.submit(payload["id"], [{"question_id": self.q1.id, "choice_ids": [self.q1_right.id]}])

        body = self.result(payload["id"]).json()
        # 4 of 6 = 67%, which passed under the 50% that was in force.
        self.assertTrue(body["passed"])

    def test_an_edited_question_does_not_change_what_was_served(self):
        payload = self.start()
        self.q1.prompt = "Changed while you were reading"
        self.q1.save(update_fields=["prompt"])

        resumed = self.client.get(f"/api/quiz-attempts/{payload['id']}/").json()
        prompts = [question["prompt"] for question in resumed["paper"]["questions"]]
        self.assertEqual(prompts, ["2 + 2 = ?", "Which are primes?"])
