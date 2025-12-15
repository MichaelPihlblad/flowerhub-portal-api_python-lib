"""Async Flowerhub client suitable for Home Assistant integrations.

This module implements `AsyncFlowerhubClient` built on top of `aiohttp.ClientSession`.
It mirrors the synchronous API in `flowerhub_client.client` with async methods
so it can be used with Home Assistant's event loop and `DataUpdateCoordinator`.
"""

from __future__ import annotations

import asyncio
import datetime
import logging
from typing import Any, Dict, Optional

try:
    import aiohttp
except Exception:  # pragma: no cover - optional dependency
    aiohttp = None

from dataclasses import dataclass
from typing import Any, Dict, List, Optional

try:
    import aiohttp
except Exception:  # pragma: no cover - optional dependency
    aiohttp = None


@dataclass
class User:
    """User information returned from login."""
    id: int
    email: str
    role: int
    name: Optional[str]
    distributorId: Optional[int]
    installerId: Optional[int]
    assetOwnerId: int


@dataclass
class LoginResponse:
    """Response from login endpoint."""
    user: User
    refreshTokenExpirationDate: str


@dataclass
class FlowerHubStatus:
    """Status information for the FlowerHub system."""
    status: Optional[str] = None
    message: Optional[str] = None
    updated_at: Optional[datetime.datetime] = None

    @property
    def updated_timestamp(self) -> Optional[datetime.datetime]:
        return self.updated_at

    def age_seconds(self) -> Optional[float]:
        if not self.updated_at:
            return None
        return (
            datetime.datetime.now(datetime.timezone.utc) - self.updated_at
        ).total_seconds()


@dataclass
class Manufacturer:
    """Manufacturer information."""
    manufacturerId: int
    manufacturerName: str


@dataclass
class Inverter:
    """Inverter specifications."""
    manufacturerId: int
    manufacturerName: str
    inverterModelId: int
    name: str
    numberOfBatteryStacksSupported: int
    capacityId: int
    powerCapacity: int


@dataclass
class Battery:
    """Battery specifications."""
    manufacturerId: int
    manufacturerName: str
    batteryModelId: int
    name: str
    minNumberOfBatteryModules: int
    maxNumberOfBatteryModules: int
    capacityId: int
    energyCapacity: int
    powerCapacity: int


@dataclass
class Asset:
    """Complete asset information."""
    id: int
    inverter: Inverter
    battery: Battery
    fuseSize: int
    flowerHubStatus: FlowerHubStatus
    isInstalled: bool


@dataclass
class AssetOwner:
    """Asset owner information."""
    id: int
    assetId: int
    firstName: str


class AsyncFlowerhubClient:
    def __init__(
        self,
        base_url: str = "https://api.portal.flowerhub.se",
        session: Optional["aiohttp.ClientSession"] = None,
    ):
        # session or aiohttp may be provided; actual request-time will raise if session is missing
        self.base_url = base_url
        self._session = session
        self.asset_owner_id: Optional[int] = None
        self.asset_id: Optional[int] = None
        self.asset_info: Optional[Dict[str, Any]] = None
        self.flowerhub_status: Optional[FlowerHubStatus] = None

    async def _request(self, path: str, method: str = "GET", **kwargs) -> Any:
        sess = self._session
        if sess is None:
            raise RuntimeError("aiohttp ClientSession is required")
        url = (
            path
            if path.startswith("http")
            else f"{self.base_url.rstrip('/')}/{path.lstrip('/')}"
        )
        headers = {"Origin": "https://portal.flowerhub.se", **kwargs.pop("headers", {})}
        cm = sess.request(method, url, headers=headers, **kwargs)
        if asyncio.iscoroutine(cm):
            cm = await cm
        async with cm as resp:
            text = await resp.text()
            try:
                data = await resp.json()
            except Exception:
                data = None
            # Handle 401 -> try refresh-token once and retry original request
            if resp.status == 401:
                try:
                    # attempt refresh
                    rref_ctx = sess.request(
                        "GET",
                        f"{self.base_url.rstrip('/')}/auth/refresh-token",
                        headers=headers,
                    )
                    if asyncio.iscoroutine(rref_ctx):
                        rref_ctx = await rref_ctx
                    async with rref_ctx as rref:
                        try:
                            rref_json = await rref.json()
                        except Exception:
                            rref_json = None
                        # try to update asset_owner_id if present
                        try:
                            if isinstance(rref_json, dict):
                                u = rref_json.get("user")
                                if isinstance(u, dict) and "assetOwnerId" in u:
                                    self.asset_owner_id = int(u["assetOwnerId"])
                        except Exception:
                            pass
                except Exception:
                    logging.exception("Refresh token request failed")
                # retry original request once
                cm2 = sess.request(method, url, headers=headers, **kwargs)
                if asyncio.iscoroutine(cm2):
                    cm2 = await cm2
                async with cm2 as resp2:
                    text2 = await resp2.text()
                    try:
                        data2 = await resp2.json()
                    except Exception:
                        data2 = None
                    return resp2, data2, text2
            return resp, data, text

    async def async_login(self, username: str, password: str) -> Dict[str, Any]:
        if self._session is None:
            raise RuntimeError("aiohttp ClientSession is required for login")
        url = f"{self.base_url.rstrip('/')}/auth/login"
        resp, data, text = await self._request(
            url, method="POST", json={"username": username, "password": password}
        )
        # try to set asset_owner_id from json
        try:
            if data and isinstance(data, dict):
                u = data.get("user")
                if isinstance(u, dict) and "assetOwnerId" in u:
                    self.asset_owner_id = int(u["assetOwnerId"])
        except Exception:
            pass
        return {"status_code": resp.status, "json": data}

    async def async_fetch_asset_id(
        self, asset_owner_id: Optional[int] = None
    ) -> Optional[Any]:
        aoid = asset_owner_id or self.asset_owner_id
        if not aoid:
            return None
        path = f"/asset-owner/{aoid}/withAssetId"
        resp, data, _ = await self._request(path)
        if isinstance(data, dict):
            if "assetId" in data:
                try:
                    self.asset_id = int(data["assetId"])
                except Exception:
                    self.asset_id = None
        return resp

    async def async_fetch_asset(self, asset_id: Optional[int] = None) -> Optional[Any]:
        aid = asset_id or self.asset_id
        if not aid:
            return None
        path = f"/asset/{aid}"
        resp, data, _ = await self._request(path)
        if resp.status < 400 and isinstance(data, dict):
            self.asset_info = data
            fhs = data.get("flowerHubStatus")
            if isinstance(fhs, dict):
                now = datetime.datetime.now(datetime.timezone.utc)
                self.flowerhub_status = FlowerHubStatus(
                    status=fhs.get("status"), message=fhs.get("message"), updated_at=now
                )
        return resp

    async def async_readout_sequence(
        self, asset_owner_id: Optional[int] = None
    ) -> Dict[str, Any]:
        ao = asset_owner_id or self.asset_owner_id
        if not ao:
            raise ValueError("asset_owner_id is required for readout")
        with_resp = await self.async_fetch_asset_id(ao)
        asset_resp = None
        if self.asset_id:
            asset_resp = await self.async_fetch_asset(self.asset_id)
        return {
            "asset_owner_id": ao,
            "asset_id": self.asset_id,
            "with_asset_resp": with_resp,
            "asset_resp": asset_resp,
        }

    # helper to integrate with HA DataUpdateCoordinator is documented in README

    # ----- Periodic fetch helpers (async) -----
    def start_periodic_asset_fetch(
        self,
        interval_seconds: float = 60.0,
        run_immediately: bool = False,
        on_update: Optional[callable] = None,
        result_queue: Optional["asyncio.Queue"] = None,
    ) -> asyncio.Task:
        """Start a background asyncio Task that periodically fetches the asset.

        Returns the asyncio.Task instance. Call :meth:`stop_periodic_asset_fetch` to cancel.
        """
        if interval_seconds < 5.0:
            raise ValueError("interval_seconds must be at least 5 seconds")
        if getattr(self, "_asset_fetch_task", None):
            raise RuntimeError("Periodic asset fetch is already running")

        async def _handle_update():
            fh = getattr(self, "flowerhub_status", None)
            if not fh:
                return
            if on_update:
                try:
                    on_update(fh)
                except Exception:
                    logging.exception("on_update callback raised an exception")
            if result_queue:
                try:
                    result_queue.put_nowait(fh)
                except Exception:
                    logging.exception("result_queue.put_nowait raised an exception")

        async def _loop():
            if run_immediately:
                try:
                    if not self.asset_id:
                        await self.async_fetch_asset_id(self.asset_owner_id)
                    if self.asset_id:
                        await self.async_fetch_asset(self.asset_id)
                        await _handle_update()
                except Exception:
                    logging.exception("Initial fetch failed in periodic start")
            try:
                while True:
                    await asyncio.sleep(float(interval_seconds))
                    try:
                        if not self.asset_id:
                            await self.async_fetch_asset_id(self.asset_owner_id)
                        if self.asset_id:
                            await self.async_fetch_asset(self.asset_id)
                            await _handle_update()
                    except Exception:
                        logging.exception("Periodic fetch_asset() raised an exception")
            except asyncio.CancelledError:
                return

        task = asyncio.create_task(_loop())
        self._asset_fetch_task = task
        return task

    def stop_periodic_asset_fetch(self) -> None:
        t = getattr(self, "_asset_fetch_task", None)
        if t and not t.cancelled():
            t.cancel()
        self._asset_fetch_task = None

    def is_asset_fetch_running(self) -> bool:
        t = getattr(self, "_asset_fetch_task", None)
        return bool(t and not t.done())
