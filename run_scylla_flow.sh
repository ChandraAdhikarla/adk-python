#!/usr/bin/env bash
set -euo pipefail

# Ensure this script is run from the adk-python directory
dir=$(pwd)
echo "Working directory: $dir"

# Activate the virtual environment
if [ -f "/workspace/.venv/bin/activate" ]; then
  source /workspace/.venv/bin/activate
else
  echo "Virtual environment not found at .venv. Make sure you've run 'uv venv .venv'."
  exit 1
fi

echo "\n--- Phase 0: Seeding ScyllaDB keyspace for demo-org/devops ---"
pushd ../db > /dev/null
# Default to origon keyspace (matches setup_and_seed.py schema)
export SCYLLA_HOSTS="${SCYLLA_HOSTS:-10.4.137.109}"
export SCYLLA_KEYSPACE="${SCYLLA_KEYSPACE:-origon_adk}"
# Run schema creation + seed demo data
python setup_and_seed.py
popd > /dev/null

echo "\n--- Phase 1: Launching API server in Scylla mode ---"
export ADK_STORAGE_BACKEND=scylla
export ADK_TEAM_ID=devops
export ADK_VERSION=v1
nohup uvicorn api_server:app --reload > server.log 2>&1 &
SERVER_PID=$!
echo "Server PID: $SERVER_PID"

# Wait until the agent listing endpoint is healthy
echo -n "Waiting for API server to be ready"
until curl -s "http://localhost:8000/agents?app_name=demo-org" > /dev/null; do
  echo -n "."
  sleep 1
done

echo "\nServer is up!"

# Utility: pretty-print with jq if available
JQ=""
if command -v jq > /dev/null; then
  JQ="| jq"
fi

echo "\n--- Phase 2: List all agents ---"
eval "curl -s \"http://localhost:8000/agents?app_name=demo-org\" $JQ"

echo "\n--- Phase 3: Fetch 'deploy' agent definition ---"
eval "curl -s \"http://localhost:8000/agents/deploy?app_name=demo-org\" $JQ"

echo "\n--- Phase 4: Create a new session for 'alice' ---"
SESSION_ID=$(curl -s -X POST "http://localhost:8000/sessions?app_name=demo-org&user_id=alice" | jq -r '.session_id')
echo "Created session ID: $SESSION_ID"

echo "\n--- Phase 5: Run the 'deploy' agent ---"
eval "curl -s -X POST http://localhost:8000/run \
  -H 'Content-Type: application/json' \
  -d '{"agent_id":"deploy","app_name":"demo-org","user_id":"alice","session_id":"'${SESSION_ID}'","message":{"role":"user","parts":[{"text":"Please deploy version v2 to prod"}]}}' $JQ"

echo "\n--- Phase 6: List logs for the session ---"
eval "curl -s \"http://localhost:8000/sessions/${SESSION_ID}/logs?app_name=demo-org&user_id=alice\" $JQ"

echo "\n--- Phase 7: List artifacts for the session ---"
eval "curl -s \"http://localhost:8000/sessions/${SESSION_ID}/artifacts?app_name=demo-org&user_id=alice\" $JQ"

echo "\n--- Done. Shutting down API server (PID $SERVER_PID) ---"
kill $SERVER_PID
exit 0 