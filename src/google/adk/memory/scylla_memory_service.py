import os
import json
import logging
from cassandra.cluster import Cluster
from ai_core.db.client import ScyllaDBClient
from ..db.schema_init import ensure_schema
from typing_extensions import override
from .base_memory_service import BaseMemoryService, MemoryResult, SearchMemoryResponse
from ..sessions.session import Session
from ..events.event import Event

logger = logging.getLogger(__name__)

class ScyllaMemoryService(BaseMemoryService):
    """ScyllaDB-backed implementation of the memory service."""

    def __init__(self):
        # Ensure shared schema is initialized
        ensure_schema()

        self.client = ScyllaDBClient()
        self.ks = self.client._keyspace
        logger.info(f"ScyllaMemoryService initialized with keyspace: {self.ks}")

    @override
    def add_session_to_memory(self, session: Session):
        # Follow Google's exact pattern: filter events with content
        filtered_events = [
            event for event in session.events if event.content
        ]
        
        # Serialize events to JSON for database storage
        events_data = []
        for event in filtered_events:
            event_dict = event.dict()
            # Convert sets to lists for JSON serialization
            if event_dict.get('long_running_tool_ids') is not None:
                event_dict['long_running_tool_ids'] = list(event_dict['long_running_tool_ids'])
            events_data.append(event_dict)
        
        events_json = json.dumps(events_data)
        cql = f"INSERT INTO {self.ks}.memories (app_name, user_id, session_id, events) VALUES (?, ?, ?, ?)"
        params = (session.app_name, session.user_id, session.id, events_json)
        self.client.execute(cql, params)
        logger.info(f"Successfully stored session {session.id} in memory with {len(filtered_events)} events")

    @override
    def search_memory(self, *, app_name: str, user_id: str, query: str) -> SearchMemoryResponse:
        # Follow Google's exact logic
        keywords = set(query.lower().split())
        response = SearchMemoryResponse()
        
        # Get all sessions for this app_name/user_id (equivalent to Google's key filtering)
        cql = f"SELECT session_id, events FROM {self.ks}.memories WHERE app_name=? AND user_id=?"
        rows = self.client.execute(cql, (app_name, user_id))
        
        for row in rows:
            # Reconstruct events from JSON storage
            events_list = json.loads(row.events) if row.events else []
            events = []
            for ev_data in events_list:
                # Convert long_running_tool_ids back from list to set
                if ev_data.get('long_running_tool_ids') is not None:
                    ev_data['long_running_tool_ids'] = set(ev_data['long_running_tool_ids'])
                
                # Simple reconstruction - if it fails, the data is corrupted, skip this session
                try:
                    event = Event(**ev_data)
                    events.append(event)
                except Exception:
                    # Skip this entire session if any event is corrupted
                    events = []
                    break
            
            # Apply Google's exact matching logic
            matched_events = []
            for event in events:
                if not event.content or not event.content.parts:
                    continue
                parts = event.content.parts
                text = '\n'.join([part.text for part in parts if part.text]).lower()
                for keyword in keywords:
                    if keyword in text:
                        matched_events.append(event)
                        break
            
            # Add to response if matches found (Google's exact pattern)
            if matched_events:
                response.memories.append(
                    MemoryResult(session_id=row.session_id, events=matched_events)
                )
        
        return response 