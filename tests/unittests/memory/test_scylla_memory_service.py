import os
import uuid
import pytest
from cassandra.cluster import Cluster
import json

from src.google.adk.db.schema_init import ensure_schema
from src.google.adk.memory.scylla_memory_service import ScyllaMemoryService
from src.google.adk.sessions.session import Session

@pytest.fixture(scope="module")
def keyspace():
    # Create a fresh keyspace for tests
    ks = f"test_ks_{uuid.uuid4().hex}"
    os.environ["SCYLLA_KEYSPACE"] = ks
    os.environ.setdefault("SCYLLA_HOSTS", "127.0.0.1")
    ensure_schema()
    yield ks

    # Teardown: drop keyspace
    cluster = Cluster(os.environ["SCYLLA_HOSTS"].split(","))
    session = cluster.connect()
    session.execute(f"DROP KEYSPACE IF EXISTS {ks}")
    session.shutdown()
    cluster.shutdown()

@pytest.fixture
def service(keyspace):
    return ScyllaMemoryService()


def test_add_and_query_memory(service):
    app_name = "app"
    user_id = "u1"
    session_id = "s1"
    # Create dummy session (no events for simplicity)
    dummy_session = Session(
        id=session_id,
        app_name=app_name,
        user_id=user_id,
        state={},
        events=[],
    )
    # Add to memory
    service.add_session_to_memory(dummy_session)
    # Direct CQL query to verify insertion
    rows = service.client.execute(
        f"SELECT session_id, events FROM {service.ks}.memories "
        "WHERE app_name=? AND user_id=?",
        (app_name, user_id)
    )
    session_ids = [r.session_id for r in rows]
    assert session_id in session_ids 