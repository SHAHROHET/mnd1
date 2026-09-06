import os
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "backend"))

from analytics import AnalyticsStore, PROFILE_CATEGORIES


class TestAnalyticsStore(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.store = AnalyticsStore(os.path.join(self.temp_dir.name, "analytics.sqlite"))

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_conversations_and_calendar_periods(self):
        now = datetime(2026, 9, 6, 2, 0, tzinfo=timezone.utc)
        self.store.record_chat("user-1", "conversation-1", "Question one", "Carer", now)
        self.store.record_chat("user-1", "conversation-1", "Question two", "Carer", now)
        self.store.record_chat("user-1", "conversation-2", "Question one", "Carer", now)
        self.store.record_chat(
            "user-2", "conversation-3", "Question three", "Other",
            datetime(2026, 8, 31, 15, 0, tzinfo=timezone.utc),
        )
        self.store.record_chat(
            "user-3", "conversation-4", "Question four", "Other",
            datetime(2026, 8, 30, 13, 0, tzinfo=timezone.utc),
        )

        totals = self.store.get_aggregates(now)["total_conversations"]
        self.assertEqual(totals, {"this_week": 3, "this_month": 3, "all_time": 4})

    def test_questions_normalize_and_count_within_conversation(self):
        now = datetime(2026, 9, 6, 2, 0, tzinfo=timezone.utc)
        self.store.record_chat("user-1", "conversation-1", "What are MND symptoms?", "Carer", now)
        self.store.record_chat("user-2", "conversation-2", " what ARE mnd symptoms! ", "Carer", now)
        self.store.record_chat("user-1", "conversation-1", "What are MND symptoms?", "Carer", now)

        popular = self.store.get_aggregates(now)["popular_questions"]
        self.assertEqual(popular[0], {"question": "what are mnd symptoms", "count": 3})

    def test_popular_questions_are_limited_to_top_ten(self):
        now = datetime(2026, 9, 6, 2, 0, tzinfo=timezone.utc)
        for index in range(11):
            self.store.record_chat(
                f"user-{index}", f"conversation-{index}", f"Question {index}", "Other", now
            )
        self.assertEqual(len(self.store.get_aggregates(now)["popular_questions"]), 10)

    def test_profile_counts_unique_users_and_uses_existing_categories(self):
        now = datetime(2026, 9, 6, 2, 0, tzinfo=timezone.utc)
        self.store.record_chat("user-1", "conversation-1", "Question", "Carer", now)
        self.store.record_chat("user-1", "conversation-2", "Question", "Carer", now)
        self.store.record_chat("user-2", "conversation-3", "Question", "Carer", now)
        self.store.record_chat("user-3", "conversation-4", "Question", "Other", now)

        categories = self.store.get_aggregates(now)["profile_categories"]
        self.assertEqual([item["category"] for item in categories], list(PROFILE_CATEGORIES))
        counts = {item["category"]: item["count"] for item in categories}
        self.assertEqual(counts["Carer"], 2)
        self.assertEqual(counts["Other"], 1)
        self.assertEqual(counts["Client/Participant"], 0)

    def test_private_questions_are_not_stored(self):
        now = datetime(2026, 9, 6, 2, 0, tzinfo=timezone.utc)
        self.store.record_chat("user-1", "conversation-1", "My email is person@example.com", "Other", now)
        self.store.record_chat("user-2", "conversation-2", "What is MND?", "Other", now)
        questions = self.store.get_aggregates(now)["popular_questions"]
        self.assertEqual(questions, [{"question": "what is mnd", "count": 1}])

    def test_feedback_counts_and_prevents_duplicate_vote(self):
        now = datetime(2026, 9, 6, 2, 0, tzinfo=timezone.utc)
        self.store.record_feedback("user-1", "response-1", "like", now)
        self.store.record_feedback("user-1", "response-1", "dislike", now)
        self.store.record_feedback("user-2", "response-2", "like", now)
        self.assertEqual(self.store.get_aggregates(now)["feedback"], {"likes": 1, "dislikes": 1})


class TestAnalyticsAPI(unittest.TestCase):
    def test_public_api_and_chat_survive_analytics_failure(self):
        from fastapi.testclient import TestClient
        from app import app, analytics_store

        with patch.object(analytics_store, "record_chat", side_effect=RuntimeError("storage offline")):
            with TestClient(app) as client:
                response = client.post("/api/chat", json={"message": "What is MND?"})
                self.assertEqual(response.status_code, 200)
                public = client.get("/api/analytics")
                self.assertEqual(public.status_code, 200)
                self.assertNotIn("user_key", public.text)
                self.assertNotIn("conversation_key", public.text)

    def test_feedback_endpoint_rejects_invalid_rating(self):
        from fastapi.testclient import TestClient
        from app import app

        with TestClient(app) as client:
            response = client.post("/api/analytics/feedback", json={"rating": "maybe"})
            self.assertEqual(response.status_code, 400)


if __name__ == "__main__":
    unittest.main(verbosity=2)
