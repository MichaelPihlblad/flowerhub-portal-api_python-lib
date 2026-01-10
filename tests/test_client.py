import asyncio

# pylint: disable=too-many-lines
from flowerhub_portal_api_client import ApiError, AuthenticationError, FlowerHubStatus
from flowerhub_portal_api_client.async_client import AsyncFlowerhubClient
from flowerhub_portal_api_client.types import (
    AssetOwnerDetails,
    AssetOwnerProfile,
    Revenue,
    UptimeHistoryEntry,
    UptimeMonth,
)


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
        try:
            await client.async_fetch_asset_id(aoid)
            assert False, "Expected ApiError due to invalid assetId"
        except ApiError as e:
            assert "Failed to parse assetId" in str(e)

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
        try:
            await client.async_fetch_asset(asset_id)
            assert False, "Expected ApiError due to missing flowerHubStatus"
        except ApiError as e:
            assert "flowerHubStatus" in str(e)

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


def test_fetch_profile_success():
    sess = DummySession()
    base = "https://api.portal.flowerhub.se"
    aoid = 123
    profile_json = {
        "id": aoid,
        "firstName": "Ada",
        "lastName": "Lovelace",
        "mainEmail": "ada@example.com",
        "contactEmail": None,
        "phone": "+460000000",
        "address": {"street": "Main St 1", "postalCode": "12345", "city": "Göteborg"},
        "accountStatus": "Verified",
        "installer": {
            "id": 77,
            "name": "Installer AB",
            "address": {
                "street": "Installergatan 2",
                "postalCode": "54321",
                "city": "Stockholm",
            },
        },
    }
    sess.add_response(
        base + f"/asset-owner/{aoid}/profile",
        DummyResp(status=200, json_data=profile_json, text="{"),
    )

    client = AsyncFlowerhubClient(base, session=sess)

    async def _run():
        result = await client.async_fetch_asset_owner_profile(aoid)
        assert result["status_code"] == 200
        assert isinstance(result["profile"], AssetOwnerProfile)
        prof = result["profile"]
        assert prof is not None and prof.id == aoid
        assert prof.accountStatus == "Verified"
        assert prof.address.city == "Göteborg"
        assert prof.installer.id == 77

    run(_run())


def test_fetch_profile_invalid_payload_non_dict_returns_error_when_not_raising():
    sess = DummySession()
    base = "https://api.portal.flowerhub.se"
    aoid = 5
    # API returns a list unexpectedly
    sess.add_response(
        base + f"/asset-owner/{aoid}/profile",
        DummyResp(status=200, json_data=[{"id": aoid}], text="["),
    )

    client = AsyncFlowerhubClient(base, session=sess)

    async def _run():
        result = await client.async_fetch_asset_owner_profile(
            aoid, raise_on_error=False
        )
        assert result["status_code"] == 200
        assert result["profile"] is None
        assert (
            isinstance(result["error"], str)
            and "expected dict" in result["error"].lower()
        )

    run(_run())


def test_fetch_asset_owner_details_success():
    sess = DummySession()
    base = "https://api.portal.flowerhub.se"
    aoid = 100
    details_json = {
        "id": aoid,
        "firstName": "Alice",
        "lastName": "Smith",
        "installer": {"id": 42, "name": "Test Installer Co"},
        "distributor": {"id": 23, "name": "Example Distributor AB"},
        "asset": {
            "id": 500,
            "serialNumber": "SN123456789",
            "assetModel": {
                "id": 10,
                "name": "Solar Model X",
                "manufacturer": "TestManufacturer",
            },
        },
        "compensation": {"status": "Qualified", "message": "Qualified"},
        "bessCompensationStartDate": "2024-01-01",
    }
    sess.add_response(
        base + f"/asset-owner/{aoid}",
        DummyResp(status=200, json_data=details_json, text="{"),
    )

    client = AsyncFlowerhubClient(base, session=sess)

    async def _run():
        result = await client.async_fetch_asset_owner(aoid)
        assert result["status_code"] == 200
        assert isinstance(result["details"], AssetOwnerDetails)
        details = result["details"]
        assert details is not None and details.id == aoid
        assert details.firstName == "Alice"
        assert details.lastName == "Smith"
        assert details.installer.id == 42
        assert details.installer.name == "Test Installer Co"
        assert details.distributor.id == 23
        assert details.asset.id == 500
        assert details.asset.serialNumber == "SN123456789"
        assert details.asset.assetModel.manufacturer == "TestManufacturer"
        assert details.compensation.status == "Qualified"
        assert details.bessCompensationStartDate == "2024-01-01"

    run(_run())


def test_fetch_asset_owner_details_missing_id():
    sess = DummySession()
    base = "https://api.portal.flowerhub.se"
    aoid = 10
    # Missing required id field
    sess.add_response(
        base + f"/asset-owner/{aoid}",
        DummyResp(status=200, json_data={"firstName": "Test"}, text="{"),
    )

    client = AsyncFlowerhubClient(base, session=sess)

    async def _run():
        try:
            await client.async_fetch_asset_owner(aoid)
            assert False, "Expected ApiError due to missing id"
        except ApiError as e:
            assert "missing or invalid id" in str(e).lower()

    run(_run())


def test_fetch_asset_owner_details_no_raise_on_invalid():
    sess = DummySession()
    base = "https://api.portal.flowerhub.se"
    aoid = 11
    # Non-dict payload
    sess.add_response(
        base + f"/asset-owner/{aoid}",
        DummyResp(status=200, json_data=[], text="["),
    )

    client = AsyncFlowerhubClient(base, session=sess)

    async def _run():
        result = await client.async_fetch_asset_owner(aoid, raise_on_error=False)
        assert result["status_code"] == 200
        assert result["details"] is None
        assert isinstance(result["error"], str)

    run(_run())


def test_fetch_uptime_available_months_success():
    sess = DummySession()
    base = "https://api.portal.flowerhub.se"
    asset_id = 500
    months_json = [
        {"value": "2025-03", "label": "March 2025"},
        {"value": "2025-04", "label": "April 2025"},
        {"value": "2025-05", "label": "May 2025"},
    ]
    sess.add_response(
        base + f"/asset-uptime/available-months/{asset_id}",
        DummyResp(status=200, json_data=months_json, text="["),
    )

    client = AsyncFlowerhubClient(base, session=sess)
    client.asset_id = asset_id

    async def _run():
        result = await client.async_fetch_available_uptime_months()
        assert result["status_code"] == 200
        months = result["months"]
        assert months is not None and len(months) == 3
        assert isinstance(months[0], UptimeMonth)
        assert months[0].value == "2025-03"
        assert months[-1].label == "May 2025"

    run(_run())


def test_fetch_uptime_available_months_non_list_payload():
    sess = DummySession()
    base = "https://api.portal.flowerhub.se"
    asset_id = 123
    # Endpoint returns non-list unexpectedly
    sess.add_response(
        base + f"/asset-uptime/available-months/{asset_id}",
        DummyResp(status=200, json_data={"value": "2025-03"}, text="{"),
    )

    client = AsyncFlowerhubClient(base, session=sess)

    async def _run():
        result = await client.async_fetch_available_uptime_months(
            asset_id, raise_on_error=False
        )
        assert result["status_code"] == 200
        assert result["months"] is None
        assert isinstance(result["error"], str)

    run(_run())


def test_fetch_uptime_available_months_missing_asset_id():
    client = AsyncFlowerhubClient()
    client.asset_id = None

    async def _run():
        try:
            await client.async_fetch_available_uptime_months()
            assert False, "Expected ValueError due to missing asset_id"
        except ValueError as e:
            assert "asset_id" in str(e)

    run(_run())


def test_fetch_uptime_history_success():
    sess = DummySession()
    base = "https://api.portal.flowerhub.se"
    asset_id = 600
    history_json = [
        {"date": "2025-03", "uptime": 100},
        {"date": "2025-04", "uptime": 99},
        {"date": "2025-05", "uptime": 92},
    ]
    sess.add_response(
        base + f"/asset-uptime/bar-chart/history/{asset_id}",
        DummyResp(status=200, json_data=history_json, text="["),
    )

    client = AsyncFlowerhubClient(base, session=sess)
    client.asset_id = asset_id

    async def _run():
        result = await client.async_fetch_uptime_history()
        assert result["status_code"] == 200
        history = result["history"]
        assert history is not None and len(history) == 3
        assert isinstance(history[0], UptimeHistoryEntry)
        assert history[0].date == "2025-03"
        assert history[-1].uptime == 92

    run(_run())


def test_fetch_uptime_history_non_list_payload():
    sess = DummySession()
    base = "https://api.portal.flowerhub.se"
    asset_id = 601
    # Endpoint returns non-list unexpectedly
    sess.add_response(
        base + f"/asset-uptime/bar-chart/history/{asset_id}",
        DummyResp(status=200, json_data={"date": "2025-03"}, text="{"),
    )

    client = AsyncFlowerhubClient(base, session=sess)

    async def _run():
        result = await client.async_fetch_uptime_history(asset_id, raise_on_error=False)
        assert result["status_code"] == 200
        assert result["history"] is None
        assert isinstance(result["error"], str)

    run(_run())


def test_fetch_uptime_history_missing_asset_id():
    client = AsyncFlowerhubClient()
    client.asset_id = None

    async def _run():
        try:
            await client.async_fetch_uptime_history()
            assert False, "Expected ValueError due to missing asset_id"
        except ValueError as e:
            assert "asset_id" in str(e)

    run(_run())


def test_fetch_revenue_success():
    sess = DummySession()
    base = "https://api.portal.flowerhub.se"
    asset_id = 800
    revenue_json = {
        "id": 74,
        "minAvailablePower": 5,
        "compensation": 300,
        "compensationPerKW": 60,
    }
    sess.add_response(
        base + f"/asset/{asset_id}/revenue",
        DummyResp(status=200, json_data=revenue_json, text="{"),
    )

    client = AsyncFlowerhubClient(base, session=sess)
    client.asset_id = asset_id

    async def _run():
        result = await client.async_fetch_revenue()
        assert result["status_code"] == 200
        rev = result["revenue"]
        assert isinstance(rev, Revenue)
        assert rev.id == 74
        assert rev.minAvailablePower == 5
        assert rev.compensationPerKW == 60

    run(_run())


def test_fetch_revenue_non_dict_payload():
    sess = DummySession()
    base = "https://api.portal.flowerhub.se"
    asset_id = 801
    sess.add_response(
        base + f"/asset/{asset_id}/revenue",
        DummyResp(status=200, json_data=[{"id": 1}], text="["),
    )

    client = AsyncFlowerhubClient(base, session=sess)

    async def _run():
        result = await client.async_fetch_revenue(asset_id, raise_on_error=False)
        assert result["status_code"] == 200
        assert result["revenue"] is None
        assert isinstance(result["error"], str)

    run(_run())


def test_fetch_revenue_missing_asset_id():
    client = AsyncFlowerhubClient()
    client.asset_id = None

    async def _run():
        try:
            await client.async_fetch_revenue()
            assert False, "Expected ValueError due to missing asset_id"
        except ValueError as e:
            assert "asset_id" in str(e)

    run(_run())


def test_fetch_uptime_pie_success():
    sess = DummySession()
    base = "https://api.portal.flowerhub.se"
    asset_id = 700
    slices_json = [
        {"name": "uptime", "value": 2500000},
        {"name": "downtime", "value": 5000},
        {"name": "noData", "value": 0},
    ]
    # Match by prefix; omit query to allow startswith() to match
    sess.add_response(
        base + f"/asset-uptime/pie-chart/{asset_id}",
        DummyResp(status=200, json_data=slices_json, text="["),
    )

    client = AsyncFlowerhubClient(base, session=sess)
    client.asset_id = asset_id

    async def _run():
        result = await client.async_fetch_uptime_pie(period="2025-05")
        assert result["status_code"] == 200
        assert result["uptime"] == 2500000
        assert result["downtime"] == 5000
        assert result["noData"] == 0
        assert result["uptime_ratio_total"] is not None
        assert result["uptime_ratio_total"] > 99.0  # Should be very high uptime
        assert result["uptime_ratio_actual"] is not None
        assert (
            result["uptime_ratio_actual"] > 99.0
        )  # Should be very high when excluding noData

    run(_run())


def test_fetch_uptime_pie_non_list_payload():
    sess = DummySession()
    base = "https://api.portal.flowerhub.se"
    asset_id = 701
    sess.add_response(
        base + f"/asset-uptime/pie-chart/{asset_id}",
        DummyResp(status=200, json_data={"name": "uptime"}, text="{"),
    )

    client = AsyncFlowerhubClient(base, session=sess)

    async def _run():
        result = await client.async_fetch_uptime_pie(
            asset_id, period="2025-06", raise_on_error=False
        )
        assert result["status_code"] == 200
        assert result["uptime"] is None
        assert result["downtime"] is None
        assert result["noData"] is None
        assert isinstance(result["error"], str)

    run(_run())


def test_fetch_uptime_pie_missing_asset_id():
    client = AsyncFlowerhubClient()
    client.asset_id = None

    async def _run():
        try:
            await client.async_fetch_uptime_pie(period="2025-06")
            assert False, "Expected ValueError due to missing asset_id"
        except ValueError as e:
            assert "asset_id" in str(e)

    run(_run())


def test_fetch_uptime_pie_missing_or_invalid_period():
    sess = DummySession()
    base = "https://api.portal.flowerhub.se"
    asset_id = 702
    client = AsyncFlowerhubClient(base, session=sess)
    client.asset_id = asset_id

    async def _run():
        # Missing period defaults to current month, should not raise
        # Add a response that matches the default period format
        slices_json = [
            {"name": "uptime", "value": 2500000},
        ]
        sess.add_response(
            base + f"/asset-uptime/pie-chart/{asset_id}",
            DummyResp(status=200, json_data=slices_json, text="["),
        )
        result = await client.async_fetch_uptime_pie()
        assert result["status_code"] == 200
        assert result["uptime"] == 2500000
        assert result["uptime_ratio_total"] is not None

        # Invalid blank period should raise ValueError
        try:
            await client.async_fetch_uptime_pie(period="   ")
            assert False, "Expected ValueError due to invalid period"
        except ValueError as e:
            assert "period" in str(e)

    run(_run())
