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


def run(coro):
    loop = asyncio.new_event_loop()
    try:
        asyncio.set_event_loop(loop)
        return loop.run_until_complete(coro)
    finally:
        try:
            loop.run_until_complete(loop.shutdown_asyncgens())
        except Exception:
            pass
        loop.close()


def test_periodic_discovery_triggers_callback():
    base = "https://api.portal.flowerhub.se"
    sess = DummySession()
    asset_owner_id = 42
    asset_id = 99
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
    client.asset_owner_id = asset_owner_id

    called = []

    def cb(fhs):
        called.append(fhs)

    async def _run():
        client.start_periodic_asset_fetch(5, run_immediately=True, on_update=cb)
        await asyncio.sleep(0.01)
        assert client.asset_id == asset_id
        assert len(called) >= 1
        client.stop_periodic_asset_fetch()

    run(_run())
