import asyncio

from flowerhub_portal_api_client.async_client import AsyncFlowerhubClient


class DummyResp:
    def __init__(self, status=200, json_data=None, text=""):
        self.status = status
        self._json = json_data
        self._text = text

    async def text(self):
        return self._text

    async def json(self):
        return self._json


class DummySession:
    def __init__(self):
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
        # find first matching by prefix and consume it (to emulate sequential responses)
        for idx, (u, r) in enumerate(self.calls):
            if url.startswith(u):
                self.calls.pop(idx)
                return DummySession._req_ctx(r)
        # fallback: return 404 dummy
        return DummySession._req_ctx(DummyResp(status=404, json_data=None, text=""))


def test_async_readout_smoke():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    sess = DummySession()
    base = "https://api.portal.flowerhub.se"
    asset_owner_id = 42
    asset_id = 99
    sess.add_response(
        base + "/auth/login",
        DummyResp(
            status=200, json_data={"user": {"assetOwnerId": asset_owner_id}}, text="{"
        ),
    )
    sess.add_response(
        base + f"/asset-owner/{asset_owner_id}/withAssetId",
        DummyResp(status=200, json_data={"assetId": asset_id}, text="{"),
    )
    sess.add_response(
        base + f"/asset/{asset_id}",
        DummyResp(
            status=200,
            json_data={
                "id": asset_id,
                "flowerHubStatus": {"status": "Connected", "message": "ok"},
            },
            text="{",
        ),
    )

    client = AsyncFlowerhubClient(base, session=sess)

    async def _run():
        await client.async_login("u", "p")
        r = await client.async_readout_sequence()
        assert r["asset_id"] == asset_id
        assert client.flowerhub_status is not None

    loop.run_until_complete(_run())


if __name__ == "__main__":
    test_async_readout_smoke()
