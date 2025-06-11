import abc
from datetime import datetime
from typing import Any, Dict, Optional, List


class LogEntry:
    """Represents a log entry for a session."""
    def __init__(
        self,
        app_name: str,
        user_id: str,
        session_id: str,
        log_time: datetime,
        level: str,
        logger: str,
        message: str,
        attributes: Optional[Dict[str, Any]] = None,
        agent_id: Optional[str] = None,
    ) -> None:
        self.app_name = app_name
        self.user_id = user_id
        self.session_id = session_id
        self.log_time = log_time
        self.level = level
        self.logger = logger
        self.message = message
        self.attributes = attributes or {}
        self.agent_id = agent_id


class BaseLogService(abc.ABC):
    """Abstract base class for log services."""

    @abc.abstractmethod
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
        """Record a log entry."""

    @abc.abstractmethod
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
        """List log entries for a session.""" 
        
    @abc.abstractmethod
    def get_session_logs(
        self,
        *,
        team_id: str,
        org_id: str,
        session_id: str,
    ) -> List[LogEntry]:
        """List all log entries for a session.""" 
        
    @abc.abstractmethod
    def insert_session_summary(
        self,
        *,
        team_id: str,
        org_id: str,
        session_id: str,
        summary: str,
        created_at: datetime,
    ) -> str:
        """Insert the summary for a session.""" 