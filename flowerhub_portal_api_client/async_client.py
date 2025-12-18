"""Async Flowerhub client suitable for Home Assistant integrations.

This module implements `AsyncFlowerhubClient` built on top of `aiohttp.ClientSession`.
It mirrors the synchronous API in `flowerhub_client.client` with async methods
so it can be used with Home Assistant's event loop and `DataUpdateCoordinator`.
"""

from __future__ import annotations

import asyncio
import datetime
import logging
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

_LOGGER = logging.getLogger(__name__)

aiohttp: Any
try:
    import aiohttp
except Exception:  # pragma: no cover - optional dependency
    aiohttp = None


class AuthenticationError(Exception):
    """Raised when authentication token expires and refresh fails.

    This exception indicates that the user needs to login again.
    """


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


@dataclass
class AgreementState:
    """State metadata for electricity agreements (consumption/production)."""

    stateCategory: Optional[str] = None
    stateId: Optional[int] = None
    siteId: Optional[int] = None
    startDate: Optional[str] = None
    terminationDate: Optional[str] = None


@dataclass
class ElectricityAgreement:
    """Electricity agreement covering consumption and production sites."""

    consumption: Optional[AgreementState] = None
    production: Optional[AgreementState] = None


@dataclass
class InvoiceLine:
    """Single invoice line item."""

    item_id: str
    name: str
    description: str
    price: str
    volume: str
    amount: str
    settlements: Any


@dataclass
class Invoice:
    """Invoice structure, optionally containing sub group invoices."""

    id: str
    due_date: Optional[str]
    ocr: Optional[str]
    invoice_status: Optional[str]
    invoice_has_settlements: Optional[str]
    invoice_status_id: Optional[str]
    invoice_create_date: Optional[str]
    invoiced_month: Optional[str]
    invoice_period: Optional[str]
    invoice_date: Optional[str]
    total_amount: Optional[str]
    remaining_amount: Optional[str]
    invoice_lines: List[InvoiceLine] = field(default_factory=list)
    invoice_pdf: Optional[str] = None
    invoice_type_id: Optional[str] = None
    invoice_type: Optional[str] = None
    claim_status: Optional[str] = None
    claim_reminder_pdf: Optional[str] = None
    site_id: Optional[str] = None
    sub_group_invoices: List["Invoice"] = field(default_factory=list)
    current_payment_type_id: Optional[str] = None
    current_payment_type_name: Optional[str] = None


@dataclass
class ConsumptionRecord:
    """Consumption history entry (reading or calculated)."""

    site_id: str
    valid_from: str
    valid_to: Optional[str]
    invoiced_month: str
    volume: Optional[float]
    type: str
    type_id: Optional[int]


class AsyncFlowerhubClient:
    def __init__(
        self,
        base_url: str = "https://api.portal.flowerhub.se",
        session: Optional["aiohttp.ClientSession"] = None,
        on_auth_failed: Optional[Callable[[], None]] = None,
    ):
        # session or aiohttp may be provided; actual request-time will raise if session is missing
        self.base_url = base_url
        self._session: Optional["aiohttp.ClientSession"] = session
        self.on_auth_failed = on_auth_failed
        self.asset_owner_id: Optional[int] = None
        self.asset_id: Optional[int] = None
        self.asset_info: Optional[Dict[str, Any]] = None
        self.flowerhub_status: Optional[FlowerHubStatus] = None
        self._asset_fetch_task: Optional[asyncio.Task[Any]] = None

    @staticmethod
    def _safe_int(value: Any) -> Optional[int]:
        try:
            return int(value)
        except (ValueError, TypeError):
            return None

    @staticmethod
    def _safe_float(value: Any) -> Optional[float]:
        try:
            return float(value)
        except (ValueError, TypeError):
            return None

    @classmethod
    def _parse_agreement_state(cls, payload: Dict[str, Any]) -> AgreementState:
        return AgreementState(
            stateCategory=payload.get("stateCategory"),
            stateId=cls._safe_int(payload.get("stateId")),
            siteId=cls._safe_int(payload.get("siteId")),
            startDate=payload.get("startDate"),
            terminationDate=payload.get("terminationDate"),
        )

    @classmethod
    def _parse_electricity_agreement(cls, data: Any) -> Optional[ElectricityAgreement]:
        if not isinstance(data, dict):
            return None
        consumption = data.get("consumption")
        production = data.get("production")
        return ElectricityAgreement(
            consumption=(
                cls._parse_agreement_state(consumption)
                if isinstance(consumption, dict)
                else None
            ),
            production=(
                cls._parse_agreement_state(production)
                if isinstance(production, dict)
                else None
            ),
        )

    @classmethod
    def _parse_invoice_line(cls, payload: Dict[str, Any]) -> InvoiceLine:
        return InvoiceLine(
            item_id=str(payload.get("item_id", "")),
            name=payload.get("name", ""),
            description=payload.get("description", ""),
            price=str(payload.get("price", "")),
            volume=str(payload.get("volume", "")),
            amount=str(payload.get("amount", "")),
            settlements=payload.get("settlements", []),
        )

    @classmethod
    def _parse_invoice(cls, payload: Dict[str, Any]) -> Invoice:
        lines: List[InvoiceLine] = []
        for entry in payload.get("invoice_lines", []):
            if isinstance(entry, dict):
                lines.append(cls._parse_invoice_line(entry))

        sub_invoices: List[Invoice] = []
        for sub in payload.get("sub_group_invoices", []):
            if isinstance(sub, dict):
                sub_invoices.append(cls._parse_invoice(sub))

        return Invoice(
            id=str(payload.get("id", "")),
            due_date=payload.get("due_date"),
            ocr=payload.get("ocr"),
            invoice_status=payload.get("invoice_status"),
            invoice_has_settlements=payload.get("invoice_has_settlements"),
            invoice_status_id=payload.get("invoice_status_id"),
            invoice_create_date=payload.get("invoice_create_date"),
            invoiced_month=payload.get("invoiced_month"),
            invoice_period=payload.get("invoice_period"),
            invoice_date=payload.get("invoice_date"),
            total_amount=payload.get("total_amount"),
            remaining_amount=payload.get("remaining_amount"),
            invoice_lines=lines,
            invoice_pdf=payload.get("invoice_pdf"),
            invoice_type_id=payload.get("invoice_type_id"),
            invoice_type=payload.get("invoice_type"),
            claim_status=payload.get("claim_status"),
            claim_reminder_pdf=payload.get("claim_reminder_pdf"),
            site_id=payload.get("site_id"),
            sub_group_invoices=sub_invoices,
            current_payment_type_id=payload.get("current_payment_type_id"),
            current_payment_type_name=payload.get("current_payment_type_name"),
        )

    @classmethod
    def _parse_invoices(cls, data: Any) -> Optional[List[Invoice]]:
        if not isinstance(data, list):
            return None
        invoices: List[Invoice] = []
        for item in data:
            if isinstance(item, dict):
                invoices.append(cls._parse_invoice(item))
        return invoices

    @classmethod
    def _parse_consumption(cls, data: Any) -> Optional[List[ConsumptionRecord]]:
        if not isinstance(data, list):
            return None
        records: List[ConsumptionRecord] = []
        for item in data:
            if not isinstance(item, dict):
                continue
            records.append(
                ConsumptionRecord(
                    site_id=str(item.get("site_id", "")),
                    valid_from=item.get("valid_from", ""),
                    valid_to=item.get("valid_to") or None,
                    invoiced_month=item.get("invoiced_month", ""),
                    volume=cls._safe_float(item.get("volume")),
                    type=item.get("type", ""),
                    type_id=cls._safe_int(item.get("type_id")),
                )
            )
        return records

    async def _request(  # pylint: disable=too-many-locals,too-many-branches,too-many-statements
        self, path: str, method: str = "GET", **kwargs
    ) -> Any:
        sess = self._session
        if sess is None:
            _LOGGER.error("Request failed: aiohttp ClientSession is required")
            raise RuntimeError("aiohttp ClientSession is required")
        url = (
            path
            if path.startswith("http")
            else f"{self.base_url.rstrip('/')}/{path.lstrip('/')}"
        )
        headers = {"Origin": "https://portal.flowerhub.se", **kwargs.pop("headers", {})}

        _LOGGER.debug("Making %s request to %s", method, path)

        cm: Any = sess.request(method, url, headers=headers, **kwargs)
        if asyncio.iscoroutine(cm):
            cm = await cm
        async with cm as resp:
            text = await resp.text()
            try:
                data = await resp.json()
            except Exception as err:
                _LOGGER.debug("Response is not JSON for %s: %s", path, err)
                data = None

            # Handle 401 -> try refresh-token once and retry original request
            if resp.status == 401:
                _LOGGER.info("Access token expired for %s, attempting refresh", path)
                try:
                    # attempt refresh
                    rref_cm: Any = sess.request(
                        "GET",
                        f"{self.base_url.rstrip('/')}/auth/refresh-token",
                        headers=headers,
                    )
                    if asyncio.iscoroutine(rref_cm):
                        rref_cm = await rref_cm
                    async with rref_cm as rref:
                        if rref.status == 200:
                            _LOGGER.info("Token refresh successful")
                        else:
                            _LOGGER.warning(
                                "Token refresh failed with status %s", rref.status
                            )
                        try:
                            rref_json = await rref.json()
                        except Exception as err:
                            _LOGGER.debug("Refresh response is not JSON: %s", err)
                            rref_json = None
                        # try to update asset_owner_id if present
                        try:
                            if isinstance(rref_json, dict):
                                u = rref_json.get("user")
                                if isinstance(u, dict) and "assetOwnerId" in u:
                                    self.asset_owner_id = int(u["assetOwnerId"])
                                    _LOGGER.debug(
                                        "Updated asset_owner_id to %s from refresh",
                                        self.asset_owner_id,
                                    )
                        except (ValueError, TypeError, KeyError) as err:
                            _LOGGER.debug("Could not extract assetOwnerId: %s", err)
                except Exception as err:
                    _LOGGER.error(
                        "Token refresh request failed: %s", err, exc_info=True
                    )

                # retry original request once
                _LOGGER.debug("Retrying original request to %s after refresh", path)
                cm2: Any = sess.request(method, url, headers=headers, **kwargs)
                if asyncio.iscoroutine(cm2):
                    cm2 = await cm2
                async with cm2 as resp2:
                    text2 = await resp2.text()
                    try:
                        data2 = await resp2.json()
                    except Exception as err:
                        _LOGGER.debug(
                            "Retry response is not JSON for %s: %s", path, err
                        )
                        data2 = None

                    if resp2.status == 401:
                        _LOGGER.error(
                            "Request to %s failed after token refresh: re-authentication required",
                            path,
                        )
                        # Invoke callback if provided
                        if self.on_auth_failed:
                            try:
                                self.on_auth_failed()
                            except Exception as err:
                                _LOGGER.error(
                                    "on_auth_failed callback raised an exception: %s",
                                    err,
                                    exc_info=True,
                                )
                        # Raise exception to notify caller
                        raise AuthenticationError(
                            "Authentication token expired and refresh failed. Please login again."
                        )
                    if resp2.status >= 400:
                        _LOGGER.warning(
                            "Request to %s failed after token refresh with status %s",
                            path,
                            resp2.status,
                        )
                    else:
                        _LOGGER.debug(
                            "Request to %s succeeded after refresh with status %s",
                            path,
                            resp2.status,
                        )
                    return resp2, data2, text2

            if resp.status >= 400:
                _LOGGER.warning(
                    "Request to %s returned error status %s", path, resp.status
                )
            elif resp.status >= 300:
                _LOGGER.debug(
                    "Request to %s returned redirect status %s", path, resp.status
                )

            return resp, data, text

    async def async_login(self, username: str, password: str) -> Dict[str, Any]:
        if self._session is None:
            _LOGGER.error("Login failed: aiohttp ClientSession is required")
            raise RuntimeError("aiohttp ClientSession is required for login")

        _LOGGER.debug("Attempting login for user %s", username)
        url = f"{self.base_url.rstrip('/')}/auth/login"
        resp, data, text = await self._request(
            url, method="POST", json={"username": username, "password": password}
        )

        if resp.status == 200:
            _LOGGER.info("Login successful for user %s", username)
        else:
            _LOGGER.warning(
                "Login failed for user %s with status %s", username, resp.status
            )

        # try to set asset_owner_id from json
        try:
            if data and isinstance(data, dict):
                u = data.get("user")
                if isinstance(u, dict) and "assetOwnerId" in u:
                    self.asset_owner_id = int(u["assetOwnerId"])
                    _LOGGER.debug(
                        "Set asset_owner_id to %s from login response",
                        self.asset_owner_id,
                    )
        except (ValueError, TypeError, KeyError) as err:
            _LOGGER.debug("Could not extract assetOwnerId from login: %s", err)

        return {"status_code": resp.status, "json": data}

    async def async_fetch_asset_id(
        self, asset_owner_id: Optional[int] = None
    ) -> Optional[Any]:
        aoid = asset_owner_id or self.asset_owner_id
        if not aoid:
            _LOGGER.warning("Cannot fetch asset ID: asset_owner_id not set")
            return None
        path = f"/asset-owner/{aoid}/withAssetId"
        resp, data, _ = await self._request(path)
        if isinstance(data, dict):
            if "assetId" in data:
                try:
                    self.asset_id = int(data["assetId"])
                    _LOGGER.debug("Fetched asset_id: %s", self.asset_id)
                except (ValueError, TypeError) as err:
                    _LOGGER.error("Failed to parse assetId from response: %s", err)
                    self.asset_id = None
            else:
                _LOGGER.warning("Response missing assetId field")
        else:
            _LOGGER.warning("Unexpected response format for asset_id fetch")
        return resp

    async def async_fetch_asset(self, asset_id: Optional[int] = None) -> Optional[Any]:
        aid = asset_id or self.asset_id
        if not aid:
            _LOGGER.warning("Cannot fetch asset: asset_id not set")
            return None
        path = f"/asset/{aid}"
        resp, data, _ = await self._request(path)
        if resp.status < 400 and isinstance(data, dict):
            self.asset_info = data
            _LOGGER.debug("Successfully fetched asset info for asset_id %s", aid)
            fhs = data.get("flowerHubStatus")
            if isinstance(fhs, dict):
                now = datetime.datetime.now(datetime.timezone.utc)
                self.flowerhub_status = FlowerHubStatus(
                    status=fhs.get("status"), message=fhs.get("message"), updated_at=now
                )
                _LOGGER.debug(
                    "FlowerHub status updated: %s - %s",
                    self.flowerhub_status.status,
                    self.flowerhub_status.message,
                )
            else:
                _LOGGER.debug("Asset response missing flowerHubStatus")
        elif resp.status >= 400:
            _LOGGER.error("Failed to fetch asset %s: status %s", aid, resp.status)
        return resp

    async def async_fetch_system_notification(
        self, slug: str = "active-flower"
    ) -> Dict[str, Any]:
        """Fetch a system-notification payload by slug (e.g. ``active-flower`` or ``active-zavann``)."""

        path = f"/system-notification/{slug}"
        resp, data, text = await self._request(path)
        return {"status_code": resp.status, "json": data, "text": text}

    async def async_fetch_electricity_agreement(
        self, asset_owner_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """Fetch electricity agreement details for the given asset owner."""

        aoid = asset_owner_id or self.asset_owner_id
        if not aoid:
            _LOGGER.error("Cannot fetch electricity agreement: asset_owner_id not set")
            raise ValueError(
                "asset_owner_id is required for electricity agreement fetch"
            )
        path = f"/asset-owner/{aoid}/electricity-agreement"
        resp, data, text = await self._request(path)

        if resp.status == 200:
            _LOGGER.debug("Successfully fetched electricity agreement")
        elif resp.status >= 400:
            _LOGGER.warning(
                "Failed to fetch electricity agreement: status %s", resp.status
            )

        return {
            "status_code": resp.status,
            "json": data,
            "text": text,
            "agreement": self._parse_electricity_agreement(data),
        }

    async def async_fetch_invoices(
        self, asset_owner_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """Fetch invoice information for the given asset owner."""

        aoid = asset_owner_id or self.asset_owner_id
        if not aoid:
            _LOGGER.error("Cannot fetch invoices: asset_owner_id not set")
            raise ValueError("asset_owner_id is required for invoice fetch")
        path = f"/asset-owner/{aoid}/invoice"
        resp, data, text = await self._request(path)

        if resp.status == 200:
            invoice_count = len(data) if isinstance(data, list) else 0
            _LOGGER.debug("Successfully fetched %s invoices", invoice_count)
        elif resp.status >= 400:
            _LOGGER.warning("Failed to fetch invoices: status %s", resp.status)

        return {
            "status_code": resp.status,
            "json": data,
            "text": text,
            "invoices": self._parse_invoices(data),
        }

    async def async_fetch_consumption(
        self, asset_owner_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """Fetch consumption data for the given asset owner."""

        aoid = asset_owner_id or self.asset_owner_id
        if not aoid:
            _LOGGER.error("Cannot fetch consumption: asset_owner_id not set")
            raise ValueError("asset_owner_id is required for consumption fetch")
        path = f"/asset-owner/{aoid}/consumption"
        resp, data, text = await self._request(path)

        if resp.status == 200:
            record_count = len(data) if isinstance(data, list) else 0
            _LOGGER.debug("Successfully fetched %s consumption records", record_count)
        elif resp.status >= 400:
            _LOGGER.warning("Failed to fetch consumption: status %s", resp.status)

        return {
            "status_code": resp.status,
            "json": data,
            "text": text,
            "consumption": self._parse_consumption(data),
        }

    async def async_readout_sequence(
        self, asset_owner_id: Optional[int] = None
    ) -> Dict[str, Any]:
        ao = asset_owner_id or self.asset_owner_id
        if not ao:
            _LOGGER.error("Cannot perform readout: asset_owner_id not set")
            raise ValueError("asset_owner_id is required for readout")

        _LOGGER.debug("Starting readout sequence for asset_owner_id %s", ao)
        with_resp = await self.async_fetch_asset_id(ao)
        asset_resp = None
        if self.asset_id:
            asset_resp = await self.async_fetch_asset(self.asset_id)
            _LOGGER.debug("Readout sequence completed successfully")
        else:
            _LOGGER.warning("Readout sequence incomplete: asset_id not found")

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
        on_update: Optional[Callable[[FlowerHubStatus], None]] = None,
        result_queue: Optional["asyncio.Queue"] = None,
    ) -> asyncio.Task:
        """Start a background asyncio Task that periodically fetches the asset.

        Returns the asyncio.Task instance. Call :meth:`stop_periodic_asset_fetch` to cancel.
        """
        if interval_seconds < 5.0:
            _LOGGER.error(
                "Cannot start periodic fetch: interval must be at least 5 seconds"
            )
            raise ValueError("interval_seconds must be at least 5 seconds")
        if getattr(self, "_asset_fetch_task", None):
            _LOGGER.warning("Periodic asset fetch is already running")
            raise RuntimeError("Periodic asset fetch is already running")

        _LOGGER.info(
            "Starting periodic asset fetch with interval %s seconds",
            interval_seconds,
        )

        async def _handle_update():
            fh = getattr(self, "flowerhub_status", None)
            if not fh:
                return
            if on_update:
                try:
                    on_update(fh)
                except Exception as err:
                    _LOGGER.error(
                        "on_update callback raised an exception: %s", err, exc_info=True
                    )
            if result_queue:
                try:
                    result_queue.put_nowait(fh)
                except Exception as err:
                    _LOGGER.error(
                        "Failed to put result in queue: %s", err, exc_info=True
                    )

        async def _loop():
            if run_immediately:
                try:
                    if not self.asset_id:
                        await self.async_fetch_asset_id(self.asset_owner_id)
                    if self.asset_id:
                        await self.async_fetch_asset(self.asset_id)
                        await _handle_update()
                except Exception as err:
                    _LOGGER.error(
                        "Initial fetch failed in periodic start: %s", err, exc_info=True
                    )
            try:
                while True:
                    await asyncio.sleep(float(interval_seconds))
                    try:
                        if not self.asset_id:
                            await self.async_fetch_asset_id(self.asset_owner_id)
                        if self.asset_id:
                            await self.async_fetch_asset(self.asset_id)
                            await _handle_update()
                    except Exception as err:
                        _LOGGER.error(
                            "Periodic fetch_asset() failed: %s", err, exc_info=True
                        )
            except asyncio.CancelledError:
                _LOGGER.debug("Periodic asset fetch cancelled")
                return

        task = asyncio.create_task(_loop())
        self._asset_fetch_task = task
        return task

    def stop_periodic_asset_fetch(self) -> None:
        t = getattr(self, "_asset_fetch_task", None)
        if t and not t.cancelled():
            _LOGGER.info("Stopping periodic asset fetch")
            t.cancel()
        self._asset_fetch_task = None

    def is_asset_fetch_running(self) -> bool:
        t = getattr(self, "_asset_fetch_task", None)
        return bool(t and not t.done())
