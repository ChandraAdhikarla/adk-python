import os
from cassandra.cluster import Cluster


def ensure_schema():
    """Creates the keyspace and all required tables in ScyllaDB."""
    hosts = os.getenv("SCYLLA_HOSTS").split(",")
    keyspace = os.getenv("SCYLLA_KEYSPACE")

    cluster = Cluster(hosts)
    session = cluster.connect()

    # Create keyspace
    session.execute(f"""
        CREATE KEYSPACE IF NOT EXISTS {keyspace}
        WITH replication = {{ 'class': 'SimpleStrategy', 'replication_factor': 1 }}
    """.strip())
    session.set_keyspace(keyspace)

    # Sessions table
    session.execute(f"""
CREATE TABLE IF NOT EXISTS {keyspace}.sessions (
  app_name text,
  user_id text,
  session_id text,
  created_at timestamp,
  description text,
  parameter text,
  search_idx text,
  state text,
  status text,
  title text,
  updated_at timestamp,
  PRIMARY KEY ((app_name, user_id), session_id, created_at)
) WITH CLUSTERING ORDER BY (session_id DESC, created_at DESC)
    """.strip())

    # Ensure latest session columns exist (safe to execute repeatedly; errors are ignored)
    for col_def in [
        "created_time timestamp",
        "description text",
        "parameter text",
        "search_idx text",
        "status text",
        "title text",
        "updated_at timestamp",
    ]:
        try:
            session.execute(f"ALTER TABLE {keyspace}.sessions ADD {col_def}")
        except Exception:
            # Column probably already exists – ignore
            pass

    # Events table
    session.execute(f"""
CREATE TABLE IF NOT EXISTS {keyspace}.events (
  app_name text,
  user_id text,
  session_id text,
  event_id text,
  invocation_id text,
  author text,
  branch text,
  timestamp timestamp,
  content text,
  actions text,
  grounding_metadata text,
  partial boolean,
  turn_complete boolean,
  error_code text,
  error_message text,
  interrupted boolean,
  agent_id text,
  PRIMARY KEY ((app_name, user_id, session_id), event_id)
)
    """.strip())

    # App states table
    session.execute(f"""
CREATE TABLE IF NOT EXISTS {keyspace}.app_states (
  app_name text,
  state text,
  update_time timestamp,
  PRIMARY KEY (app_name)
)
    """.strip())

    # User states table
    session.execute(f"""
CREATE TABLE IF NOT EXISTS {keyspace}.user_states (
  app_name text,
  user_id text,
  state text,
  update_time timestamp,
  PRIMARY KEY ((app_name, user_id))
)
    """.strip())

    # Memories table
    session.execute(f"""
CREATE TABLE IF NOT EXISTS {keyspace}.memories (
  app_name text,
  user_id text,
  session_id text,
  events text,
  PRIMARY KEY ((app_name, user_id), session_id)
)
    """.strip())

    # Artifacts table
    session.execute(f"""
CREATE TABLE IF NOT EXISTS {keyspace}.artifacts (
  app_name text,
  user_id text,
  session_id text,
  filename text,
  version int,
  data text,
  PRIMARY KEY ((app_name, user_id, session_id), filename, version)
) WITH CLUSTERING ORDER BY (filename ASC, version DESC)
    """.strip())

    # Logs table
    session.execute(f"""
CREATE TABLE IF NOT EXISTS {keyspace}.logs (
  app_name text,
  user_id text,
  session_id text,
  log_time timestamp,
  level text,
  logger text,
  message text,
  message_idx text,
  agent_id text,
  status text,
  attributes text,
  PRIMARY KEY ((app_name, user_id, session_id), log_time)
) WITH CLUSTERING ORDER BY (log_time ASC)
    """.strip())

    # Agent registry table (store agent definitions)
    session.execute(f"""
CREATE TABLE IF NOT EXISTS {keyspace}.agent_registry (
  org_id text,
  team_id text,
  version text,
  agent_id text,
  definition text,
  PRIMARY KEY ((org_id, team_id), agent_id)
)
""".strip())

    # Shutdown
    session.shutdown()
    cluster.shutdown() 