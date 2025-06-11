import os
import json
from datetime import datetime, timezone
from cassandra.cluster import Cluster
from ai_core.db.client import ScyllaDBClient
from typing import Optional, Dict, Any, List, Deque
from typing_extensions import override
import logging

from .base_log_service import BaseLogService, LogEntry

# Helper function to safely convert any value to a string for logging purposes
def safe_str(value: Any) -> str:
    """Convert any value to a string safely for logging purposes."""
    if value is None:
        return "None"
    try:
        return str(value)
    except Exception:
        return repr(value)

class ScyllaLogService(BaseLogService):
    """ScyllaDB-backed implementation of the log service."""

    def __init__(self):
        hosts = os.getenv("SCYLLA_HOSTS").split(",")
        keyspace = os.getenv("SCYLLA_KEYSPACE")
        ddl_cluster = Cluster(hosts)
        ddl_session = ddl_cluster.connect()
        # Ensure keyspace exists
        ddl_session.execute(f"""
            CREATE KEYSPACE IF NOT EXISTS {keyspace}
            WITH replication = {{ 'class': 'SimpleStrategy', 'replication_factor': 1 }}
        """.strip())
        ddl_session.set_keyspace(keyspace)
        # Create logs table
        ddl_session.execute(f"""
            CREATE TABLE IF NOT EXISTS logs (
              app_name text,
              user_id text,
              session_id text,
              log_time timestamp,
              level text,
              logger text,
              message text,
              message_idx text,
              agent_id text,
              attributes text,
              PRIMARY KEY ((app_name, user_id, session_id), log_time)
            ) WITH CLUSTERING ORDER BY (log_time ASC)
        """.strip())
        ddl_session.shutdown()
        ddl_cluster.shutdown()

        self.client = ScyllaDBClient()
        self.ks = self.client._keyspace
        # Dictionary to map sanitized agent names to display names
        self.agent_display_names = {}
        self._logger = logging.getLogger(__name__)

    def register_agent_name(self, internal_name: str, display_name: str) -> None:
        """Register a mapping between sanitized internal name and display name.
        
        Args:
            internal_name: The sanitized name used as identifier
            display_name: The original human-readable name for display
        """
        self.agent_display_names[internal_name] = display_name
        
        # Log the registration for debugging
        self._logger.debug(f"Registered agent name mapping: {safe_str(internal_name)} -> {safe_str(display_name)}")
        
        # Also record this mapping in our own logs table
        self.log(
            app_name="system",
            user_id="system",
            session_id="agent_names",
            level="DEBUG",
            logger="name_registry",
            message=f"Agent name registered: {safe_str(internal_name)} -> {safe_str(display_name)}",
            attributes={"internal_name": internal_name, "display_name": display_name}
        )

    def get_display_name(self, internal_name: str) -> str:
        """Get the display name for an agent, or return the internal name if not found.
        
        Args:
            internal_name: The sanitized name used as identifier
            
        Returns:
            The display name if registered, otherwise the internal name
        """
        return self.agent_display_names.get(internal_name, internal_name)

    @override
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
        log_time = datetime.utcnow()
        # Serialize attributes, converting sets to lists and fallback to string
        attrs_json_for_db = None
        if attributes:
            try:
                attrs_json_for_db = json.dumps(attributes, default=lambda o: list(o) if isinstance(o, set) else str(o))
            except Exception:
                attrs_json_for_db = None
        
        # Derive additional columns
        message_idx = message.strip().lower() if isinstance(message, str) else None

        # Derive agent_id from attributes if available
        agent_id_for_db = None
        message_for_db = message
        logger_name = logger

        if isinstance(attributes, dict):
            agent_id_for_db = attributes.get("agent_id") or attributes.get("author")
            
            # If we have an agent_id and it's in our display name mapping, 
            # update the message to use the display name
            if agent_id_for_db and agent_id_for_db in self.agent_display_names and message:
                # Replace the internal name with display name in the message
                # This helps make log messages more readable with proper agent names
                display_name = self.agent_display_names[agent_id_for_db]
                message_for_db = message.replace(agent_id_for_db, display_name)
                
                # Also update attributes if needed
                if attributes.get("author") == agent_id_for_db:
                    # Create a copy to avoid modifying the original dict
                    attributes_copy = dict(attributes)
                    attributes_copy["display_name"] = display_name
                    # Re-serialize with updated attributes
                    try:
                        attrs_json_for_db = json.dumps(attributes_copy, default=lambda o: list(o) if isinstance(o, set) else str(o))
                    except Exception:
                        pass  # Keep original attributes_json if this fails

        cql = (
            f"INSERT INTO {self.ks}.logs "
            "(app_name, user_id, session_id, log_time, level, logger, message, message_idx, agent_id, attributes) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"
        )
        params_db = (
            app_name,
            user_id,
            session_id,
            log_time,
            level,
            logger_name,
            message_for_db,
            message_idx,
            agent_id_for_db,
            attrs_json_for_db,
        )
        self.client.execute(cql, params_db)

    @override
    def list_logs(
        self,
        *,
        app_name: str,
        user_id: str,
        session_id: str,
        since: Optional[str] = None,
        level: Optional[str] = None,
        limit: Optional[int] = None,
    ) -> List[LogEntry]:

        # Build base CQL and params based on whether level is specified
        if level:
            base_cql = (
                f"SELECT app_name, user_id, session_id, log_time, level, logger, message, attributes, agent_id "
                f"FROM {self.ks}.logs_by_level "
                "WHERE app_name=? AND user_id=? AND session_id=? AND level=?"
            )
            params = [app_name, user_id, session_id, level]
        else:
            base_cql = (
            f"SELECT app_name, user_id, session_id, log_time, level, logger, message, attributes, agent_id "
            f"FROM {self.ks}.logs "
            "WHERE app_name=? AND user_id=? AND session_id=?"
            )
            params = [app_name, user_id, session_id]

        since_dt_for_query: Optional[datetime] = None

        if since:
            original_since_for_log = str(since) # For consistent logging of the input value

            if isinstance(since, datetime):
                self._logger.info(f"ScyllaLogService: 'since' parameter is a datetime object: {since.isoformat()}")
                since_dt_for_query = since
            elif isinstance(since, str):
                self._logger.info(f"ScyllaLogService: 'since' parameter is a string: '{since}'")
                parsed_from_string_dt = None
                try:
                    # Attempt 1: Direct parsing. datetime.fromisoformat should handle 'Z' and 'T' separator.
                    # Python 3.11+ also handles space separator here if unambiguous.
                    parsed_from_string_dt = datetime.fromisoformat(since)
                except ValueError:
                    self._logger.debug(f"ScyllaLogService: Direct fromisoformat failed for '{since}'. Trying fallbacks.")
                    try:
                        # Attempt 2: Explicitly replace 'Z' at the end with '+00:00'
                        if since.endswith('Z'):
                            parsed_from_string_dt = datetime.fromisoformat(since[:-1] + '+00:00')
                        else:
                            # Re-raise to fall into further attempts or the final warning.
                            raise ValueError("String not Z-terminated for Z-suffix fallback.")
                    except ValueError:
                        self._logger.debug(f"ScyllaLogService: Z-suffix fallback failed for '{since}'. Trying space to T conversion.")
                        # Attempt 3: Handle space-separated date/time "YYYY-MM-DD HH:MM:SS..."
                        # This is useful if Python version < 3.11 where fromisoformat is stricter about space.
                        if ' ' in since and 'T' not in since:
                            try:
                                parts = since.split(" ", 1)
                                if len(parts) == 2:
                                    t_formatted_since = "T".join(parts)
                                    parsed_from_string_dt = datetime.fromisoformat(t_formatted_since)
                                    self._logger.debug(f"ScyllaLogService: Parsed with space-to-T: {t_formatted_since} -> {parsed_from_string_dt.isoformat() if parsed_from_string_dt else 'None'}")
                                else:
                                    raise ValueError("Could not split string into two parts for space-to-T conversion.")
                            except ValueError as e_attempt3:
                                self._logger.debug(f"ScyllaLogService: Space-to-T conversion failed for '{since}': {e_attempt3}")
                                parsed_from_string_dt = None # Ensure it's None on failure
                        else: # No space for T-replacement or already has T, and previous attempts failed
                             parsed_from_string_dt = None
                
                if parsed_from_string_dt:
                    since_dt_for_query = parsed_from_string_dt
                else:
                    self._logger.warning(f"ScyllaLogService: Could not parse 'since' string: '{since}' after all attempts. SINCE filter NOT applied.")
            else: # 'since' is not None, not datetime, not string
                self._logger.warning(f"ScyllaLogService: 'since' parameter has unexpected type: {type(since)}. SINCE filter NOT applied.")

            # If since_dt_for_query is set (from datetime or successful string parse), make it UTC and add to query
            if since_dt_for_query:
                final_since_dt: datetime
                if since_dt_for_query.tzinfo is None:
                    final_since_dt = since_dt_for_query.replace(tzinfo=timezone.utc)
                else:
                    final_since_dt = since_dt_for_query.astimezone(timezone.utc)
                
                self._logger.info(f"ScyllaLogService: Applying SINCE filter (original input effectively '{original_since_for_log}', processed to UTC: {final_since_dt.isoformat()}). Query: log_time >= {final_since_dt}")
                base_cql += " AND log_time >= ?"
                params.append(final_since_dt)
            # else: The reason for not applying SINCE filter was logged above.
        else: # 'since' was None or empty string from the start
            self._logger.info(f"ScyllaLogService: No SINCE filter applied (since was None or empty).")
        
        # Add LIMIT clause if limit is provided
        if limit is not None and limit > 0:
            self._logger.info(f"ScyllaLogService: Applying LIMIT: {limit}")
            base_cql += " LIMIT ?"
            params.append(limit)

        self._logger.info(f"ScyllaLogService: Executing CQL: {base_cql} with params: {params}")
        rows = self.client.execute(base_cql, tuple(params))
        result: List[LogEntry] = []
        for r in rows:
            attrs = json.loads(r.attributes) if r.attributes else {}
            log_time_from_db = r.log_time
            if log_time_from_db.tzinfo is None:
                log_time_from_db = log_time_from_db.replace(tzinfo=timezone.utc)
            else:
                log_time_from_db = log_time_from_db.astimezone(timezone.utc)
            entry = LogEntry(
                app_name=r.app_name,
                user_id=r.user_id,
                session_id=r.session_id,
                log_time=log_time_from_db, 
                level=r.level,
                logger=r.logger,
                message=r.message,
                attributes=attrs,
                agent_id=r.agent_id,
            )
            result.append(entry)
        return result 
    
    @override
    def get_session_logs(
        self,
        *,
        team_id: str,
        org_id: str,
        session_id: str,
    ) -> List[LogEntry]:
        base_cql = (
            f"SELECT app_name, user_id, session_id, log_time, level, logger, message, attributes, agent_id "
            f"FROM {self.ks}.logs "
            "WHERE app_name=? AND user_id=? AND session_id=?"
            )
        params = [team_id, org_id, session_id]
        rows = self.client.execute(base_cql, tuple(params))
        result: List[LogEntry] = []
        for r in rows:
            attrs = json.loads(r.attributes) if r.attributes else {}
            log_time_from_db = r.log_time
            if log_time_from_db.tzinfo is None:
                log_time_from_db = log_time_from_db.replace(tzinfo=timezone.utc)
            else:
                log_time_from_db = log_time_from_db.astimezone(timezone.utc)
            entry = LogEntry(
                app_name=r.app_name,
                user_id=r.user_id,
                session_id=r.session_id,
                log_time=log_time_from_db, 
                level=r.level,
                logger=r.logger,
                message=r.message,
                attributes=attrs,
                agent_id=r.agent_id,
            )
            result.append(entry)
        return result 
    
    @override
    def insert_session_summary(
        self,
        *,
        team_id: str,
        org_id: str,
        session_id: str,
        summary: str,
        created_at: datetime,
    ) -> None:
        cql = (
            f"INSERT INTO {self.ks}.session_summary "
            "(team_id, org_id, session_id, data, created) "
            "VALUES (?, ?, ?, ?, ?)"
        )
        params = [team_id, org_id, session_id, summary, created_at]
        self.client.execute(cql, tuple(params))
        return 