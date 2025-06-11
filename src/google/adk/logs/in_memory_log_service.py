import threading
from datetime import datetime
from typing import Optional, Dict, Any, List

from .base_log_service import BaseLogService, LogEntry


class InMemoryLogService(BaseLogService):
    """In-memory implementation of the log service."""

    def __init__(self):
        # key: (app_name, user_id, session_id) -> list of LogEntry
        self._logs: Dict[tuple[str, str, str], List[LogEntry]] = {}
        self._lock = threading.Lock()

    def log(
        self,
        *,
        app_name: str,
        user_id: str,
        session_id: str,
        level: str,
        logger: str,
        message: str,
        attributes: Optional[Dict[str, Any]] = None,
    ) -> None:
        entry = LogEntry(
            app_name=app_name,
            user_id=user_id,
            session_id=session_id,
            log_time=datetime.utcnow(),
            level=level,
            logger=logger,
            message=message,
            attributes=attributes,
        )
        key = (app_name, user_id, session_id)
        with self._lock:
            self._logs.setdefault(key, []).append(entry)

    def list_logs(
        self,
        *,
        app_name: str,
        user_id: str,
        session_id: str,
        since: Optional[datetime] = None,
        level: Optional[str] = None,
        limit: Optional[int] = None,
    ) -> List[LogEntry]:
        key = (app_name, user_id, session_id)
        with self._lock:
            entries = list(self._logs.get(key, []))
        result: List[LogEntry] = []
        for entry in entries:
            if since and entry.log_time < since:
                continue
            if level and entry.level != level:
                continue
            result.append(entry)
            if limit is not None and len(result) >= limit:
                break
        return result 

    def get_session_logs(
        self,
        *,
        team_id: str,
        org_id: str,
        session_id: str,
    ) -> List[LogEntry]:
        key = (team_id, org_id, session_id)
        with self._lock:
            return list(self._logs.get(key, []))
    
    def insert_session_summary(
        self,
        *,
        team_id: str,
        org_id: str,
        session_id: str,
        summary: str,
        created_at: datetime,
    ) -> None:
        key = (team_id, org_id, session_id)
        with self._lock:
            self._logs.setdefault(key, []).append(summary)
            return 