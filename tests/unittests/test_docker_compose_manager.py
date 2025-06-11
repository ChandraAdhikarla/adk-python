import pytest
import socket
import subprocess
from types import SimpleNamespace

from ai_core.tools.docker_compose_manager import get_service_port, wait_for_port

class DummyResult:
    def __init__(self, stdout: str):
        self.stdout = stdout


def test_get_service_port_success(monkeypatch):
    def fake_run(cmd, check, capture_output, text):
        return SimpleNamespace(stdout="0.0.0.0:49175\n")
    monkeypatch.setattr(subprocess, 'run', fake_run)
    port = get_service_port("validate_1234", "github", 50051)
    assert port == 49175


def test_get_service_port_invalid(monkeypatch):
    def fake_run(cmd, check, capture_output, text):
        return SimpleNamespace(stdout="invalid output\n")
    monkeypatch.setattr(subprocess, 'run', fake_run)
    with pytest.raises(RuntimeError):
        get_service_port("validate_1234", "github", 50051)


def test_wait_for_port_success():
    # Open a listening socket on an ephemeral port
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(('localhost', 0))
    port = s.getsockname()[1]
    s.listen(1)
    try:
        wait_for_port('localhost', port, timeout=2)
    finally:
        s.close()


def test_wait_for_port_timeout():
    # Find an unused port by binding and closing
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(('localhost', 0))
    port = s.getsockname()[1]
    s.close()
    with pytest.raises(TimeoutError):
        wait_for_port('localhost', port, timeout=1) 