import pytest

from intervals_mcp.safety import check_event_name, forbid, prefixed


def test_safe_by_default(monkeypatch):
    monkeypatch.delenv("INTERVALS_MCP_SAFE", raising=False)
    assert prefixed("Fartlek") == "TEST - Fartlek"
    assert prefixed("TEST - Fartlek") == "TEST - Fartlek"  # idempotent


def test_only_test_events_can_change(monkeypatch):
    monkeypatch.delenv("INTERVALS_MCP_SAFE", raising=False)
    check_event_name("TEST - probe")
    for name in ("MyCoachLM - 4x8min", "Fartlek", "", None):
        with pytest.raises(PermissionError):
            check_event_name(name)


def test_real_data_tools_forbidden(monkeypatch):
    monkeypatch.delenv("INTERVALS_MCP_SAFE", raising=False)
    with pytest.raises(PermissionError):
        forbid("update_sport_settings")


def test_unsafe_mode_lifts_everything(monkeypatch):
    monkeypatch.setenv("INTERVALS_MCP_SAFE", "0")
    assert prefixed("Fartlek") == "Fartlek"
    check_event_name("MyCoachLM - 4x8min")
    forbid("update_sport_settings")
