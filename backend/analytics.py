"""Privacy-conscious aggregate analytics storage for the public chatbot."""

from __future__ import annotations

import hashlib
import re
import sqlite3
import unicodedata
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo


PROFILE_CATEGORIES = (
    "Disability Support Worker",
    "Carer",
    "Physiotherapist",
    "Occupational Therapist",
    "Client/Participant",
    "Other",
)
RATINGS = {"like", "dislike"}
ID_RE = re.compile(r"^[A-Za-z0-9._:-]{1,160}$")
EMAIL_RE = re.compile(r"\b[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}\b")
URL_RE = re.compile(r"(?:https?://|www\.)\S+", re.I)
PHONE_RE = re.compile(r"(?<!\w)(?:\+?\d[\d\s().-]{7,}\d)(?!\w)")
PRIVATE_RE = re.compile(
    r"\b(?:my\s+(?:name|address|phone|mobile|email|medicare)|"
    r"i\s+(?:live|am\s+called)|born\s+on)\b",
    re.I,
)


class AnalyticsStore:
    """SQLite-backed event store. Public methods return aggregates only."""

    def __init__(self, path: str | Path, local_timezone: str = "Australia/Sydney"):
        self.path = Path(path)
        try:
            self.timezone = ZoneInfo(local_timezone)
        except Exception:
            self.timezone = timezone.utc

    def _connect(self) -> sqlite3.Connection:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self.path, timeout=5)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA journal_mode=WAL")
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS conversation_events (
                user_key TEXT NOT NULL,
                conversation_key TEXT NOT NULL,
                question TEXT,
                profile_category TEXT,
                created_at TEXT NOT NULL,
                UNIQUE(user_key, conversation_key)
            );
            CREATE INDEX IF NOT EXISTS idx_conversation_created
                ON conversation_events(created_at);
            CREATE INDEX IF NOT EXISTS idx_conversation_question
                ON conversation_events(question);
            CREATE TABLE IF NOT EXISTS question_events (
                event_id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_key TEXT NOT NULL,
                conversation_key TEXT NOT NULL,
                question TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_question_text
                ON question_events(question);
            CREATE TABLE IF NOT EXISTS feedback_events (
                user_key TEXT NOT NULL,
                response_key TEXT NOT NULL,
                rating TEXT NOT NULL CHECK(rating IN ('like', 'dislike')),
                created_at TEXT NOT NULL,
                UNIQUE(user_key, response_key)
            );
            CREATE INDEX IF NOT EXISTS idx_feedback_rating
                ON feedback_events(rating);
            """
        )
        return connection

    @staticmethod
    def _key(value: str) -> str:
        return hashlib.sha256(value.encode("utf-8")).hexdigest()

    @staticmethod
    def _valid_id(value: object) -> str | None:
        candidate = str(value or "").strip()
        return candidate if ID_RE.fullmatch(candidate) else None

    @staticmethod
    def normalize_question(question: object) -> str | None:
        """Return a short, displayable question or None when it looks private."""
        text = unicodedata.normalize("NFKC", str(question or "")).strip()
        if not text or len(text) > 2000:
            return None
        if EMAIL_RE.search(text) or URL_RE.search(text) or PHONE_RE.search(text) or PRIVATE_RE.search(text):
            return None
        text = text.casefold()
        text = re.sub(r"[^\w\s]", " ", text, flags=re.UNICODE)
        text = re.sub(r"\s+", " ", text).strip()
        return text[:240] or None

    @staticmethod
    def _timestamp(value: datetime | None = None) -> str:
        current = value or datetime.now(timezone.utc)
        if current.tzinfo is None:
            current = current.replace(tzinfo=timezone.utc)
        return current.astimezone(timezone.utc).isoformat(timespec="seconds")

    def record_chat(
        self,
        anonymous_user_id: object,
        conversation_id: object,
        question: object,
        profile_category: object,
        occurred_at: datetime | None = None,
    ) -> None:
        user_id = self._valid_id(anonymous_user_id)
        conversation = self._valid_id(conversation_id)
        if not user_id or not conversation:
            return
        category = str(profile_category or "").strip()
        if category not in PROFILE_CATEGORIES:
            category = "Other"
        normalized = self.normalize_question(question)
        timestamp = self._timestamp(occurred_at)
        with self._connect() as connection:
            connection.execute(
                """INSERT OR IGNORE INTO conversation_events
                   (user_key, conversation_key, question, profile_category, created_at)
                   VALUES (?, ?, ?, ?, ?)""",
                (self._key(user_id), self._key(conversation), None, category, timestamp),
            )
            if normalized:
                connection.execute(
                    """INSERT INTO question_events
                       (user_key, conversation_key, question, created_at)
                       VALUES (?, ?, ?, ?)""",
                    (self._key(user_id), self._key(conversation), normalized, timestamp),
                )

    def record_feedback(
        self,
        anonymous_user_id: object,
        response_id: object,
        rating: object,
        occurred_at: datetime | None = None,
    ) -> None:
        user_id = self._valid_id(anonymous_user_id)
        response = self._valid_id(response_id)
        normalized_rating = str(rating or "").strip().lower()
        if not user_id or not response or normalized_rating not in RATINGS:
            raise ValueError("Invalid anonymous feedback payload")
        with self._connect() as connection:
            connection.execute(
                """INSERT INTO feedback_events (user_key, response_key, rating, created_at)
                   VALUES (?, ?, ?, ?)
                   ON CONFLICT(user_key, response_key) DO UPDATE SET
                   rating = excluded.rating, created_at = excluded.created_at""",
                (self._key(user_id), self._key(response), normalized_rating, self._timestamp(occurred_at)),
            )

    def _period_start(self, now: datetime, period: str) -> datetime:
        local = now.astimezone(self.timezone)
        if period == "week":
            local = local - timedelta(days=local.weekday())
            return local.replace(hour=0, minute=0, second=0, microsecond=0)
        if period == "month":
            return local.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        return datetime.min.replace(tzinfo=self.timezone)

    def _count_conversations(self, start: datetime | None = None) -> int:
        with self._connect() as connection:
            if start is None:
                row = connection.execute("SELECT COUNT(*) AS count FROM conversation_events").fetchone()
            else:
                row = connection.execute(
                    "SELECT COUNT(*) AS count FROM conversation_events WHERE created_at >= ?",
                    (self._timestamp(start),),
                ).fetchone()
        return int(row["count"])

    def get_aggregates(self, now: datetime | None = None) -> dict:
        current = now or datetime.now(timezone.utc)
        with self._connect() as connection:
            week = self._count_conversations(self._period_start(current, "week"))
            month = self._count_conversations(self._period_start(current, "month"))
            all_time = self._count_conversations()
            questions = connection.execute(
                     """SELECT question, COUNT(*) AS count FROM question_events
                         GROUP BY question
                   ORDER BY count DESC, question ASC LIMIT 10"""
            ).fetchall()
            profiles = connection.execute(
                """SELECT profile_category, COUNT(DISTINCT user_key) AS count
                   FROM conversation_events GROUP BY profile_category
                   ORDER BY count DESC, profile_category ASC"""
            ).fetchall()
            feedback = connection.execute(
                "SELECT rating, COUNT(*) AS count FROM feedback_events GROUP BY rating"
            ).fetchall()
        profile_counts = {row["profile_category"]: int(row["count"]) for row in profiles}
        feedback_counts = {row["rating"]: int(row["count"]) for row in feedback}
        return {
            "total_conversations": {
                "this_week": week,
                "this_month": month,
                "all_time": all_time,
            },
            "popular_questions": [
                {"question": row["question"], "count": int(row["count"])} for row in questions
            ],
            "profile_categories": [
                {"category": category, "count": profile_counts.get(category, 0)}
                for category in PROFILE_CATEGORIES
            ],
            "feedback": {
                "likes": feedback_counts.get("like", 0),
                "dislikes": feedback_counts.get("dislike", 0),
            },
        }
