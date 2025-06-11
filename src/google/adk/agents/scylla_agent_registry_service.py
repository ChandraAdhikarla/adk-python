import os
from cassandra.cluster import Cluster
from ai_core.db.client import ScyllaDBClient

from .base_agent_registry_service import BaseAgentRegistryService


class ScyllaAgentRegistryService(BaseAgentRegistryService):
    """ScyllaDB-backed implementation of the agent registry service."""

    def __init__(self):
        # Initialize Scylla client
        self.client = ScyllaDBClient()
        self.ks = self.client._keyspace

    def list_agent_ids(
        self,
        org_id: str,
        team_id: str,
        version: str,
    ) -> list[str]:
        cql = (
            f"SELECT id FROM {self.ks}.agents "
            "WHERE org_id=? AND team_id=? AND version=?"
        )
        rows = self.client.execute(cql, (org_id, team_id, version))
        return [r.id for r in rows]

    def register_agent(
        self,
        org_id: str,
        team_id: str,
        version: str,
        agent_id: str,
        definition: dict,
    ):
        # Store a JSON blob of the definition in a separate table
        # For now, we keep in a special registry table
        cql = (
            f"INSERT INTO {self.ks}.agent_registry "
            "(org_id, team_id, version, agent_id, definition) "
            "VALUES (?, ?, ?, ?, ?)"
        )
        # Serialize definition dict to JSON string
        try:
            import json
            def_json = json.dumps(definition)
        except Exception:
            def_json = str(definition)
        self.client.execute(cql, (org_id, team_id, version, agent_id, def_json))

    def get_agent_definition(
        self,
        org_id: str,
        team_id: str,
        version: str,
        agent_id: str,
    ) -> dict | None:
        # Fetch the saved definition JSON from agent_registry
        cql = (
            f"SELECT definition FROM {self.ks}.agent_registry "
            "WHERE org_id=? AND team_id=? AND agent_id=? LIMIT 1"
        )
        row = self.client.execute(cql, (org_id, team_id, agent_id)).one()
        if not row or not row.definition:
            return None
        # Definition was stored as a JSON/text blob; parse if string
        defn = row.definition
        if isinstance(defn, str):
            try:
                import json
                defn = json.loads(defn)
            except Exception:
                pass
        return defn 