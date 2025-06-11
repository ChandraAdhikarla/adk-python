# Copyright 2025 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import base64
import copy
from datetime import datetime
import json
import logging
from typing import Any, Optional
import uuid

from google.genai import types
from sqlalchemy import Boolean
from sqlalchemy import delete
from sqlalchemy import Dialect
from sqlalchemy import ForeignKeyConstraint
from sqlalchemy import func
from sqlalchemy import Text
from sqlalchemy.dialects import postgresql
from sqlalchemy.engine import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.exc import ArgumentError
from sqlalchemy.ext.mutable import MutableDict
from sqlalchemy.inspection import inspect
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column
from sqlalchemy.orm import relationship
from sqlalchemy.orm import Session as DatabaseSessionFactory
from sqlalchemy.orm import sessionmaker
from sqlalchemy.schema import MetaData
from sqlalchemy.types import DateTime
from sqlalchemy.types import PickleType
from sqlalchemy.types import String
from sqlalchemy.types import TypeDecorator
from typing_extensions import override
from tzlocal import get_localzone

from ..events.event import Event
from .base_session_service import BaseSessionService
from .base_session_service import GetSessionConfig
from .base_session_service import ListEventsResponse
from .base_session_service import ListSessionsResponse
from .session import Session
from .state import State


logger = logging.getLogger(__name__)


class DynamicJSON(TypeDecorator):
  """A JSON-like type that uses JSONB on PostgreSQL and TEXT with JSON

  serialization for other databases.
  """

  impl = Text  # Default implementation is TEXT

  def load_dialect_impl(self, dialect: Dialect):
    if dialect.name == "postgresql":
      return dialect.type_descriptor(postgresql.JSONB)
    else:
      return dialect.type_descriptor(Text)  # Default to Text for other dialects

  def process_bind_param(self, value, dialect: Dialect):
    if value is not None:
      if dialect.name == "postgresql":
        return value  # JSONB handles dict directly
      else:
        return json.dumps(value)  # Serialize to JSON string for TEXT
    return value

  def process_result_value(self, value, dialect: Dialect):
    if value is not None:
      if dialect.name == "postgresql":
        return value  # JSONB returns dict directly
      else:
        return json.loads(value)  # Deserialize from JSON string for TEXT
    return value


class Base(DeclarativeBase):
  """Base class for database tables."""
  pass


class StorageSession(Base):
  """Represents a session stored in the database."""
  __tablename__ = "sessions"

  app_name: Mapped[str] = mapped_column(String, primary_key=True)
  user_id: Mapped[str] = mapped_column(String, primary_key=True)
  id: Mapped[str] = mapped_column(
      String, primary_key=True, default=lambda: str(uuid.uuid4())
  )

  state: Mapped[MutableDict[str, Any]] = mapped_column(
      MutableDict.as_mutable(DynamicJSON), default={}
  )

  create_time: Mapped[DateTime] = mapped_column(DateTime(), default=func.now())
  update_time: Mapped[DateTime] = mapped_column(
      DateTime(), default=func.now(), onupdate=func.now()
  )

  storage_events: Mapped[list["StorageEvent"]] = relationship(
      "StorageEvent",
      back_populates="storage_session",
  )

  def __repr__(self):
    return f"<StorageSession(id={self.id}, update_time={self.update_time})>"


class StorageEvent(Base):
  """Represents an event stored in the database."""
  __tablename__ = "events"

  id: Mapped[str] = mapped_column(String, primary_key=True)
  app_name: Mapped[str] = mapped_column(String, primary_key=True)
  user_id: Mapped[str] = mapped_column(String, primary_key=True)
  session_id: Mapped[str] = mapped_column(String, primary_key=True)

  invocation_id: Mapped[str] = mapped_column(String)
  author: Mapped[str] = mapped_column(String)
  branch: Mapped[str] = mapped_column(String, nullable=True)
  timestamp: Mapped[DateTime] = mapped_column(DateTime(), default=func.now())
  content: Mapped[dict[str, Any]] = mapped_column(DynamicJSON, nullable=True)
  actions: Mapped[MutableDict[str, Any]] = mapped_column(PickleType)

  long_running_tool_ids_json: Mapped[Optional[str]] = mapped_column(
      Text, nullable=True
  )
  grounding_metadata: Mapped[dict[str, Any]] = mapped_column(
      DynamicJSON, nullable=True
  )
  partial: Mapped[bool] = mapped_column(Boolean, nullable=True)
  turn_complete: Mapped[bool] = mapped_column(Boolean, nullable=True)
  error_code: Mapped[str] = mapped_column(String, nullable=True)
  error_message: Mapped[str] = mapped_column(String, nullable=True)
  interrupted: Mapped[bool] = mapped_column(Boolean, nullable=True)

  storage_session: Mapped[StorageSession] = relationship(
      "StorageSession",
      back_populates="storage_events",
  )

  __table_args__ = (
      ForeignKeyConstraint(
          ["app_name", "user_id", "session_id"],
          ["sessions.app_name", "sessions.user_id", "sessions.id"],
          ondelete="CASCADE",
      ),
  )

  @property
  def long_running_tool_ids(self) -> set[str]:
    return (
        set(json.loads(self.long_running_tool_ids_json))
        if self.long_running_tool_ids_json
        else set()
    )

  @long_running_tool_ids.setter
  def long_running_tool_ids(self, value: set[str]):
    if value is None:
      self.long_running_tool_ids_json = None
    else:
      self.long_running_tool_ids_json = json.dumps(list(value))


class Transcript(Base):
  """Represents a transcript stored in the database."""
  __tablename__ = "transcripts"

  org_id: Mapped[str] = mapped_column(String, primary_key=True)
  session_id: Mapped[str] = mapped_column(String, primary_key=True)
  id: Mapped[str] = mapped_column(String, primary_key=True)
  timestamp: Mapped[datetime] = mapped_column(DateTime, primary_key=True)

  metadata: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
  text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

  def __repr__(self):
    return (
        f"<Transcript(org_id={self.org_id}, session_id={self.session_id},"
        f" id={self.id}, timestamp={self.timestamp})>"
    )


class Analysis(Base):
  """Represents an analysis stored in the database."""
  __tablename__ = "analysis"

  org_id: Mapped[str] = mapped_column(String, primary_key=True)
  session_id: Mapped[str] = mapped_column(String, primary_key=True)
  timestamp: Mapped[datetime] = mapped_column(DateTime, primary_key=True)

  agent_id: Mapped[Optional[str]] = mapped_column(String, nullable=True)
  id: Mapped[str] = mapped_column(String) # As per DDL, this 'id' is not part of the PK for analysis table
  analysis: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

  def __repr__(self):
    return (
        f"<Analysis(org_id={self.org_id}, session_id={self.session_id},"
        f" timestamp={self.timestamp})>"
    )


class StorageAppState(Base):
  """Represents an app state stored in the database."""
  __tablename__ = "app_states"

  app_name: Mapped[str] = mapped_column(String, primary_key=True)
  state: Mapped[MutableDict[str, Any]] = mapped_column(
      MutableDict.as_mutable(DynamicJSON), default={}
  )
  update_time: Mapped[DateTime] = mapped_column(
      DateTime(), default=func.now(), onupdate=func.now()
  )


class StorageUserState(Base):
  """Represents a user state stored in the database."""
  __tablename__ = "user_states"

  app_name: Mapped[str] = mapped_column(String, primary_key=True)
  user_id: Mapped[str] = mapped_column(String, primary_key=True)
  state: Mapped[MutableDict[str, Any]] = mapped_column(
      MutableDict.as_mutable(DynamicJSON), default={}
  )
  update_time: Mapped[DateTime] = mapped_column(
      DateTime(), default=func.now(), onupdate=func.now()
  )


# Key for storing session parameters within StorageSession.state
_SESSION_PARAMS_KEY = "_session_params_"

class DatabaseSessionService(BaseSessionService):
  """A session service that uses a database for storage."""

  def __init__(self, db_url: str):
    """
    Args:
        db_url: The database URL to connect to.
    """
    # 1. Create DB engine for db connection
    # 2. Create all tables based on schema
    # 3. Initialize all properties

    try:
      db_engine = create_engine(db_url)
    except Exception as e:
      if isinstance(e, ArgumentError):
        raise ValueError(
            f"Invalid database URL format or argument '{db_url}'."
        ) from e
      if isinstance(e, ImportError):
        raise ValueError(
            f"Database related module not found for URL '{db_url}'."
        ) from e
      raise ValueError(
          f"Failed to create database engine for URL '{db_url}'"
      ) from e

    # Get the local timezone
    local_timezone = get_localzone()
    logger.info(f"Local timezone: {local_timezone}")

    self.db_engine: Engine = db_engine
    self.metadata: MetaData = MetaData()
    self.inspector = inspect(self.db_engine)

    # DB session factory method
    self.DatabaseSessionFactory: sessionmaker[DatabaseSessionFactory] = (
        sessionmaker(bind=self.db_engine)
    )

    # Uncomment to recreate DB every time
    # Base.metadata.drop_all(self.db_engine)
    Base.metadata.create_all(self.db_engine)

  @override
  def create_session(
      self,
      *,
      app_name: str,
      user_id: str,
      state: Optional[dict[str, Any]] = None,
      parameters: Optional[dict[str, Any]] = None,
      session_id: Optional[str] = None,
      query: Optional[str] = None,
  ) -> Session:
    # 1. Populate states.
    # 2. Build storage session object
    # 3. Add the object to the table
    # 4. Build the session object with generated id
    # 5. Return the session

    with self.DatabaseSessionFactory() as sessionFactory:
      storage_app_state = sessionFactory.get(StorageAppState, (app_name))
      storage_user_state = sessionFactory.get(
          StorageUserState, (app_name, user_id)
      )

      app_state_from_db = storage_app_state.state if storage_app_state else {}
      user_state_from_db = storage_user_state.state if storage_user_state else {}

      if not storage_app_state:
        storage_app_state = StorageAppState(app_name=app_name, state={})
        sessionFactory.add(storage_app_state)
      if not storage_user_state:
        storage_user_state = StorageUserState(
            app_name=app_name, user_id=user_id, state={}
        )
        sessionFactory.add(storage_user_state)

      # state here is the initial session-specific state (excluding parameters)
      # parameters are handled separately
      app_state_delta, user_state_delta, initial_session_specific_state = _extract_state_delta(
          state
      )

      current_app_state = app_state_from_db.copy()
      current_user_state = user_state_from_db.copy()
      current_app_state.update(app_state_delta)
      current_user_state.update(user_state_delta)

      if app_state_delta:
        storage_app_state.state = current_app_state
      if user_state_delta:
        storage_user_state.state = current_user_state

      # Combine initial session-specific state with parameters for StorageSession.state
      combined_session_storage_state = initial_session_specific_state.copy()
      if parameters:
        combined_session_storage_state[_SESSION_PARAMS_KEY] = parameters

      storage_session = StorageSession(
          app_name=app_name,
          user_id=user_id,
          id=session_id,
          state=combined_session_storage_state,
      )
      sessionFactory.add(storage_session)
      sessionFactory.commit()
      sessionFactory.refresh(storage_session)

      # For the returned Session Pydantic model:
      # Session.state should be the merged app, user, and session-specific state
      # Session.parameters should be the parameters we stored
      
      merged_runtime_state = _merge_state(
          current_app_state, current_user_state, initial_session_specific_state
      )
      
      # query parameter is not directly part of the Session model typically,
      # but if it needs to be logged or stored elsewhere, that logic would go here or in session_utils.
      # For now, it's accepted by the signature.

      return Session(
          app_name=str(storage_session.app_name),
          user_id=str(storage_session.user_id),
          id=str(storage_session.id),
          state=merged_runtime_state,
          parameters=parameters or {},
          last_update_time=storage_session.update_time.timestamp(),
      )

  @override
  def get_session(
      self,
      *,
      app_name: str,
      user_id: str,
      session_id: str,
      config: Optional[GetSessionConfig] = None,
  ) -> Optional[Session]:
    with self.DatabaseSessionFactory() as sessionFactory:
      storage_session = sessionFactory.get(
          StorageSession, (app_name, user_id, session_id)
      )
      if storage_session is None:
        return None

      storage_events = (
          sessionFactory.query(StorageEvent)
          .filter(StorageEvent.session_id == storage_session.id)
          .filter(
              StorageEvent.timestamp < config.after_timestamp
              if config
              else True
          )
          .limit(config.num_recent_events if config else None)
          .all()
      )

      storage_app_state = sessionFactory.get(StorageAppState, (app_name))
      storage_user_state = sessionFactory.get(
          StorageUserState, (app_name, user_id)
      )

      app_state_from_db = storage_app_state.state if storage_app_state else {}
      user_state_from_db = storage_user_state.state if storage_user_state else {}
      
      # Separate parameters from other session state in StorageSession.state
      session_storage_state = storage_session.state.copy() if storage_session.state else {}
      session_params = session_storage_state.pop(_SESSION_PARAMS_KEY, {})
      session_specific_state = session_storage_state # What remains after popping params

      merged_runtime_state = _merge_state(app_state_from_db, user_state_from_db, session_specific_state)

      session_model = Session(
          app_name=app_name,
          user_id=user_id,
          id=session_id,
          state=merged_runtime_state,
          parameters=session_params,
          last_update_time=storage_session.update_time.timestamp(),
      )
      session_model.events = [
          Event(
              id=e.id,
              author=e.author,
              branch=e.branch,
              invocation_id=e.invocation_id,
              content=_decode_content(e.content),
              actions=e.actions,
              timestamp=e.timestamp.timestamp(),
              long_running_tool_ids=e.long_running_tool_ids,
              grounding_metadata=e.grounding_metadata,
              partial=e.partial,
              turn_complete=e.turn_complete,
              error_code=e.error_code,
              error_message=e.error_message,
              interrupted=e.interrupted,
          )
          for e in storage_events
      ]
      return session_model

  @override
  def list_sessions(
      self, *, app_name: str, user_id: str
  ) -> ListSessionsResponse:
    with self.DatabaseSessionFactory() as sessionFactory:
      results = (
          sessionFactory.query(StorageSession)
          .filter(StorageSession.app_name == app_name)
          .filter(StorageSession.user_id == user_id)
          .all()
      )
      sessions = []
      for storage_session in results:
        session = Session(
            app_name=app_name,
            user_id=user_id,
            id=storage_session.id,
            state={},
            last_update_time=storage_session.update_time.timestamp(),
        )
        sessions.append(session)
      return ListSessionsResponse(sessions=sessions)

  @override
  def delete_session(
      self, app_name: str, user_id: str, session_id: str
  ) -> None:
    with self.DatabaseSessionFactory() as sessionFactory:
      stmt = delete(StorageSession).where(
          StorageSession.app_name == app_name,
          StorageSession.user_id == user_id,
          StorageSession.id == session_id,
      )
      sessionFactory.execute(stmt)
      sessionFactory.commit()

  @override
  def append_event(self, session: Session, event: Event) -> Event:
    logger.info(f"Append event: {event} to session {session.id}")

    if event.partial:
      return event

    # 1. Check if timestamp is stale
    # 2. Update session attributes based on event config
    # 3. Store event to table
    with self.DatabaseSessionFactory() as sessionFactory:
      storage_session = sessionFactory.get(
          StorageSession, (session.app_name, session.user_id, session.id)
      )

      if storage_session.update_time.timestamp() > session.last_update_time:
        raise ValueError(
            f"Session last_update_time {session.last_update_time} is later than"
            f" the upate_time in storage {storage_session.update_time}"
        )

      # Fetch states from storage
      storage_app_state = sessionFactory.get(
          StorageAppState, (session.app_name)
      )
      storage_user_state = sessionFactory.get(
          StorageUserState, (session.app_name, session.user_id)
      )

      app_state = storage_app_state.state if storage_app_state else {}
      user_state = storage_user_state.state if storage_user_state else {}
      session_state = storage_session.state

      # Extract state delta
      app_state_delta = {}
      user_state_delta = {}
      session_state_delta = {}
      if event.actions:
        if event.actions.state_delta:
          app_state_delta, user_state_delta, session_state_delta = (
              _extract_state_delta(event.actions.state_delta)
          )

      # Merge state
      app_state.update(app_state_delta)
      user_state.update(user_state_delta)
      session_state.update(session_state_delta)

      # Update storage
      storage_app_state.state = app_state
      storage_user_state.state = user_state
      storage_session.state = session_state

      storage_event = StorageEvent(
          id=event.id,
          invocation_id=event.invocation_id,
          author=event.author,
          branch=event.branch,
          actions=event.actions,
          session_id=session.id,
          app_name=session.app_name,
          user_id=session.user_id,
          timestamp=datetime.fromtimestamp(event.timestamp),
          long_running_tool_ids=event.long_running_tool_ids,
          grounding_metadata=event.grounding_metadata,
          partial=event.partial,
          turn_complete=event.turn_complete,
          error_code=event.error_code,
          error_message=event.error_message,
          interrupted=event.interrupted,
      )
      if event.content:
        encoded_content = event.content.model_dump(exclude_none=True)
        # Workaround for multimodal Content throwing JSON not serializable
        # error with SQLAlchemy.
        for p in encoded_content["parts"]:
          if "inline_data" in p:
            p["inline_data"]["data"] = (
                base64.b64encode(p["inline_data"]["data"]).decode("utf-8"),
            )
        storage_event.content = encoded_content

      sessionFactory.add(storage_event)

      sessionFactory.commit()
      sessionFactory.refresh(storage_session)

      # Update timestamp with commit time
      session.last_update_time = storage_session.update_time.timestamp()

    # Also update the in-memory session
    super().append_event(session=session, event=event)
    return event

  @override
  def list_events(
      self,
      *,
      app_name: str,
      user_id: str,
      session_id: str,
  ) -> ListEventsResponse:
    raise NotImplementedError()

  def create_transcript(
      self,
      *,
      org_id: str,
      session_id: str,
      transcript_id: str,
      timestamp: datetime,
      metadata: Optional[str] = None,
      text: Optional[str] = None,
  ) -> Transcript:
    """Creates a new transcript record in the database."""
    with self.DatabaseSessionFactory() as sessionFactory:
      new_transcript = Transcript(
          org_id=org_id,
          session_id=session_id,
          id=transcript_id, # Renamed from id to transcript_id to avoid conflict with python's built-in id
          timestamp=timestamp,
          metadata=metadata,
          text=text,
      )
      sessionFactory.add(new_transcript)
      sessionFactory.commit()
      sessionFactory.refresh(new_transcript)
      return new_transcript

  def create_analysis(
      self,
      *,
      org_id: str,
      session_id: str,
      timestamp: datetime,
      analysis_id: str,
      agent_id: Optional[str] = None,
      analysis_text: Optional[str] = None, # Renamed from analysis to analysis_text
  ) -> Analysis:
    """Creates a new analysis record in the database."""
    with self.DatabaseSessionFactory() as sessionFactory:
      new_analysis = Analysis(
          org_id=org_id,
          session_id=session_id,
          timestamp=timestamp,
          id=analysis_id, # Renamed from id to analysis_id
          agent_id=agent_id,
          analysis=analysis_text, # Mapped to the model's 'analysis' field
      )
      sessionFactory.add(new_analysis)
      sessionFactory.commit()
      sessionFactory.refresh(new_analysis)
      return new_analysis

  @override
  def update_session_parameters(
        self,
        *,
        app_name: str,
        user_id: str,
        session_id: str,
        parameters: dict[str, Any],
    ) -> Optional[Session]:
    with self.DatabaseSessionFactory() as sessionFactory:
      storage_session = sessionFactory.get(
          StorageSession, (app_name, user_id, session_id)
      )
      if storage_session is None:
        logger.warning(f"Session not found, cannot update parameters: {app_name}/{user_id}/{session_id}")
        return None

      # Ensure state is a mutable dictionary
      if storage_session.state is None:
           storage_session.state = MutableDict.as_mutable(DynamicJSON())
      elif not isinstance(storage_session.state, MutableDict):
           storage_session.state = MutableDict.as_mutable(DynamicJSON(storage_session.state))


      # Update the parameters part of the state
      # If parameters is empty, we might want to remove the key or store an empty dict
      if not parameters:
          storage_session.state.pop(_SESSION_PARAMS_KEY, None)
      else:
          storage_session.state[_SESSION_PARAMS_KEY] = parameters
      
      # Manually trigger update of MutableDict if necessary, though direct assignment should work.
      # storage_session.state.changed() # May not be needed with direct assignment to key

      sessionFactory.commit()
      # Return the updated session by calling get_session to ensure consistency
      return self.get_session(app_name=app_name, user_id=user_id, session_id=session_id)

def convert_event(event: StorageEvent) -> Event:
  """Converts a storage event to an event."""
  return Event(
      id=event.id,
      author=event.author,
      branch=event.branch,
      invocation_id=event.invocation_id,
      content=event.content,
      actions=event.actions,
      timestamp=event.timestamp.timestamp(),
  )


def _extract_state_delta(state: dict[str, Any]):
  app_state_delta = {}
  user_state_delta = {}
  session_state_delta = {}
  if state:
    for key in state.keys():
      if key.startswith(State.APP_PREFIX):
        app_state_delta[key.removeprefix(State.APP_PREFIX)] = state[key]
      elif key.startswith(State.USER_PREFIX):
        user_state_delta[key.removeprefix(State.USER_PREFIX)] = state[key]
      elif not key.startswith(State.TEMP_PREFIX):
        session_state_delta[key] = state[key]
  return app_state_delta, user_state_delta, session_state_delta


def _merge_state(app_state, user_state, session_state):
  # Merge states for response
  merged_state = copy.deepcopy(session_state)
  for key in app_state.keys():
    merged_state[State.APP_PREFIX + key] = app_state[key]
  for key in user_state.keys():
    merged_state[State.USER_PREFIX + key] = user_state[key]
  return merged_state


def _decode_content(
    content: Optional[dict[str, Any]],
) -> Optional[types.Content]:
  if not content:
    return None
  for p in content["parts"]:
    if "inline_data" in p:
      p["inline_data"]["data"] = base64.b64decode(p["inline_data"]["data"][0])
  return types.Content.model_validate(content)
