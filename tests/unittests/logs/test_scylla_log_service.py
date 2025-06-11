import os
import uuid
import pytest
from datetime import datetime, timedelta
from cassandra.cluster import Cluster

from src.google.adk.db.schema_init import ensure_schema
from src.google.adk.logs.scylla_log_service import ScyllaLogService
from src.google.adk.logs.base_log_service import LogEntry

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
    return ScyllaLogService()


def test_log_and_list_all_levels(service):
    app_name, user_id, session_id = 'app', 'u1', 's1'
    # Log entries
    service.log(app_name=app_name, user_id=user_id, session_id=session_id,
                level='INFO', logger='test', message='First', attributes={'a':1})
    service.log(app_name=app_name, user_id=user_id, session_id=session_id,
                level='ERROR', logger='test', message='Second', attributes={'b':2})
    # List all
    entries = service.list_logs(app_name=app_name, user_id=user_id, session_id=session_id)
    assert len(entries) == 2
    msgs = [e.message for e in entries]
    assert 'First' in msgs and 'Second' in msgs


def test_list_logs_filters(service):
    app_name, user_id, session_id = 'app', 'u1', 's2'
    now = datetime.utcnow()
    # log at two times
    service.log(app_name=app_name, user_id=user_id, session_id=session_id,
                level='INFO', logger='test', message='Old', attributes=None)
    # sleep short to get newer timestamp
    later = datetime.utcnow() + timedelta(seconds=1)
    # log later
    service.log(app_name=app_name, user_id=user_id, session_id=session_id,
                level='DEBUG', logger='test', message='New', attributes=None)
    # filter by since
    entries_since = service.list_logs(app_name=app_name, user_id=user_id, session_id=session_id, since=later)
    assert len(entries_since) == 1 and entries_since[0].message == 'New'
    # filter by level
    entries_error = service.list_logs(app_name=app_name, user_id=user_id, session_id=session_id, level='ERROR')
    assert entries_error == [] 