"""Async Flowerhub client suitable for Home Assistant integrations.

This module implements `AsyncFlowerhubClient` built on top of `aiohttp.ClientSession`.
It mirrors the synchronous API in `flowerhub_client.client` with async methods
so it can be used with Home Assistant's event loop and `DataUpdateCoordinator`.
"""

# pylint: disable=too-many-lines

from __future__ import annotations

import asyncio
import datetime
import logging
import random
from typing import TYPE_CHECKING, Any, Callable, Dict, List, Optional

from .exceptions import ApiError, AuthenticationError
from .parsers import (
    ensure_dict,
    ensure_list,
    parse_agreement_state,
    parse_asset_id_value,
    parse_asset_owner_details,
    parse_asset_owner_profile,
    parse_consumption,
    parse_electricity_agreement,
    parse_invoice,
    parse_invoice_line,
    parse_invoices,
    parse_revenue,
    parse_uptime_available_months,
    parse_uptime_history,
    parse_uptime_pie,
    require_field,
    safe_float,
    safe_int,
    validate_flowerhub_status,
)
from .types import (
    AgreementResult,
    AgreementState,
    AssetFetchResult,
    AssetIdResult,
    AssetOwnerDetails,
    AssetOwnerDetailsResult,
    AssetOwnerProfile,
    ConsumptionRecord,
    ConsumptionResult,
    ElectricityAgreement,
    FlowerHubStatus,
    Invoice,
    InvoiceLine,
    InvoicesResult,
    ProfileResult,
    Revenue,
    RevenueResult,
    UptimeAvailableMonthsResult,
    UptimeHistoryEntry,
    UptimeHistoryResult,
    UptimeMonth,
    UptimePieResult,
    UptimePieSlice,
)

if TYPE_CHECKING:
    import aiohttp
else:
    try:
        import aiohttp
    except ImportError:
        aiohttp = None

_LOGGER = logging.getLogger(__name__)


class AsyncFlowerhubClient:
    """Async client for Flowerhub Portal API.

    Provides Home Assistant–friendly async methods with built-in token refresh,
    retries, timeouts, and optional callbacks for authentication and API errors.

    Configure per-call behavior using `raise_on_error`, `retry_5xx_attempts`, and
    `timeout_total`. Results are plain dicts conforming to `TypedDict` contracts
    defined in `flowerhub_portal_api_client.types`.
    """

    def __init__(
        self,
        base_url: str = "https://api.portal.flowerhub.se",
        session: Optional[aiohttp.ClientSession] = None,
        on_auth_failed: Optional[Callable[[], None]] = None,
        on_api_error: Optional[Callable[[ApiError], None]] = None,
    ):
        # session or aiohttp may be provided; actual request-time will raise if session is missing
        self.base_url = base_url
        self._session: Optional[aiohttp.ClientSession] = session
        self.on_auth_failed = on_auth_failed
        self.on_api_error = on_api_error
        self.asset_owner_id: Optional[int] = None
        self.asset_id: Optional[int] = None
        self.asset_info: Optional[Dict[str, Any]] = None
        self.flowerhub_status: Optional[FlowerHubStatus] = None
        self._asset_fetch_task: Optional[asyncio.Task[Any]] = None
        # Optional total timeout in seconds for requests (10s default). Set to 0/None to disable.
        self.request_timeout_total: Optional[float] = 10.0
        # Optional concurrency limiter
        self._semaphore: Optional[asyncio.Semaphore] = None

    # Compatibility wrappers delegating to shared parser helpers
    @staticmethod
    def _safe_int(value: Any) -> Optional[int]:
        return safe_int(value)

    @staticmethod
    def _safe_float(value: Any) -> Optional[float]:
        return safe_float(value)

    @classmethod
    def _parse_agreement_state(cls, payload: Dict[str, Any]) -> AgreementState:
        return parse_agreement_state(payload)

    @classmethod
    def _parse_electricity_agreement(cls, data: Any) -> Optional[ElectricityAgreement]:
        return parse_electricity_agreement(data)

    @classmethod
    def _parse_invoice_line(cls, payload: Dict[str, Any]) -> InvoiceLine:
        return parse_invoice_line(payload)

    @classmethod
    def _parse_invoice(cls, payload: Dict[str, Any]) -> Invoice:
        return parse_invoice(payload)

    @classmethod
    def _parse_invoices(cls, data: Any) -> Optional[List[Invoice]]:
        return parse_invoices(data)

    @classmethod
    def _parse_consumption(cls, data: Any) -> Optional[List[ConsumptionRecord]]:
        return parse_consumption(data)

    @classmethod
    def _parse_revenue(cls, data: Any) -> Optional[Revenue]:
        return parse_revenue(data)

    # ----- Internal helpers -----
    def _build_url(self, path: str) -> str:
        return (
            path
            if path.startswith("http")
            else f"{self.base_url.rstrip('/')}/{path.lstrip('/')}"
        )

    def _apply_timeout(self, kwargs: Dict[str, Any]) -> Dict[str, Any]:
        # Per-call override via timeout_total
        override = kwargs.pop("timeout_total", None)
        total = (
            override
            if isinstance(override, (int, float))
            else self.request_timeout_total
        )
        if total is not None and total > 0 and "timeout" not in kwargs:
            try:
                if aiohttp is not None:
                    kwargs["timeout"] = aiohttp.ClientTimeout(total=float(total))
            except Exception as err:  # pragma: no cover - best effort
                _LOGGER.debug("Failed to construct ClientTimeout: %s", err)
        return kwargs

    @staticmethod
    async def _read_response(resp: Any) -> tuple[Any, str]:
        text = await resp.text()
        try:
            data = await resp.json()
        except Exception as err:  # pragma: no cover - non-JSON responses
            _LOGGER.debug("Response is not JSON: %s", err)
            data = None
        return data, text

    @staticmethod
    def _should_retry_5xx(
        status: int, attempts: int, retry_5xx_attempts: Optional[int]
    ) -> bool:
        return (
            status >= 500
            and retry_5xx_attempts is not None
            and retry_5xx_attempts != 0
            and attempts < retry_5xx_attempts
        )

    @staticmethod
    def _log_status(path: str, status: int) -> None:
        if status >= 400:
            _LOGGER.warning("Request to %s returned error status %s", path, status)
        elif status >= 300:
            _LOGGER.debug("Request to %s returned redirect status %s", path, status)

    def _maybe_raise_http_error(
        self, resp: Any, data: Any, url: str, raise_on_error: bool
    ) -> None:
        if resp.status >= 400 and raise_on_error:
            err = ApiError(
                f"HTTP error: {resp.status}",
                status_code=resp.status,
                url=url,
                payload=data,
            )
            if self.on_api_error:
                try:
                    self.on_api_error(err)
                except Exception as cb_err:  # pragma: no cover
                    _LOGGER.debug("on_api_error callback failed: %s", cb_err)
            raise err

    async def _attempt_refresh(
        self, sess: aiohttp.ClientSession, headers: Dict[str, str]
    ) -> bool:
        try:
            refresh_cm: Any = sess.request(
                "GET",
                f"{self.base_url.rstrip('/')}/auth/refresh-token",
                headers=headers,
            )
            if asyncio.iscoroutine(refresh_cm):
                refresh_cm = await refresh_cm
            async with refresh_cm as refresh_response:
                if refresh_response.status == 200:
                    _LOGGER.info("Token refresh successful")
                else:
                    _LOGGER.warning(
                        "Token refresh failed with status %s", refresh_response.status
                    )
                try:
                    refresh_json = await refresh_response.json()
                except Exception as err:  # pragma: no cover - non-JSON refresh
                    _LOGGER.debug("Refresh response is not JSON: %s", err)
                    refresh_json = None
                try:
                    if isinstance(refresh_json, dict):
                        user_dict = refresh_json.get("user")
                        if isinstance(user_dict, dict) and "assetOwnerId" in user_dict:
                            self.asset_owner_id = int(user_dict["assetOwnerId"])
                            _LOGGER.debug(
                                "Updated asset_owner_id to %s from refresh",
                                self.asset_owner_id,
                            )
                except (ValueError, TypeError, KeyError) as err:  # pragma: no cover
                    _LOGGER.debug("Could not extract assetOwnerId: %s", err)
                return refresh_response.status == 200
        except Exception as err:  # pragma: no cover - network errors
            _LOGGER.error("Token refresh request failed: %s", err, exc_info=True)
            return False

    async def _retry_after_refresh(
        self,
        sess: aiohttp.ClientSession,
        method: str,
        url: str,
        *,
        headers: Dict[str, str],
        kwargs: Dict[str, Any],
        raise_on_error: bool,
        path: str,
    ) -> tuple[Any, Any, str]:
        await self._attempt_refresh(sess, headers)
        retry_cm: Any = sess.request(method, url, headers=headers, **kwargs)
        if asyncio.iscoroutine(retry_cm):
            retry_cm = await retry_cm
        async with retry_cm as retry_response:
            retry_data, retry_text = await self._read_response(retry_response)
            if retry_response.status == 401:
                _LOGGER.error(
                    "Request to %s failed after token refresh: re-authentication required",
                    path,
                )
                if self.on_auth_failed:
                    try:
                        self.on_auth_failed()
                    except Exception as err:  # pragma: no cover - user callback
                        _LOGGER.error(
                            "on_auth_failed callback raised an exception: %s",
                            err,
                            exc_info=True,
                        )
                raise AuthenticationError(
                    "Authentication token expired and refresh failed. Please login again."
                )
            self._log_status(path, retry_response.status)
            self._maybe_raise_http_error(
                retry_response, retry_data, url, raise_on_error
            )
            return retry_response, retry_data, retry_text

    async def _send_request(
        self,
        sess: aiohttp.ClientSession,
        method: str,
        url: str,
        *,
        headers: Dict[str, str],
        kwargs: Dict[str, Any],
    ) -> tuple[Any, Any, str]:
        async def _do():
            request_cm: Any = sess.request(method, url, headers=headers, **kwargs)
            if asyncio.iscoroutine(request_cm):
                request_cm = await request_cm
            async with request_cm as response:
                data, text = await self._read_response(response)
                return response, data, text

        if self._semaphore is not None:
            async with self._semaphore:
                return await _do()
        return await _do()

    @staticmethod
    def _compute_delay(attempts: int, retry_after: Optional[float] = None) -> float:
        if retry_after is not None and retry_after > 0:
            return float(retry_after)
        # Simple linear backoff with jitter
        base = float(max(1, attempts))
        return base + random.uniform(0.0, 0.3)

    async def _request(  # pylint: disable=too-many-locals,too-many-branches,too-many-statements
        self,
        path: str,
        method: str = "GET",
        *,
        raise_on_error: bool = True,
        retry_5xx_attempts: Optional[int] = 2,
        timeout_total: Optional[float] = None,
        **kwargs,
    ) -> Any:
        """Low-level HTTP request wrapper with refresh, retries and timeouts.

        - Handles `401` by attempting token refresh and retrying once.
        - Retries `5xx` and `429` with small jittered backoff; honors `Retry-After`.
        - Applies `aiohttp.ClientTimeout(total=...)` via `timeout_total` or client default.
        - Raises `ApiError` for `>=400` when `raise_on_error=True`.

        Returns a tuple `(resp, json, text)`.
        """
        sess = self._session
        if sess is None:
            _LOGGER.error("Request failed: aiohttp ClientSession is required")
            raise RuntimeError("aiohttp ClientSession is required")

        url = self._build_url(path)
        headers = {"Origin": "https://portal.flowerhub.se", **kwargs.pop("headers", {})}
        # allow per-call timeout override
        merged_kwargs = dict(kwargs)
        if timeout_total is not None:
            merged_kwargs["timeout_total"] = timeout_total
        kwargs = self._apply_timeout(merged_kwargs)

        _LOGGER.debug("Making %s request to %s", method, path)

        attempts = 0
        while True:
            resp, data, text = await self._send_request(
                sess, method, url, headers=headers, kwargs=kwargs
            )

            if resp.status == 401:
                # Do not attempt refresh on explicit login calls; surface a clear error instead
                if "/auth/login" in path:
                    _LOGGER.error(
                        "Login request to %s returned 401; refresh not attempted", path
                    )
                    if self.on_auth_failed:
                        try:
                            self.on_auth_failed()
                        except Exception as err:  # pragma: no cover - user callback
                            _LOGGER.error(
                                "on_auth_failed callback raised an exception: %s",
                                err,
                                exc_info=True,
                            )
                    raise AuthenticationError(
                        "Login failed (401). Invalid credentials or login rejected."
                    )
                _LOGGER.info("Access token expired for %s, attempting refresh", path)
                return await self._retry_after_refresh(
                    sess,
                    method,
                    url,
                    headers=headers,
                    kwargs=kwargs,
                    raise_on_error=raise_on_error,
                    path=path,
                )

            # Retry on 5xx and 429 Too Many Requests
            retry_after_hdr = (
                resp.headers.get("Retry-After") if hasattr(resp, "headers") else None
            )
            try:
                retry_after = float(retry_after_hdr) if retry_after_hdr else None
            except Exception:
                retry_after = None
            if (
                self._should_retry_5xx(resp.status, attempts, retry_5xx_attempts)
                or resp.status == 429
            ):
                attempts += 1
                delay = self._compute_delay(attempts, retry_after)
                _LOGGER.warning(
                    "Retrying %s for %s in %.2fs (attempt %s/%s)",
                    resp.status,
                    path,
                    delay,
                    attempts,
                    retry_5xx_attempts,
                )
                await asyncio.sleep(delay)
                continue

            self._log_status(path, resp.status)
            self._maybe_raise_http_error(resp, data, url, raise_on_error)
            return resp, data, text

    async def async_login(
        self, username: str, password: str, *, raise_on_error: bool = True
    ) -> Dict[str, Any]:
        """Authenticate and initialize `asset_owner_id` when available.

        Args:
            username: Account username (email).
            password: Account password.
            raise_on_error: If True, raises `ApiError` on HTTP errors.

        Returns:
            Dict[str, Any]: `{"status_code": int, "json": Any}` from login.

        Raises:
            RuntimeError: If no aiohttp `ClientSession` is configured.
            ApiError: When `raise_on_error=True` and an HTTP error occurs.
        """
        if self._session is None:
            _LOGGER.error("Login failed: aiohttp ClientSession is required")
            raise RuntimeError("aiohttp ClientSession is required for login")

        _LOGGER.debug("Attempting login for user %s", username)
        url = f"{self.base_url.rstrip('/')}/auth/login"
        resp, data, text = await self._request(
            url,
            method="POST",
            raise_on_error=raise_on_error,
            json={"username": username, "password": password},
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
                user_dict = data.get("user")
                if isinstance(user_dict, dict) and "assetOwnerId" in user_dict:
                    self.asset_owner_id = int(user_dict["assetOwnerId"])
                    _LOGGER.debug(
                        "Set asset_owner_id to %s from login response",
                        self.asset_owner_id,
                    )
        except (ValueError, TypeError, KeyError) as err:
            _LOGGER.debug("Could not extract assetOwnerId from login: %s", err)

        return {"status_code": resp.status, "json": data}

    async def async_fetch_asset_id(
        self, asset_owner_id: Optional[int] = None, *, raise_on_error: bool = True
    ) -> AssetIdResult:
        """Fetch asset ID for an asset owner.

        Args:
            asset_owner_id: Asset owner identifier. Defaults to `self.asset_owner_id`.
            raise_on_error: If True, raises `ApiError` on validation/HTTP errors.

        Returns:
            AssetIdResult: `{status_code, asset_id, error}`.

        Raises:
            ValueError: If asset owner id is not provided.
            ApiError: When parsing/validation fails and `raise_on_error=True`.
        """
        owner_id = asset_owner_id or self.asset_owner_id
        if not owner_id:
            _LOGGER.error("Cannot fetch asset ID: asset_owner_id not set")
            raise ValueError("asset_owner_id is required for asset id fetch")
        path = f"/asset-owner/{owner_id}/withAssetId"
        url = self._build_url(path)
        resp, data, _ = await self._request(path, raise_on_error=raise_on_error)

        data_dict, err = ensure_dict(
            data,
            context="asset_id fetch",
            status_code=resp.status,
            url=url,
            raise_on_error=raise_on_error,
        )
        if data_dict is None:
            return {"status_code": resp.status, "asset_id": None, "error": err}

        asset_id_value, err = require_field(
            data_dict,
            "assetId",
            status_code=resp.status,
            url=url,
            raise_on_error=raise_on_error,
        )
        if asset_id_value is None:
            return {"status_code": resp.status, "asset_id": None, "error": err}

        asset_id_int, err = parse_asset_id_value(
            asset_id_value,
            status_code=resp.status,
            url=url,
            payload=data_dict,
            raise_on_error=raise_on_error,
        )
        if asset_id_int is None:
            self.asset_id = None
            return {"status_code": resp.status, "asset_id": None, "error": err}

        self.asset_id = asset_id_int
        _LOGGER.debug("Fetched asset_id: %s", self.asset_id)
        return {"status_code": resp.status, "asset_id": self.asset_id, "error": None}

    async def async_fetch_asset(
        self,
        asset_id: Optional[int] = None,
        *,
        raise_on_error: bool = True,
        retry_5xx_attempts: Optional[int] = None,
        timeout_total: Optional[float] = None,
    ) -> AssetFetchResult:
        """Fetch asset information and update `flowerhub_status`.

        Args:
            asset_id: Asset identifier. Defaults to `self.asset_id`.
            raise_on_error: If True, raises `ApiError` on HTTP/validation errors.
            retry_5xx_attempts: Optional number of retries for 5xx; `None` disables.
            timeout_total: Optional total timeout override in seconds.

        Returns:
            AssetFetchResult: `{status_code, asset_info, flowerhub_status, error}`.

        Raises:
            ValueError: If asset id is not provided.
            ApiError: On invalid response, missing `flowerHubStatus`, or HTTP errors when `raise_on_error=True`.
        """
        aid = asset_id or self.asset_id
        if not aid:
            _LOGGER.error("Cannot fetch asset: asset_id not set")
            raise ValueError("asset_id is required for asset fetch")
        path = f"/asset/{aid}"
        url = self._build_url(path)
        resp, data, _ = await self._request(
            path,
            raise_on_error=raise_on_error,
            retry_5xx_attempts=retry_5xx_attempts,
            timeout_total=timeout_total,
        )

        data_dict, err = ensure_dict(
            data,
            context="asset fetch",
            status_code=resp.status,
            url=url,
            raise_on_error=raise_on_error,
        )
        if data_dict is None:
            return {
                "status_code": resp.status,
                "asset_info": None,
                "flowerhub_status": None,
                "error": err,
            }

        fh_status, err = validate_flowerhub_status(
            data_dict.get("flowerHubStatus"),
            status_code=resp.status,
            url=url,
            payload=data_dict,
            raise_on_error=raise_on_error,
        )
        if fh_status is None:
            return {
                "status_code": resp.status,
                "asset_info": data_dict,
                "flowerhub_status": None,
                "error": err,
            }

        self.asset_info = data_dict
        self.flowerhub_status = fh_status
        _LOGGER.debug(
            "FlowerHub status updated: %s - %s",
            self.flowerhub_status.status,
            self.flowerhub_status.message,
        )
        return {
            "status_code": resp.status,
            "asset_info": self.asset_info,
            "flowerhub_status": self.flowerhub_status,
            "error": None,
        }

    async def async_fetch_system_notification(
        self,
        slug: str = "active-flower",
        *,
        raise_on_error: bool = True,
        retry_5xx_attempts: Optional[int] = None,
        timeout_total: Optional[float] = None,
    ) -> Dict[str, Any]:
        """Fetch a system-notification payload by slug.

        Args:
            slug: Notification identifier (e.g., "active-flower").
            raise_on_error: If True, raises `ApiError` on HTTP errors.
            retry_5xx_attempts: Optional number of retries for 5xx.
            timeout_total: Optional total timeout override in seconds.

        Returns:
            Dict[str, Any]: `{status_code, json, text}`.

        Raises:
            ApiError: On HTTP errors when `raise_on_error=True`.
        """

        path = f"/system-notification/{slug}"
        resp, data, text = await self._request(
            path,
            raise_on_error=raise_on_error,
            retry_5xx_attempts=retry_5xx_attempts,
            timeout_total=timeout_total,
        )
        return {"status_code": resp.status, "json": data, "text": text}

    async def async_fetch_electricity_agreement(
        self,
        asset_owner_id: Optional[int] = None,
        *,
        raise_on_error: bool = True,
        retry_5xx_attempts: Optional[int] = None,
        timeout_total: Optional[float] = None,
    ) -> AgreementResult:
        """Fetch electricity agreement details for the given asset owner.

        Args:
            asset_owner_id: Asset owner identifier. Defaults to `self.asset_owner_id`.
            raise_on_error: If True, raises `ApiError` on invalid payload/HTTP errors.
            retry_5xx_attempts: Optional number of retries for 5xx.
            timeout_total: Optional total timeout override in seconds.

        Returns:
            AgreementResult: `{status_code, agreement, json, text, error}`.

        Raises:
            ValueError: If asset owner id is not provided.
            ApiError: If payload is not a dict (when `raise_on_error=True`).
        """

        aoid = asset_owner_id or self.asset_owner_id
        if not aoid:
            _LOGGER.error("Cannot fetch electricity agreement: asset_owner_id not set")
            raise ValueError(
                "asset_owner_id is required for electricity agreement fetch"
            )
        path = f"/asset-owner/{aoid}/electricity-agreement"
        resp, data, text = await self._request(
            path,
            raise_on_error=raise_on_error,
            retry_5xx_attempts=retry_5xx_attempts,
            timeout_total=timeout_total,
        )

        if resp.status == 200:
            _LOGGER.debug("Successfully fetched electricity agreement")

        agreement = parse_electricity_agreement(data)
        if agreement is None and raise_on_error:
            msg = "Unexpected response type for electricity agreement (expected dict)"
            _LOGGER.error(msg)
            raise ApiError(msg, status_code=resp.status, url=path, payload=data)
        return {
            "status_code": resp.status,
            "json": data,
            "text": text,
            "agreement": agreement,
            "error": None,
        }

    async def async_fetch_invoices(
        self,
        asset_owner_id: Optional[int] = None,
        *,
        raise_on_error: bool = True,
        retry_5xx_attempts: Optional[int] = None,
        timeout_total: Optional[float] = None,
    ) -> InvoicesResult:
        """Fetch invoice information for the given asset owner.

        Args:
            asset_owner_id: Asset owner identifier. Defaults to `self.asset_owner_id`.
            raise_on_error: If True, raises `ApiError` on invalid payload/HTTP errors.
            retry_5xx_attempts: Optional number of retries for 5xx.
            timeout_total: Optional total timeout override in seconds.

        Returns:
            InvoicesResult: `{status_code, invoices, json, text, error}`.

        Raises:
            ValueError: If asset owner id is not provided.
            ApiError: If payload is not a list (when `raise_on_error=True`).
        """

        aoid = asset_owner_id or self.asset_owner_id
        if not aoid:
            _LOGGER.error("Cannot fetch invoices: asset_owner_id not set")
            raise ValueError("asset_owner_id is required for invoice fetch")
        path = f"/asset-owner/{aoid}/invoice"
        url = self._build_url(path)
        resp, data, text = await self._request(
            path,
            raise_on_error=raise_on_error,
            retry_5xx_attempts=retry_5xx_attempts,
            timeout_total=timeout_total,
        )

        if resp.status == 200:
            invoice_count = len(data) if isinstance(data, list) else 0
            _LOGGER.debug("Successfully fetched %s invoices", invoice_count)

        data_list, err = ensure_list(
            data,
            context="invoices",
            status_code=resp.status,
            url=url,
            raise_on_error=raise_on_error,
        )
        invoices = parse_invoices(data_list) if data_list is not None else None
        if invoices is None and err:
            return {
                "status_code": resp.status,
                "json": data,
                "text": text,
                "invoices": None,
                "error": err,
            }
        return {
            "status_code": resp.status,
            "json": data,
            "text": text,
            "invoices": invoices,
            "error": None,
        }

    async def async_fetch_consumption(
        self,
        asset_owner_id: Optional[int] = None,
        *,
        raise_on_error: bool = True,
        retry_5xx_attempts: Optional[int] = None,
        timeout_total: Optional[float] = None,
    ) -> ConsumptionResult:
        """Fetch consumption data for the given asset owner.

        Args:
            asset_owner_id: Asset owner identifier. Defaults to `self.asset_owner_id`.
            raise_on_error: If True, raises `ApiError` on invalid payload/HTTP errors.
            retry_5xx_attempts: Optional number of retries for 5xx.
            timeout_total: Optional total timeout override in seconds.

        Returns:
            ConsumptionResult: `{status_code, consumption, json, text, error}`.

        Raises:
            ValueError: If asset owner id is not provided.
            ApiError: If payload is not a list (when `raise_on_error=True`).
        """

        aoid = asset_owner_id or self.asset_owner_id
        if not aoid:
            _LOGGER.error("Cannot fetch consumption: asset_owner_id not set")
            raise ValueError("asset_owner_id is required for consumption fetch")
        path = f"/asset-owner/{aoid}/consumption"
        url = self._build_url(path)
        resp, data, text = await self._request(
            path,
            raise_on_error=raise_on_error,
            retry_5xx_attempts=retry_5xx_attempts,
            timeout_total=timeout_total,
        )

        if resp.status == 200:
            record_count = len(data) if isinstance(data, list) else 0
            _LOGGER.debug("Successfully fetched %s consumption records", record_count)

        data_list, err = ensure_list(
            data,
            context="consumption",
            status_code=resp.status,
            url=url,
            raise_on_error=raise_on_error,
        )
        consumption = parse_consumption(data_list) if data_list is not None else None
        if consumption is None and err:
            return {
                "status_code": resp.status,
                "json": data,
                "text": text,
                "consumption": None,
                "error": err,
            }
        return {
            "status_code": resp.status,
            "json": data,
            "text": text,
            "consumption": consumption,
            "error": None,
        }

    async def async_fetch_asset_owner_profile(
        self,
        asset_owner_id: Optional[int] = None,
        *,
        raise_on_error: bool = True,
        retry_5xx_attempts: Optional[int] = None,
        timeout_total: Optional[float] = None,
    ) -> ProfileResult:
        """Fetch asset owner profile details.

        Args:
            asset_owner_id: Asset owner identifier. Defaults to `self.asset_owner_id`.
            raise_on_error: If True, raises `ApiError` on invalid payload/HTTP errors.
            retry_5xx_attempts: Optional number of retries for 5xx.
            timeout_total: Optional total timeout override in seconds.

        Returns:
            ProfileResult: `{status_code, profile, json, text, error}`.

        Raises:
            ValueError: If asset owner id is not provided.
            ApiError: If payload is not a dict (when `raise_on_error=True`).
        """

        aoid = asset_owner_id or self.asset_owner_id
        if not aoid:
            _LOGGER.error("Cannot fetch profile: asset_owner_id not set")
            raise ValueError("asset_owner_id is required for profile fetch")
        path = f"/asset-owner/{aoid}/profile"
        url = self._build_url(path)
        resp, data, text = await self._request(
            path,
            raise_on_error=raise_on_error,
            retry_5xx_attempts=retry_5xx_attempts,
            timeout_total=timeout_total,
        )

        data_dict, err = ensure_dict(
            data,
            context="asset owner profile",
            status_code=resp.status,
            url=url,
            raise_on_error=raise_on_error,
        )
        if data_dict is None:
            return {
                "status_code": resp.status,
                "profile": None,
                "json": data,
                "text": text,
                "error": err,
            }

        profile: Optional[AssetOwnerProfile] = parse_asset_owner_profile(data_dict)
        if profile is None and raise_on_error:
            msg = "Unexpected response format for asset owner profile (missing or invalid id)"
            _LOGGER.error(msg)
            raise ApiError(msg, status_code=resp.status, url=url, payload=data_dict)
        return {
            "status_code": resp.status,
            "profile": profile,
            "json": data,
            "text": text,
            "error": None,
        }

    async def async_fetch_available_uptime_months(
        self,
        asset_id: Optional[int] = None,
        *,
        raise_on_error: bool = True,
        retry_5xx_attempts: Optional[int] = None,
        timeout_total: Optional[float] = None,
    ) -> UptimeAvailableMonthsResult:
        """Fetch available uptime months for the given asset.

        Args:
            asset_id: Asset identifier. Defaults to `self.asset_id`.
            raise_on_error: If True, raises `ApiError` on invalid payload/HTTP errors.
            retry_5xx_attempts: Optional number of retries for 5xx.
            timeout_total: Optional total timeout override in seconds.

        Returns:
            UptimeAvailableMonthsResult: `{status_code, months, json, text, error}`.

        Raises:
            ValueError: If asset id is not provided.
            ApiError: If payload is not a list (when `raise_on_error=True`).
        """

        aid = asset_id or self.asset_id
        if not aid:
            _LOGGER.error("Cannot fetch uptime months: asset_id not set")
            raise ValueError("asset_id is required for uptime available months fetch")
        path = f"/asset-uptime/available-months/{aid}"
        url = self._build_url(path)
        resp, data, text = await self._request(
            path,
            raise_on_error=raise_on_error,
            retry_5xx_attempts=retry_5xx_attempts,
            timeout_total=timeout_total,
        )

        data_list, err = ensure_list(
            data,
            context="uptime available months",
            status_code=resp.status,
            url=url,
            raise_on_error=raise_on_error,
        )
        months: Optional[List[UptimeMonth]] = (
            parse_uptime_available_months(data_list) if data_list is not None else None
        )
        if months is None and err:
            return {
                "status_code": resp.status,
                "months": None,
                "json": data,
                "text": text,
                "error": err,
            }
        return {
            "status_code": resp.status,
            "months": months,
            "json": data,
            "text": text,
            "error": None,
        }

    async def async_fetch_uptime_history(
        self,
        asset_id: Optional[int] = None,
        *,
        raise_on_error: bool = True,
        retry_5xx_attempts: Optional[int] = None,
        timeout_total: Optional[float] = None,
    ) -> UptimeHistoryResult:
        """Fetch uptime ratio history per month for the given asset.

        Args:
            asset_id: Asset identifier. Defaults to `self.asset_id`.
            raise_on_error: If True, raises `ApiError` on invalid payload/HTTP errors.
            retry_5xx_attempts: Optional number of retries for 5xx.
            timeout_total: Optional total timeout override in seconds.

        Returns:
            UptimeHistoryResult: `{status_code, history, json, text, error}`.

        Raises:
            ValueError: If asset id is not provided.
            ApiError: If payload is not a list (when `raise_on_error=True`).
        """

        aid = asset_id or self.asset_id
        if not aid:
            _LOGGER.error("Cannot fetch uptime history: asset_id not set")
            raise ValueError("asset_id is required for uptime history fetch")
        path = f"/asset-uptime/bar-chart/history/{aid}"
        url = self._build_url(path)
        resp, data, text = await self._request(
            path,
            raise_on_error=raise_on_error,
            retry_5xx_attempts=retry_5xx_attempts,
            timeout_total=timeout_total,
        )

        data_list, err = ensure_list(
            data,
            context="uptime history",
            status_code=resp.status,
            url=url,
            raise_on_error=raise_on_error,
        )
        history: Optional[List[UptimeHistoryEntry]] = (
            parse_uptime_history(data_list) if data_list is not None else None
        )
        if history is None and err:
            return {
                "status_code": resp.status,
                "history": None,
                "json": data,
                "text": text,
                "error": err,
            }
        return {
            "status_code": resp.status,
            "history": history,
            "json": data,
            "text": text,
            "error": None,
        }

    async def async_fetch_uptime_pie(
        self,
        asset_id: Optional[int] = None,
        *,
        period: Optional[str] = None,
        raise_on_error: bool = True,
        retry_5xx_attempts: Optional[int] = None,
        timeout_total: Optional[float] = None,
    ) -> UptimePieResult:
        """Fetch uptime pie-chart data for a period (seconds per category).

        Args:
            asset_id: Asset identifier. Defaults to `self.asset_id`.
            period: Period in `YYYY-MM` format (e.g., "2026-01"). Defaults to current month.
            raise_on_error: If True, raises `ApiError` on invalid payload/HTTP errors.
            retry_5xx_attempts: Optional number of retries for 5xx.
            timeout_total: Optional total timeout override in seconds.

        Returns:
            UptimePieResult: `{status_code, slices, json, text, error}`.

        Raises:
            ValueError: If asset id is not provided or period format is invalid.
            ApiError: If payload is not a list (when `raise_on_error=True`).
        """

        aid = asset_id or self.asset_id
        if not aid:
            _LOGGER.error("Cannot fetch uptime pie: asset_id not set")
            raise ValueError("asset_id is required for uptime pie fetch")

        # Default to current month if period not provided
        if period is None:
            dt_now = datetime.datetime.now()
            period = f"{dt_now.year:04d}-{dt_now.month:02d}"
            _LOGGER.debug("Using current period for uptime pie: %s", period)
        elif not isinstance(period, str) or not period.strip():
            _LOGGER.error("Cannot fetch uptime pie: period format invalid")
            raise ValueError(
                "period must be a valid YYYY-MM string for uptime pie fetch"
            )
        # Compose path including query parameter
        path = f"/asset-uptime/pie-chart/{aid}?period={period}"
        url = self._build_url(path)
        resp, data, text = await self._request(
            path,
            raise_on_error=raise_on_error,
            retry_5xx_attempts=retry_5xx_attempts,
            timeout_total=timeout_total,
        )

        data_list, err = ensure_list(
            data,
            context="uptime pie",
            status_code=resp.status,
            url=url,
            raise_on_error=raise_on_error,
        )
        slices: Optional[List[UptimePieSlice]] = (
            parse_uptime_pie(data_list) if data_list is not None else None
        )
        if slices is None and err:
            return {
                "status_code": resp.status,
                "slices": None,
                "json": data,
                "text": text,
                "error": err,
            }
        return {
            "status_code": resp.status,
            "slices": slices,
            "json": data,
            "text": text,
            "error": None,
        }

    async def async_fetch_revenue(
        self,
        asset_id: Optional[int] = None,
        *,
        raise_on_error: bool = True,
        retry_5xx_attempts: Optional[int] = None,
        timeout_total: Optional[float] = None,
    ) -> RevenueResult:
        """Fetch revenue summary for the last invoice of an asset.

        Args:
            asset_id: Asset identifier. Defaults to `self.asset_id`.
            raise_on_error: If True, raises `ApiError` on invalid payload/HTTP errors.
            retry_5xx_attempts: Optional number of retries for 5xx.
            timeout_total: Optional total timeout override in seconds.

        Returns:
            RevenueResult: `{status_code, revenue, json, text, error}`.

        Raises:
            ValueError: If asset id is not provided.
            ApiError: If payload is not a dict (when `raise_on_error=True`).
        """

        aid = asset_id or self.asset_id
        if not aid:
            _LOGGER.error("Cannot fetch revenue: asset_id not set")
            raise ValueError("asset_id is required for revenue fetch")
        path = f"/asset/{aid}/revenue"
        url = self._build_url(path)
        resp, data, text = await self._request(
            path,
            raise_on_error=raise_on_error,
            retry_5xx_attempts=retry_5xx_attempts,
            timeout_total=timeout_total,
        )

        data_dict, err = ensure_dict(
            data,
            context="revenue",
            status_code=resp.status,
            url=url,
            raise_on_error=raise_on_error,
        )
        if data_dict is None:
            return {
                "status_code": resp.status,
                "revenue": None,
                "json": data,
                "text": text,
                "error": err,
            }

        revenue: Optional[Revenue] = parse_revenue(data_dict)
        if revenue is None and raise_on_error:
            msg = "Unexpected response format for revenue (missing or invalid id)"
            _LOGGER.error(msg)
            raise ApiError(msg, status_code=resp.status, url=url, payload=data_dict)
        return {
            "status_code": resp.status,
            "revenue": revenue,
            "json": data,
            "text": text,
            "error": None,
        }

    async def async_fetch_asset_owner(
        self,
        asset_owner_id: Optional[int] = None,
        *,
        raise_on_error: bool = True,
        retry_5xx_attempts: Optional[int] = None,
        timeout_total: Optional[float] = None,
    ) -> AssetOwnerDetailsResult:
        """Fetch asset owner details including installer, distributor, asset, and compensation.

        Args:
            asset_owner_id: Asset owner identifier. Defaults to `self.asset_owner_id`.
            raise_on_error: If True, raises `ApiError` on invalid payload/HTTP errors.
            retry_5xx_attempts: Optional number of retries for 5xx.
            timeout_total: Optional total timeout override in seconds.

        Returns:
            AssetOwnerDetailsResult: `{status_code, details, json, text, error}`.

        Raises:
            ValueError: If asset owner id is not provided.
            ApiError: If payload is not a dict (when `raise_on_error=True`).
        """

        aoid = asset_owner_id or self.asset_owner_id
        if not aoid:
            _LOGGER.error("Cannot fetch asset owner: asset_owner_id not set")
            raise ValueError("asset_owner_id is required for asset owner fetch")
        path = f"/asset-owner/{aoid}"
        url = self._build_url(path)
        resp, data, text = await self._request(
            path,
            raise_on_error=raise_on_error,
            retry_5xx_attempts=retry_5xx_attempts,
            timeout_total=timeout_total,
        )

        data_dict, err = ensure_dict(
            data,
            context="asset owner details",
            status_code=resp.status,
            url=url,
            raise_on_error=raise_on_error,
        )
        if data_dict is None:
            return {
                "status_code": resp.status,
                "details": None,
                "json": data,
                "text": text,
                "error": err,
            }

        details: Optional[AssetOwnerDetails] = parse_asset_owner_details(data_dict)
        if details is None and raise_on_error:
            msg = "Unexpected response format for asset owner details (missing or invalid id)"
            _LOGGER.error(msg)
            raise ApiError(msg, status_code=resp.status, url=url, payload=data_dict)
        return {
            "status_code": resp.status,
            "details": details,
            "json": data,
            "text": text,
            "error": None,
        }

    async def async_readout_sequence(
        self,
        asset_owner_id: Optional[int] = None,
        *,
        raise_on_error: bool = True,
        retry_5xx_attempts: Optional[int] = None,
        timeout_total: Optional[float] = None,
    ) -> Dict[str, Any]:
        """Run readout: discover asset ID then fetch asset.

        Args:
            asset_owner_id: Asset owner identifier. Defaults to `self.asset_owner_id`.
            raise_on_error: If True, raises `ApiError` on HTTP/validation errors.
            retry_5xx_attempts: Optional number of retries for 5xx during fetch.
            timeout_total: Optional total timeout override in seconds.

        Returns:
            Dict[str, Any]: `{asset_owner_id, asset_id, with_asset_resp, asset_resp}`.

        Raises:
            ValueError: If asset owner id is not provided.
            ApiError: On HTTP/validation errors when `raise_on_error=True`.
        """
        ao = asset_owner_id or self.asset_owner_id
        if not ao:
            _LOGGER.error("Cannot perform readout: asset_owner_id not set")
            raise ValueError("asset_owner_id is required for readout")

        _LOGGER.debug("Starting readout sequence for asset_owner_id %s", ao)
        with_resp = await self.async_fetch_asset_id(ao, raise_on_error=raise_on_error)
        asset_resp = None
        if self.asset_id:
            asset_resp = await self.async_fetch_asset(
                self.asset_id,
                raise_on_error=raise_on_error,
                retry_5xx_attempts=retry_5xx_attempts,
                timeout_total=timeout_total,
            )
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
        result_queue: Optional[asyncio.Queue] = None,
    ) -> asyncio.Task:
        """Start a background task that periodically fetches the asset.

        Args:
            interval_seconds: Fetch interval (minimum 5 seconds).
            run_immediately: If True, perform one fetch before scheduling.
            on_update: Optional callback invoked with `FlowerHubStatus` after fetch.
            result_queue: Optional queue where `FlowerHubStatus` is pushed.

        Returns:
            asyncio.Task: The created periodic task.

        Raises:
            ValueError: If interval is below 5 seconds.
            RuntimeError: If a periodic fetch is already running.
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

        async def _fetch_once():
            if not self.asset_id:
                await self.async_fetch_asset_id(self.asset_owner_id)
            if self.asset_id:
                await self.async_fetch_asset(self.asset_id)
                await _handle_update()

        async def _loop():
            if run_immediately:
                try:
                    await _fetch_once()
                except Exception as err:
                    _LOGGER.error(
                        "Initial fetch failed in periodic start: %s", err, exc_info=True
                    )
            try:
                while True:
                    await asyncio.sleep(float(interval_seconds))
                    try:
                        await _fetch_once()
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
        """Cancel the periodic asset fetch task if running."""
        t = getattr(self, "_asset_fetch_task", None)
        if t and not t.cancelled():
            _LOGGER.info("Stopping periodic asset fetch")
            t.cancel()
        self._asset_fetch_task = None

    def is_asset_fetch_running(self) -> bool:
        """Return True if the periodic asset fetch task is active."""
        t = getattr(self, "_asset_fetch_task", None)
        return bool(t and not t.done())

    # ----- Lifecycle & concurrency helpers -----
    async def close(self) -> None:
        """Cancel background tasks; does not close an injected session."""
        self.stop_periodic_asset_fetch()

    async def __aenter__(self) -> "AsyncFlowerhubClient":
        """Enter async context manager; returns the client itself."""
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        """Exit async context manager, ensuring cleanup via `close()`."""
        await self.close()

    def set_max_concurrency(self, max_requests: int) -> None:
        """Set a simple semaphore rate limiter for concurrent requests.

        Args:
            max_requests: Maximum concurrent in-flight HTTP requests. Pass 0/None to disable.
        """
        if max_requests and max_requests > 0:
            self._semaphore = asyncio.Semaphore(int(max_requests))
        else:
            self._semaphore = None
