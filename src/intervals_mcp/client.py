import httpx

from .auth import AuthProvider

BASE_URL = "https://intervals.icu/api/v1"


class IntervalsClient:
    def __init__(self, auth: AuthProvider):
        headers: dict[str, str] = {}
        self._http = httpx.AsyncClient(
            base_url=BASE_URL,
            auth=auth.apply(headers),
            headers=headers,
            timeout=30,
        )

    async def get(self, path: str, **params):
        r = await self._http.get(path, params={k: v for k, v in params.items() if v is not None})
        r.raise_for_status()
        return r.json()

    async def post(self, path: str, *, json=None):
        r = await self._http.post(path, json=json)
        r.raise_for_status()
        return r.json()

    async def put(self, path: str, *, json=None, params=None):
        r = await self._http.put(path, json=json, params=params)
        r.raise_for_status()
        return r.json()

    async def delete(self, path: str):
        r = await self._http.delete(path)
        r.raise_for_status()
