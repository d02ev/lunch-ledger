from __future__ import annotations
import os
import uuid
from datetime import datetime, timedelta
from app.models import LunchSession, MemberPreference

SESSION_TIMEOUT = int(os.getenv("SESSION_TIMEOUT_MINUTES", "15"))


class SessionManager:
    """
    In-memory store for active lunch sessions.
    Sessions expire after SESSION_TIMEOUT minutes.
    """

    def __init__(self) -> None:
        self._sessions: dict[str, LunchSession] = {}

    # ── Session lifecycle ──────────────────────────────────────────────────────

    def create(self, channel_id: str, created_by: str, message_ts: str | None = None) -> LunchSession:
        session_id = str(uuid.uuid4())[:8].upper()   # short, readable ID
        session = LunchSession(
            session_id=session_id,
            channel_id=channel_id,
            created_by=created_by,
            expires_at=datetime.utcnow() + timedelta(minutes=SESSION_TIMEOUT),
            message_ts=message_ts,
        )
        self._sessions[session_id] = session
        return session

    def get(self, session_id: str) -> LunchSession | None:
        session = self._sessions.get(session_id)
        if session and self._is_expired(session):
            session.status = "cancelled"
        return session

    def get_active_for_channel(self, channel_id: str) -> LunchSession | None:
        for session in self._sessions.values():
            if session.channel_id == channel_id and session.status == "open":
                if not self._is_expired(session):
                    return session
        return None

    def cancel(self, session_id: str) -> bool:
        session = self._sessions.get(session_id)
        if session:
            session.status = "cancelled"
            return True
        return False

    def mark_processing(self, session_id: str) -> None:
        if s := self._sessions.get(session_id):
            s.status = "processing"

    def mark_completed(self, session_id: str) -> None:
        if s := self._sessions.get(session_id):
            s.status = "completed"

    # ── Preferences ───────────────────────────────────────────────────────────

    def add_preference(self, session_id: str, pref: MemberPreference) -> bool:
        session = self.get(session_id)
        if not session or session.status != "open":
            return False
        session.preferences[pref.member_id] = pref
        return True

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _is_expired(self, session: LunchSession) -> bool:
        return datetime.utcnow() > session.expires_at

    def members_joined(self, session_id: str) -> list[str]:
        session = self.get(session_id)
        if not session:
            return []
        return [p.member_name for p in session.preferences.values()]

    def time_remaining(self, session_id: str) -> int:
        """Returns minutes remaining, 0 if expired."""
        session = self.get(session_id)
        if not session:
            return 0
        delta = session.expires_at - datetime.utcnow()
        return max(0, int(delta.total_seconds() / 60))


session_manager = SessionManager()