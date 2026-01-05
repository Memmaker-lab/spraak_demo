import pytest
from fastapi.testclient import TestClient


def test_hangup_endpoint_emits_control_events_and_returns_ok(monkeypatch, capsys):
    """
    Control API: POST /control/call/hangup
    - returns ok on success
    - emits control.command_received and control.command_applied
    """
    # Patch the internal delete_room helper to avoid network calls
    from control_plane import control_api

    async def _fake_delete_room(_room_name: str) -> None:
        return None

    monkeypatch.setattr(control_api, "_delete_room", _fake_delete_room)

    from control_plane.webhook_server import app

    client = TestClient(app)
    res = client.post("/control/call/hangup", json={"session_id": "call-123"})
    assert res.status_code == 200
    assert res.json() == {"status": "ok"}

    out = capsys.readouterr().out
    assert "control.command_received" in out
    assert "control.command_applied" in out


def test_hangup_endpoint_returns_stable_error_on_failure(monkeypatch):
    from control_plane import control_api

    async def _fake_delete_room(_room_name: str) -> None:
        raise RuntimeError("boom")

    monkeypatch.setattr(control_api, "_delete_room", _fake_delete_room)

    from control_plane.webhook_server import app
    client = TestClient(app)
    res = client.post("/control/call/hangup", json={"session_id": "call-123"})
    assert res.status_code == 502
    assert res.json()["detail"] == "hangup_failed"


