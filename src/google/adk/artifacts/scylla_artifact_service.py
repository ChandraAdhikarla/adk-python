import os
import json
from cassandra.cluster import Cluster
from ai_core.db.client import ScyllaDBClient
from typing_extensions import override
from google.genai import types
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

from .base_artifact_service import BaseArtifactService


class ScyllaArtifactService(BaseArtifactService):
    """ScyllaDB-backed implementation of the artifact service."""

    def __init__(self):
        # Initialize Scylla client
        self.client = ScyllaDBClient()
        self.ks = self.client._keyspace

    @override
    def save_artifact(
        self,
        *,
        org_id: str,
        team_id: str,
        session_id: str,
        filename: str,
        artifact_id: str,
        timestamp: datetime,
        file_type: str,
        file_size: int,
        agent_id: str,
        agent_name: str
    ) -> None:
       
        logger.info(f"Saving artifact to Scylla: {filename}, {agent_id}, {agent_name}")
        # Insert new artifact version
        insert_cql = f"INSERT INTO {self.ks}.artifacts " \
                     "(team_id, org_id, session_id, filename, filename_idx, id, created, file_type, file_size, agent_id, agent_name) " \
                     "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"
        self.client.execute(
            insert_cql,
            (team_id, org_id, session_id, filename, filename.lower(), artifact_id, timestamp, file_type, file_size, agent_id, agent_name),
        )
        return None

    @override
    def delete_artifact(
        self,
        *,
        team_id: str,
        org_id: str,
        session_id: str,
        filename: str,
    ) -> None:
        # Remove all versions of this artifact
        cql = f"DELETE FROM {self.ks}.artifacts " \
              "WHERE  org_id=? AND team_id=? AND session_id=? AND filename=?"
        self.client.execute(
            cql, (org_id, team_id, session_id, filename)
        )