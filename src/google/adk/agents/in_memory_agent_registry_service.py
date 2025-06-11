import threading
from typing import Dict, List

from .base_agent_registry_service import BaseAgentRegistryService


class InMemoryAgentRegistryService(BaseAgentRegistryService):
    """In-memory implementation of the agent registry service."""

    def __init__(self):
        # key: (org_id, team_id, version) -> mapping of agent_id to definition dict
        self._store: Dict[tuple[str, str, str], Dict[str, dict]] = {}
        self._lock = threading.Lock()

    def list_agent_ids(
        self,
        org_id: str,
        team_id: str,
        version: str,
    ) -> List[str]:
        key = (org_id, team_id, version)
        with self._lock:
            return list(self._store.get(key, {}).keys())

    def register_agent(
        self,
        org_id: str,
        team_id: str,
        version: str,
        agent_id: str,
        definition: dict,
    ):
        key = (org_id, team_id, version)
        with self._lock:
            if key not in self._store:
                self._store[key] = {}
            self._store[key][agent_id] = definition

    def get_agent_definition(
        self,
        org_id: str,
        team_id: str,
        version: str,
        agent_id: str,
    ) -> dict | None:
        key = (org_id, team_id, version)
        with self._lock:
            return self._store.get(key, {}).get(agent_id) 