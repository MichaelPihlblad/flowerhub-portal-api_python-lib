import asyncio

from flowerhub_portal_api_client import AuthenticationError, FlowerHubStatus
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


def test_refresh_token_fails_then_retries():
    """Test 401 with failed refresh-token then 401 again on retry raises AuthenticationError."""
    sess = DummySession()
    base = "https://api.portal.flowerhub.se"
    asset_owner_id = 42
    # first attempt returns 401
    sess.add_response(
        base + f"/asset-owner/{asset_owner_id}/withAssetId",
        DummyResp(status=401, json_data=None, text=""),
    )
    # refresh attempt fails (500)
    sess.add_response(
        base + "/auth/refresh-token",
        DummyResp(status=500, json_data=None, text=""),
    )
    # retry original request also fails (401 again)
    sess.add_response(
        base + f"/asset-owner/{asset_owner_id}/withAssetId",
        DummyResp(status=401, json_data=None, text=""),
    )

    callback_invoked = []

    def auth_failed_callback():
        callback_invoked.append(True)

    client = AsyncFlowerhubClient(
        base, session=sess, on_auth_failed=auth_failed_callback
    )

    async def _run():
        # Should raise AuthenticationError after failed refresh and retry
        try:
            await client.async_fetch_asset_id(asset_owner_id)
            assert False, "Expected AuthenticationError to be raised"
        except AuthenticationError as e:
            assert "refresh failed" in str(e).lower()
            assert "login again" in str(e).lower()

    run(_run())
    # Verify callback was invoked
    assert len(callback_invoked) == 1


def test_refresh_token_updates_asset_owner_id():
    """Test that 401 refresh successfully updates asset_owner_id from response."""
    sess = DummySession()
    base = "https://api.portal.flowerhub.se"
    old_aoid = 42
    new_aoid = 99
    asset_id = 55
    # first attempt returns 401
    sess.add_response(
        base + f"/asset-owner/{old_aoid}/withAssetId",
        DummyResp(status=401, json_data=None, text=""),
    )
    # refresh returns new assetOwnerId
    sess.add_response(
        base + "/auth/refresh-token",
        DummyResp(
            status=200,
            json_data={"user": {"assetOwnerId": new_aoid}},
            text="{",
        ),
    )
    # retry succeeds
    sess.add_response(
        base + f"/asset-owner/{old_aoid}/withAssetId",
        DummyResp(status=200, json_data={"assetId": asset_id}, text="{"),
    )

    client = AsyncFlowerhubClient(base, session=sess)
    client.asset_owner_id = old_aoid

    async def _run():
        await client.async_fetch_asset_id(old_aoid)
        # asset_owner_id should be updated from refresh response
        assert client.asset_owner_id == new_aoid

    run(_run())


def test_safe_int_with_invalid_input():
    """Test _safe_int helper with various invalid inputs."""
    assert AsyncFlowerhubClient._safe_int("not_a_number") is None
    assert AsyncFlowerhubClient._safe_int(None) is None
    assert AsyncFlowerhubClient._safe_int([]) is None
    assert AsyncFlowerhubClient._safe_int("42") == 42
    assert AsyncFlowerhubClient._safe_int(42.5) == 42


def test_safe_float_with_invalid_input():
    """Test _safe_float helper with various invalid inputs."""
    assert AsyncFlowerhubClient._safe_float("not_a_float") is None
    assert AsyncFlowerhubClient._safe_float(None) is None
    assert AsyncFlowerhubClient._safe_float([]) is None
    assert AsyncFlowerhubClient._safe_float("3.14") == 3.14
    assert AsyncFlowerhubClient._safe_float(42) == 42.0


def test_parse_agreement_state_with_none():
    """Test _parse_agreement_state with None and empty dict."""
    result = AsyncFlowerhubClient._parse_agreement_state({})
    assert result.stateCategory is None
    assert result.stateId is None
    assert result.siteId is None
    assert result.startDate is None
    assert result.terminationDate is None


def test_parse_electricity_agreement_with_none():
    """Test _parse_electricity_agreement with None input."""
    result = AsyncFlowerhubClient._parse_electricity_agreement(None)
    assert result is None

    result = AsyncFlowerhubClient._parse_electricity_agreement("not_a_dict")
    assert result is None

    result = AsyncFlowerhubClient._parse_electricity_agreement({})
    assert result.consumption is None
    assert result.production is None


def test_parse_invoice_line_with_minimal_data():
    """Test _parse_invoice_line with missing optional fields."""
    payload = {}
    result = AsyncFlowerhubClient._parse_invoice_line(payload)
    assert result.item_id == ""
    assert result.name == ""
    assert result.description == ""
    assert result.price == ""
    assert result.volume == ""
    assert result.amount == ""
    assert result.settlements == []


def test_parse_invoices_with_none():
    """Test _parse_invoices with None and non-list inputs."""
    assert AsyncFlowerhubClient._parse_invoices(None) is None
    assert AsyncFlowerhubClient._parse_invoices("not_a_list") is None
    assert AsyncFlowerhubClient._parse_invoices(42) is None

    result = AsyncFlowerhubClient._parse_invoices([])
    assert result == []

    result = AsyncFlowerhubClient._parse_invoices([None, {"id": "1"}])
    assert len(result) == 1
    assert result[0].id == "1"


def test_parse_consumption_with_none():
    """Test _parse_consumption with None and non-list inputs."""
    assert AsyncFlowerhubClient._parse_consumption(None) is None
    assert AsyncFlowerhubClient._parse_consumption("not_a_list") is None
    assert AsyncFlowerhubClient._parse_consumption(42) is None

    result = AsyncFlowerhubClient._parse_consumption([])
    assert result == []

    result = AsyncFlowerhubClient._parse_consumption([None, {"site_id": "123"}])
    assert len(result) == 1
    assert result[0].site_id == "123"


def test_login_with_invalid_response():
    """Test async_login with malformed response."""
    sess = DummySession()
    base = "https://api.portal.flowerhub.se"
    sess.add_response(
        base + "/auth/login",
        DummyResp(status=200, json_data={"no_user_key": {}}, text="{"),
    )

    client = AsyncFlowerhubClient(base, session=sess)

    async def _run():
        result = await client.async_login("user", "pass")
        assert result["status_code"] == 200
        # asset_owner_id should remain None when user key is missing
        assert client.asset_owner_id is None

    run(_run())


def test_fetch_asset_id_with_invalid_response():
    """Test async_fetch_asset_id with malformed assetId."""
    sess = DummySession()
    base = "https://api.portal.flowerhub.se"
    aoid = 42
    sess.add_response(
        base + f"/asset-owner/{aoid}/withAssetId",
        DummyResp(status=200, json_data={"assetId": "not_a_number"}, text="{"),
    )

    client = AsyncFlowerhubClient(base, session=sess)

    async def _run():
        await client.async_fetch_asset_id(aoid)
        # asset_id should remain None due to failed int conversion
        assert client.asset_id is None

    run(_run())


def test_fetch_asset_with_missing_status():
    """Test async_fetch_asset with missing flowerHubStatus."""
    sess = DummySession()
    base = "https://api.portal.flowerhub.se"
    asset_id = 99
    sess.add_response(
        base + f"/asset/{asset_id}",
        DummyResp(
            status=200,
            json_data={"id": asset_id},  # missing flowerHubStatus
            text="{",
        ),
    )

    client = AsyncFlowerhubClient(base, session=sess)

    async def _run():
        await client.async_fetch_asset(asset_id)
        # flowerhub_status should remain None
        assert client.flowerhub_status is None

    run(_run())


def test_consumption_fetch_missing_asset_owner_id():
    """Test async_fetch_consumption raises ValueError when asset_owner_id is None."""
    client = AsyncFlowerhubClient()
    client.asset_owner_id = None

    async def _run():
        try:
            await client.async_fetch_consumption()
            raised = False
        except ValueError as e:
            raised = True
            assert "asset_owner_id" in str(e)
        assert raised

    run(_run())


def test_readout_sequence_missing_asset_owner_id():
    """Test async_readout_sequence raises ValueError when asset_owner_id is None."""
    client = AsyncFlowerhubClient()
    client.asset_owner_id = None

    async def _run():
        try:
            await client.async_readout_sequence()
            raised = False
        except ValueError as e:
            raised = True
            assert "asset_owner_id" in str(e)
        assert raised

    run(_run())
