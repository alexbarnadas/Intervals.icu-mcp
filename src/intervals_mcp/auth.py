"""Authentication strategies.

The rest of the server only sees `AuthProvider.apply()`, so swapping the
dev API key for OAuth later changes nothing in client.py or the tools.
"""
import os
from typing import Protocol

import httpx


class AuthProvider(Protocol):
    def apply(self, headers: dict[str, str]) -> httpx.Auth | None:
        """Mutate headers and/or return an httpx.Auth for the request."""


class ApiKeyAuth:
    """Dev-only: intervals.icu personal API key via HTTP Basic."""

    def __init__(self, api_key: str):
        self._auth = httpx.BasicAuth("API_KEY", api_key)

    def apply(self, headers: dict[str, str]) -> httpx.Auth | None:
        return self._auth


# class OAuthAuth: planned. Auth-code flow, token kept in the OS keyring,
# refreshed transparently. Needs a registered intervals.icu OAuth app first.


def load_auth() -> AuthProvider:
    key = os.environ.get("INTERVALS_API_KEY")
    if key:
        return ApiKeyAuth(key)
    raise RuntimeError(
        "No credentials. Set INTERVALS_API_KEY (dev) — OAuth login is not built yet."
    )
