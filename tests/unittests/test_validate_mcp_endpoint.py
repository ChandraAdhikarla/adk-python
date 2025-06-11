import os
import pytest
from fastapi.testclient import TestClient
from ai_core.adk_python.api_server import app

# Fixtures to stub out container orchestration and MCP connection
@pytest.fixture(autouse=True)
def patch_container_and_mcp(monkeypatch):
    # Stub docker compose manager functions
    monkeypatch.setattr('ai_core.tools.docker_compose_manager.up_compose', lambda *args, **kwargs: None)
    monkeypatch.setattr('ai_core.tools.docker_compose_manager.down_compose', lambda *args, **kwargs: None)
    monkeypatch.setattr('ai_core.tools.docker_compose_manager.get_service_port', lambda project, service, port: 12345)
    monkeypatch.setattr('ai_core.tools.docker_compose_manager.wait_for_port', lambda host, port, timeout: None)

    # Stub MCPToolset.from_server to simulate valid and invalid tokens
    class DummyToolset:
        @classmethod
        async def from_server(cls, params):
            if 'invalid' in params.get('grpc_server', ''):
                raise RuntimeError("Connection failed")
            return cls()

        @property
        def tools(self):
            return []

    monkeypatch.setattr('src.google.adk.tools.mcp_tool.MCPToolset', DummyToolset)

    yield

client = TestClient(app)

# Test GitHub validation success
def test_validate_github_success():
    payload = {"service": "github", "token": "valid_token"}
    response = client.post("/validate_mcp_token", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert "container_name" in data
    assert data["valid"] is True

# Test GitHub validation invalid (simulate invalid by injecting 'invalid' in port)
def test_validate_github_invalid(monkeypatch):
    # Force get_service_port to return an 'invalid' port mapping path to trigger failure
    monkeypatch.setattr('ai_core.tools.docker_compose_manager.get_service_port', lambda project, service, port: int('invalid'), raising=False)
    payload = {"service": "github", "token": "invalid"}
    response = client.post("/validate_mcp_token", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["valid"] is False

# Test Slack missing parameters
def test_validate_slack_missing_fields():
    payload = {"service": "slack", "token": "x", "slack_team_id": None, "slack_channel_ids": None}
    response = client.post("/validate_mcp_token", json=payload)
    assert response.status_code == 400

# Test Slack validation success
def test_validate_slack_success():
    payload = {
        "service": "slack",
        "token": "valid_token",
        "slack_team_id": "T123",
        "slack_channel_ids": "C123"
    }
    response = client.post("/validate_mcp_token", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["valid"] is True 