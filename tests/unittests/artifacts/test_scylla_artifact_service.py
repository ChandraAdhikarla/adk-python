import os
import uuid
import pytest
from cassandra.cluster import Cluster

from google.genai import types
from src.google.adk.db.schema_init import ensure_schema
from src.google.adk.artifacts.scylla_artifact_service import ScyllaArtifactService

@pytest.fixture(scope="module")
def keyspace():
    ks = f"test_ks_{uuid.uuid4().hex}"
    os.environ["SCYLLA_KEYSPACE"] = ks
    os.environ.setdefault("SCYLLA_HOSTS", "127.0.0.1")
    ensure_schema()
    yield ks

    cluster = Cluster(os.environ["SCYLLA_HOSTS"].split(","))
    session = cluster.connect()
    session.execute(f"DROP KEYSPACE IF EXISTS {ks}")
    session.shutdown()
    cluster.shutdown()

@pytest.fixture
def service(keyspace):
    return ScyllaArtifactService()


def test_save_load_list_versions_delete(service):
    app_name = "app"
    user_id = "u1"
    session_id = "s1"
    filename = "file.txt"
    part = types.Part.from_text(text="hello world")

    # Save artifact versions
    v0 = service.save_artifact(app_name=app_name, user_id=user_id, session_id=session_id, filename=filename, artifact=part)
    assert v0 == 0
    v1 = service.save_artifact(app_name=app_name, user_id=user_id, session_id=session_id, filename=filename, artifact=part)
    assert v1 == 1

    # List keys
    keys = service.list_artifact_keys(app_name=app_name, user_id=user_id, session_id=session_id)
    assert filename in keys

    # List versions
    versions = service.list_versions(app_name=app_name, user_id=user_id, session_id=session_id, filename=filename)
    assert versions == [0, 1]

    # Load latest
    latest = service.load_artifact(app_name=app_name, user_id=user_id, session_id=session_id, filename=filename)
    assert latest.text == "hello world"

    # Load specific version
    old = service.load_artifact(app_name=app_name, user_id=user_id, session_id=session_id, filename=filename, version=0)
    assert old.text == "hello world"

    # Delete artifact
    service.delete_artifact(app_name=app_name, user_id=user_id, session_id=session_id, filename=filename)
    # After delete, no keys
    keys2 = service.list_artifact_keys(app_name=app_name, user_id=user_id, session_id=session_id)
    assert keys2 == [] 