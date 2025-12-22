import asyncio

import aiohttp
import pytest

from flowerhub_portal_api_client import ApiError
from flowerhub_portal_api_client.async_client import AsyncFlowerhubClient


class DummyResp:
    def __init__(self, status=200, json_data=None, text="", headers=None):
        self.status = status
        self._json = json_data
        self._text = text
        self.headers = headers or {}

    async def text(self):
        return self._text

    async def json(self):
        return self._json


class DummySessionCapture:
    def __init__(self):
        self.calls = []
        self.last_kwargs = None

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
        # capture kwargs to inspect timeout application
        self.last_kwargs = dict(kwargs)
        for idx, (u, r) in enumerate(self.calls):
            if url.startswith(u):
                self.calls.pop(idx)
                return DummySessionCapture._req_ctx(r)
        return DummySessionCapture._req_ctx(
            DummyResp(status=404, json_data=None, text="")
        )


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


def test_retry_5xx_then_success():
    base = "https://api.portal.flowerhub.se"
    sess = DummySessionCapture()
    asset_id = 99
    # initial 5xx triggers retry
    sess.add_response(
        base + f"/asset/{asset_id}",
        DummyResp(status=500, json_data=None, text="", headers={"Retry-After": "0.01"}),
    )
    # success on retry
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
        r = await client.async_fetch_asset(asset_id, retry_5xx_attempts=1)
        assert r["status_code"] == 200
        assert r["asset_info"]["id"] == asset_id
        assert r["flowerhub_status"] is not None

    run(_run())


def test_retry_429_then_success():
    base = "https://api.portal.flowerhub.se"
    sess = DummySessionCapture()
    asset_id = 99
    # Too Many Requests with short Retry-After
    sess.add_response(
        base + f"/asset/{asset_id}",
        DummyResp(status=429, json_data=None, text="", headers={"Retry-After": "0.01"}),
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
        r = await client.async_fetch_asset(asset_id)
        assert r["status_code"] == 200
        assert r["asset_info"]["id"] == asset_id
        assert r["flowerhub_status"] is not None

    run(_run())


def test_on_api_error_callback_invoked_and_raises():
    base = "https://api.portal.flowerhub.se"
    sess = DummySessionCapture()
    # system-notification returns 500 to trigger ApiError via _maybe_raise_http_error
    sess.add_response(
        base + "/system-notification/active-flower",
        DummyResp(status=500, json_data=None, text="{"),
    )

    called = []

    def on_api_error(err: ApiError):
        called.append(err)

    client = AsyncFlowerhubClient(base, session=sess, on_api_error=on_api_error)

    async def _run():
        with pytest.raises(ApiError):
            await client.async_fetch_system_notification("active-flower")

    run(_run())
    assert len(called) == 1
    assert called[0].status_code == 500


def test_timeout_applied_default_and_override():
    base = "https://api.portal.flowerhub.se"
    sess = DummySessionCapture()
    # Provide a benign 200 response so we can inspect kwargs
    sess.add_response(
        base + "/system-notification/test",
        DummyResp(status=200, json_data={"ok": True}, text="{"),
    )

    client = AsyncFlowerhubClient(base, session=sess)
    client.request_timeout_total = 0.5

    async def _run():
        # default client timeout
        await client.async_fetch_system_notification("test")
        assert isinstance(sess.last_kwargs.get("timeout"), aiohttp.ClientTimeout)
        # per-call override
        sess.add_response(
            base + "/system-notification/test2",
            DummyResp(status=200, json_data={"ok": True}, text="{"),
        )
        await client.async_fetch_system_notification("test2", timeout_total=0.2)
        to = sess.last_kwargs.get("timeout")
        assert isinstance(to, aiohttp.ClientTimeout)
        # aiohttp.ClientTimeout exposes total via .total
        assert abs(to.total - 0.2) < 1e-6

    run(_run())


def test_electricity_agreement_invalid_raises_apierror():
    base = "https://api.portal.flowerhub.se"
    sess = DummySessionCapture()
    aoid = 42
    # Return a non-dict payload to trigger parse_electricity_agreement(None)
    sess.add_response(
        base + f"/asset-owner/{aoid}/electricity-agreement",
        DummyResp(status=200, json_data=["unexpected"], text="["),
    )

    client = AsyncFlowerhubClient(base, session=sess)

    async def _run():
        with pytest.raises(ApiError):
            await client.async_fetch_electricity_agreement(aoid)

    run(_run())


def test_invoices_non_list_returns_error_when_no_raise():
    base = "https://api.portal.flowerhub.se"
    sess = DummySessionCapture()
    aoid = 42
    # Payload is dict, not list -> ensure_list error path when raise_on_error=False
    sess.add_response(
        base + f"/asset-owner/{aoid}/invoice",
        DummyResp(status=200, json_data={"not": "a list"}, text="{"),
    )

    client = AsyncFlowerhubClient(base, session=sess)

    async def _run():
        r = await client.async_fetch_invoices(aoid, raise_on_error=False)
        assert r["status_code"] == 200
        assert r["invoices"] is None
        assert isinstance(r["error"], str) and "expected list" in r["error"].lower()

    run(_run())


def test_consumption_non_list_returns_error_when_no_raise():
    base = "https://api.portal.flowerhub.se"
    sess = DummySessionCapture()
    aoid = 42
    # Payload is dict, not list -> ensure_list error path when raise_on_error=False
    sess.add_response(
        base + f"/asset-owner/{aoid}/consumption",
        DummyResp(status=200, json_data={"not": "a list"}, text="{"),
    )

    client = AsyncFlowerhubClient(base, session=sess)

    async def _run():
        r = await client.async_fetch_consumption(aoid, raise_on_error=False)
        assert r["status_code"] == 200
        assert r["consumption"] is None
        assert isinstance(r["error"], str) and "expected list" in r["error"].lower()

    run(_run())
