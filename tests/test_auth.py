import pytest

from intervals_mcp.auth import ApiKeyAuth, BearerAuth, load_auth
from intervals_mcp.client import IntervalsClient


def test_bearer_sets_authorization_header():
    headers: dict[str, str] = {}
    assert BearerAuth("tok").apply(headers) is None
    assert headers == {"Authorization": "Bearer tok"}


def test_client_sends_the_bearer_header():
    client = IntervalsClient(BearerAuth("tok"))
    assert client._http.headers["Authorization"] == "Bearer tok"


def test_access_token_wins_over_api_key(monkeypatch):
    monkeypatch.setenv("INTERVALS_ACCESS_TOKEN", "tok")
    monkeypatch.setenv("INTERVALS_API_KEY", "key")
    assert isinstance(load_auth(), BearerAuth)


def test_api_key_still_works(monkeypatch):
    monkeypatch.delenv("INTERVALS_ACCESS_TOKEN", raising=False)
    monkeypatch.setenv("INTERVALS_API_KEY", "key")
    assert isinstance(load_auth(), ApiKeyAuth)


def test_no_credentials_raises(monkeypatch):
    monkeypatch.delenv("INTERVALS_ACCESS_TOKEN", raising=False)
    monkeypatch.delenv("INTERVALS_API_KEY", raising=False)
    with pytest.raises(RuntimeError):
        load_auth()
