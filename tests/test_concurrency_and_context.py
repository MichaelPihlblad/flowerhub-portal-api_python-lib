import asyncio

from flowerhub_portal_api_client.async_client import AsyncFlowerhubClient


class DummyResp:
    def __init__(
        self, status=200, json_data=None, text="", headers=None, *, delay_enter=0.0
    ):
        self.status = status
        self._json = json_data
        self._text = text
        self.headers = headers or {}
        self._delay_enter = float(delay_enter)

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
            # simulate network delay on entering the context
            if getattr(self._resp, "_delay_enter", 0.0) > 0:
                await asyncio.sleep(self._resp._delay_enter)
            return self._resp

        async def __aexit__(self, exc_type, exc, tb):
            return False

    def add_response(self, url, resp: DummyResp):
        self.calls.append((url, resp))

    async def request(self, method, url, headers=None, **kwargs):
        for idx, (u, r) in enumerate(self.calls):
            if url.startswith(u):
                self.calls.pop(idx)
                return DummySession._req_ctx(r)
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


def test_concurrency_limiter_serializes_requests():
    base = "https://api.portal.flowerhub.se"
    sess = DummySession()
    asset_id = 1
    # two asset responses; each has delay on enter to simulate network duration
    payload = {
        "id": asset_id,
        "flowerHubStatus": {"status": "Connected", "message": "ok"},
    }
    sess.add_response(
        base + f"/asset/{asset_id}",
        DummyResp(status=200, json_data=payload, text="{", delay_enter=0.03),
    )
    sess.add_response(
        base + f"/asset/{asset_id}",
        DummyResp(status=200, json_data=payload, text="{", delay_enter=0.03),
    )

    client = AsyncFlowerhubClient(base, session=sess)
    client.set_max_concurrency(1)

    async def _run():
        start = asyncio.get_running_loop().time()
        # fire two requests concurrently; semaphore(1) should serialize them
        await asyncio.gather(
            client.async_fetch_asset(asset_id),
            client.async_fetch_asset(asset_id),
        )
        elapsed = asyncio.get_running_loop().time() - start
        # since both have 30ms delay, serialized total should exceed ~60ms
        assert elapsed >= 0.055

    run(_run())


def test_context_manager_closes_periodic_fetch():
    base = "https://api.portal.flowerhub.se"
    sess = DummySession()
    asset_owner_id = 42
    asset_id = 99
    # discovery responses
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

    async def _run():
        async with AsyncFlowerhubClient(base, session=sess) as client:
            client.asset_owner_id = asset_owner_id
            # start periodic fetch and ensure it is running
            client.start_periodic_asset_fetch(5, run_immediately=True)
            await asyncio.sleep(0.01)
            assert client.is_asset_fetch_running()
        # after exiting context, periodic task should be stopped
        # attribute is reset to None by stop_periodic_asset_fetch in close()
        assert not client.is_asset_fetch_running()

    run(_run())
