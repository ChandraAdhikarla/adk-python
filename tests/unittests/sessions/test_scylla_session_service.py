import os
import uuid
import pytest
from cassandra.cluster import Cluster

from src.google.adk.db.schema_init import ensure_schema
from src.google.adk.sessions.scylla_session_service import ScyllaSessionService
from src.google.adk.sessions.base_session_service import GetSessionConfig
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
    return ScyllaSessionService()


def test_create_get_list_delete_session(service):
    app_name = "test_app"
    user_id = "user1"
    # Create session
    session = service.create_session(app_name=app_name, user_id=user_id)
    assert isinstance(session, Session)
    sid = session.id
    # Get session
    fetched = service.get_session(app_name=app_name, user_id=user_id, session_id=sid)
    assert fetched is not None
    assert fetched.id == sid
    # List sessions
    resp = service.list_sessions(app_name=app_name, user_id=user_id)
    assert any(s.id == sid for s in resp.sessions)
    # Delete session
    service.delete_session(app_name=app_name, user_id=user_id, session_id=sid)
    # After deletion
    assert service.get_session(app_name=app_name, user_id=user_id, session_id=sid) is None 