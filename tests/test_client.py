import asyncio

from flowerhub_portal_api_client import FlowerHubStatus
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


def test_login_and_fetch():
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
        info = await client.async_login("user@example.com", "password")
        assert info["status_code"] == 200
        assert client.asset_owner_id == asset_owner_id
        r = await client.async_readout_sequence()
        assert r["asset_id"] == asset_id
        assert client.asset_info is not None and client.asset_info.get("id") == asset_id
        assert client.flowerhub_status is not None

    run(_run())


def test_refresh_on_401():
    sess = DummySession()
    base = "https://api.portal.flowerhub.se"
    asset_owner_id = 42
    asset_id = 99
    # first attempt to withAssetId returns 401
    sess.add_response(
        base + f"/asset-owner/{asset_owner_id}/withAssetId",
        DummyResp(status=401, json_data=None, text=""),
    )
    # refresh succeeds and returns some json
    sess.add_response(
        base + "/auth/refresh-token",
        DummyResp(status=200, json_data={"ok": True}, text="{"),
    )
    # subsequent attempt returns the asset id
    sess.add_response(
        base + f"/asset-owner/{asset_owner_id}/withAssetId",
        DummyResp(
            status=200, json_data={"id": asset_owner_id, "assetId": asset_id}, text="{"
        ),
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
        r = await client.async_readout_sequence(asset_owner_id)
        assert r["asset_id"] == asset_id
        assert client.asset_info is not None and client.asset_info.get("id") == asset_id

    run(_run())


def test_flowerhub_status_timestamp_updates():
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
    asset_json = {
        "id": asset_id,
        "flowerHubStatus": {
            "status": "Connected",
            "message": "InverterDongleFoundAndComponentsAreRunning",
        },
    }
    sess.add_response(
        base + f"/asset/{asset_id}",
        DummyResp(status=200, json_data=asset_json, text="{"),
    )

    client = AsyncFlowerhubClient(base, session=sess)

    async def _run():
        await client.async_login("user@example.com", "password")
        await client.async_readout_sequence()
        first_ts = client.flowerhub_status.updated_at
        assert first_ts is not None
        # add another response and re-fetch asset
        sess.add_response(
            base + f"/asset/{asset_id}",
            DummyResp(status=200, json_data=asset_json, text="{"),
        )
        await client.async_fetch_asset()
        second_ts = client.flowerhub_status.updated_at
        assert second_ts is not None and second_ts >= first_ts

    run(_run())


def test_periodic_start_too_short_raises():
    client = AsyncFlowerhubClient()
    try:
        client.start_periodic_asset_fetch(1)
        raised = False
    except ValueError:
        raised = True
    assert raised


def test_periodic_start_and_stop_runs_and_stops():
    sess = DummySession()
    base = "https://api.portal.flowerhub.se"
    asset_owner_id = 42
    asset_id = 99
    # ensure discovery can run
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

    async def _run():
        client.start_periodic_asset_fetch(5, run_immediately=True)
        # let scheduled task run initial fetch
        await asyncio.sleep(0.01)
        assert client.is_asset_fetch_running()
        client.stop_periodic_asset_fetch()
        await asyncio.sleep(0)
        assert not client.is_asset_fetch_running()

    run(_run())


def test_periodic_callback_and_queue():
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
                "flowerHubStatus": {
                    "status": "Connected",
                    "message": "InverterDongleFoundAndComponentsAreRunning",
                },
            },
            text="{",
        ),
    )

    client = AsyncFlowerhubClient(base, session=sess)

    async def _run():
        await client.async_login("user@example.com", "password")
        called = []
        q = asyncio.Queue()

        def cb(fhs: FlowerHubStatus):
            called.append(fhs)

        client.start_periodic_asset_fetch(
            5, run_immediately=True, on_update=cb, result_queue=q
        )
        # let it run the initial fetch
        await asyncio.sleep(0.01)
        assert len(called) >= 1
        assert not q.empty()
        v = q.get_nowait()
        assert isinstance(v, FlowerHubStatus)
        client.stop_periodic_asset_fetch()

    run(_run())
