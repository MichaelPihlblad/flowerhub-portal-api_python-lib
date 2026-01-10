"""Run a minimal async demo using a fake aiohttp-like session.

This mirrors the previous synchronous `simulated_run` but uses the async
client so it remains a small, dependency-free smoke test.
"""

import asyncio
import sys
from pathlib import Path
from typing import cast

# Add parent directory to path so we can import flowerhub_portal_api_client
sys.path.insert(0, str(Path(__file__).parent.parent))

# pylint: disable=wrong-import-position
from flowerhub_portal_api_client import AsyncFlowerhubClient


class DummyResp:
    def __init__(self, status=200, json_data=None, text=""):
        self.status = status
        self._json = json_data or {}
        self._text = text

    async def text(self):
        return self._text or ""

    async def json(self):
        return self._json


class DummySession:
    def __init__(self, asset_owner_id=99, asset_id=166):
        self.asset_owner_id = asset_owner_id
        self.asset_id = asset_id
        self.cookies = {}
        self.calls = []

    class _req_ctx:
        def __init__(self, resp):
            self._resp = resp

        async def __aenter__(self):
            return self._resp

        async def __aexit__(self, exc_type, exc, tb):
            return False

    def add_response(self, url, resp: DummyResp):
        self.calls.append((url, resp))

    async def request(self, method, url, headers=None, **kwargs):
        # emulate auth endpoints and asset responses by prefix
        if url.endswith("/auth/login"):
            self.cookies["Authentication"] = "jwtaccess-dummy"
            self.cookies["Refresh"] = "jwtrefresh-dummy"
            return DummySession._req_ctx(
                DummyResp(
                    status=200,
                    json_data={"user": {"assetOwnerId": self.asset_owner_id}},
                )
            )
        if url.endswith("/auth/refresh-token"):
            self.cookies["Authentication"] = "jwtaccess-dummy2"
            return DummySession._req_ctx(DummyResp(status=200, json_data={"ok": True}))
        if f"/asset-owner/{self.asset_owner_id}/withAssetId" in url:
            if "Authentication" in self.cookies:
                return DummySession._req_ctx(
                    DummyResp(
                        status=200,
                        json_data={"id": self.asset_owner_id, "assetId": self.asset_id},
                    )
                )
            return DummySession._req_ctx(DummyResp(status=401))
        if url.endswith(f"/asset/{self.asset_id}"):
            if "Authentication" in self.cookies:
                return DummySession._req_ctx(
                    DummyResp(
                        status=200,
                        json_data={
                            "id": self.asset_id,
                            "flowerHubStatus": {
                                "status": "Connected",
                                "message": "InverterDongleFoundAndComponentsAreRunning",
                            },
                        },
                    )
                )
            return DummySession._req_ctx(DummyResp(status=401))
        return DummySession._req_ctx(DummyResp(status=404))


def run_demo():
    asset_owner_id = 42
    asset_id = 99

    async def _run():
        sess = DummySession(asset_owner_id, asset_id)
        client = AsyncFlowerhubClient(session=cast(object, sess))
        await client.async_login("user@example.com", "secret")
        print("Login asset_owner_id:", client.asset_owner_id)
        ro = await client.async_readout_sequence()
        print("readout:", ro["asset_id"], client.asset_info)

        # simulate expired auth and refresh behavior
        sess.cookies.pop("Authentication", None)
        # trigger discovery/refresh by calling fetch_asset_id which will get 401 then refresh
        await client.async_fetch_asset_id(asset_owner_id)
        print("after refresh asset_id:", client.asset_id)

    asyncio.run(_run())


if __name__ == "__main__":
    run_demo()
