# Flowerhub Portal Python Client

[![CI](https://github.com/MichaelPihlblad/flowerhub-portal-api_python-lib/actions/workflows/ci.yml/badge.svg)](https://github.com/MichaelPihlblad/flowerhub-portal-api_python-lib/actions/workflows/ci.yml)
[![Code Coverage](https://img.shields.io/badge/coverage-84%25-brightgreen)](https://github.com/MichaelPihlblad/flowerhub-portal-api_python-lib)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)

A lightweight, Python client for the [Flowerhub portal](https://portal.flowerhub.se) API with cookie-based JWT authentication.

**Related Projects:**
- [Home Assistant Custom Integration](https://github.com/MichaelPihlblad/homeassistant-flowerhub)  (known consumer)

## Features

- **Authentication**: Cookie-based JWT with automatic token refresh and `AuthenticationError` on login failure
- **Async/await**: Full async support via `aiohttp` with configurable timeouts and retries
- **API coverage**: 12+ endpoints including assets, consumption, invoices, uptime metrics, revenue, and profiles
- **Type-safe**: Fully typed with `TypedDict` result types extending `StandardResult` base class
- Designed for Home Assistant integrations and similar use cases with robust error handling


## Installation

### From PyPI

```bash
pip install flowerhub-portal-api-client
```

### From Source

```bash
git clone https://github.com/MichaelPihlblad/flowerhub-portal-api_python-lib.git
cd flowerhub-portal-api_python-lib
pip install -e ".[async]"
```

## Quick Start

```python
import asyncio
from flowerhub_portal_api_client import AsyncFlowerhubClient

async def main():
    async with aiohttp.ClientSession() as session:
        client = AsyncFlowerhubClient(session=session)

        # Login
        result = await client.async_login("user@example.com", "password")

        # Fetch asset information
        await client.async_readout_sequence()

        # Access asset status
        if client.flowerhub_status:
            print(f"Status: {client.flowerhub_status.status}")
            print(f"Message: {client.flowerhub_status.message}")

asyncio.run(main())
```

## Documentation

- **Online**: [Library documentation](https://michaelpihlblad.github.io/flowerhub-portal-api_python-lib/) — hosted on GitHub Pages, auto-published on push to `main`.
- **Local preview**:

```bash
pip install -r dev-requirements.txt
mkdocs serve
```

To build the static site locally:

```bash
mkdocs build --strict
```

## Configuration

### Credentials

**⚠️ Security Warning**: Never commit real credentials to the repository. The file `examples/secrets.json` is in `.gitignore` — use it as a template for local development only. Always use environment variables or secure credential managers in production. The pre-commit hook `detect-private-key` will block commits containing suspected private keys.

## Development Setup

For contributors and local development:

```bash
# Clone and setup environment
git clone https://github.com/MichaelPihlblad/flowerhub-portal-api_python-lib.git
cd flowerhub-portal-api_python-lib
python -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt
pip install -r dev-requirements.txt

  - `result_queue` (an `asyncio.Queue`) will receive `FlowerHubStatus` objects via non-blocking `put_nowait`.
  - `interval_seconds` must be >= 5 (default 60).
```


## Usage Guide

- **Per-call options**: All public fetch methods accept `raise_on_error` (default `True`), `retry_5xx_attempts` (controls 5xx/429 retries; `None` or `0` disables), and `timeout_total` (per-call `aiohttp.ClientTimeout` override; default is 10s, `0`/`None` disables timeout).
- **Error handling**: `AuthenticationError` is raised after a failed refresh retry on `401`; `ApiError` is raised for other HTTP errors or validation issues when `raise_on_error=True`. Use `on_auth_failed` and `on_api_error` callbacks for integration-specific handling.
- **Lifecycle**: Prefer `async with AsyncFlowerhubClient(...)` or call `close()` to stop background tasks. The client does not close an injected session.
- **Concurrency / rate limiting**: Call `set_max_concurrency(n)` to limit in-flight requests with a semaphore; pass `0`/`None` to disable.
- **Retry/backoff**: 5xx and 429 responses are retried with a small jitter; 429 honors `Retry-After` when provided.

### Public Methods (async)

**Authentication:**
- `async_login(username, password)` - Authenticate and establish session

**Core Data Fetching:**
- `async_fetch_asset_id()` - Discover asset ID for the authenticated user
- `async_fetch_asset()` - Fetch asset details and FlowerHub status
- `async_readout_sequence()` - Convenient readout of: asset ID → asset info → uptime pie

**Financial Data:**
- `async_fetch_invoices()` - Fetch billing invoices
- `async_fetch_consumption()` - Fetch consumption records
- `async_fetch_revenue()` - Fetch revenue/compensation data

**Uptime Metrics:**
- `async_fetch_uptime_pie(period=None)` - Uptime distribution with automatic ratio calculation
- `async_fetch_uptime_history()` - Monthly uptime percentages
- `async_fetch_available_uptime_months()` - Available month options for uptime queries

**User & System:**
- `async_fetch_asset_owner_profile()` - Fetch owner profile with contact info
- `async_fetch_asset_owner()` - Fetch complete owner details (installer/distributor)
- `async_fetch_electricity_agreement()` - Fetch consumption/production agreement states
- `async_fetch_system_notification()` - System-level notifications (Flower/Zavann status)

**Lifecycle & Monitoring:**
- `start_periodic_asset_fetch(interval_seconds, ...)` - Start background polling
- `stop_periodic_asset_fetch()` - Stop background polling
- `is_asset_fetch_running()` - Check polling status

### Data Models and Types

**Exceptions:**
- `AuthenticationError` - Raised on 401 authentication failures after refresh retry
- `ApiError` - Raised for HTTP errors or validation issues (includes `status_code`, `url`, `payload`)

**Result Types (all extend `StandardResult`):**
- Base: `StandardResult` - Common envelope with `status_code`, `json`, `text`, `error`
- Asset: `AssetIdResult`, `AssetFetchResult`
- Financial: `InvoicesResult`, `ConsumptionResult`, `RevenueResult`
- Uptime: `UptimeAvailableMonthsResult`, `UptimeHistoryResult`, `UptimePieResult`
- User: `ProfileResult`, `AssetOwnerDetailsResult`
- Other: `AgreementResult`, `SystemNotificationResult` (alias to StandardResult)

**Data Classes:**
- Status: `FlowerHubStatus` (device status with age tracking)
- Financial: `Invoice`, `InvoiceLine`, `ConsumptionRecord`, `Revenue`
- Uptime: `UptimeMonth`, `UptimeHistoryEntry`
- User: `AssetOwnerProfile`, `AssetOwnerDetails`, `SimpleInstaller`, `SimpleDistributor`
- Other: `ElectricityAgreement`, `AgreementState`, `Asset`, `Inverter`, `Battery`

See [types.py](flowerhub_portal_api_client/types.py) for complete type definitions.

### Options, Callbacks, and Lifecycle

- Callbacks: `on_auth_failed` (refresh failed + second 401), `on_api_error` (before raising ApiError when `raise_on_error=True`).
- Concurrency: `set_max_concurrency(n)` adds a semaphore-based rate limiter; `0`/`None` disables.
- Context manager: `async with AsyncFlowerhubClient(...)` or `close()` to stop periodic tasks; injected sessions are not closed by the client.

### Modules

- `exceptions.py`: `AuthenticationError`, `ApiError` (includes `status_code`, `url`, `payload`).
- `types.py`: dataclasses and TypedDicts used by the client (`FlowerHubStatus`, `ElectricityAgreement`, `Invoice`, `ConsumptionRecord`, `AssetIdResult`, `AssetFetchResult`, etc.).
- `parsers.py`: pure helpers to parse/validate API payloads (used by the client but can be imported directly for advanced/standalone parsing).

## Authentication Error Handling

The client automatically handles token refresh on `401 Unauthorized` responses. If the refresh fails and the request still returns `401`, an `AuthenticationError` is raised, indicating that the user needs to login again.

### Exception-Based Handling

```python
from flowerhub_portal_api_client import AsyncFlowerhubClient, AuthenticationError

try:
    await client.async_fetch_asset_id()
except AuthenticationError:
    # Token refresh failed, re-authentication required
    await client.async_login(username, password)
    await client.async_fetch_asset_id()
```

### Callback-Based Handling

For Home Assistant integrations or event-driven architectures:

```python
def on_auth_failed():
    """Called when authentication fails and re-login is needed."""
    print("Re-authentication required")
    # Trigger reauth flow, set flag, etc.

client = AsyncFlowerhubClient(
    session=session,
    on_auth_failed=on_auth_failed
)
```

See `examples/auth_error_handling.py` for complete examples including Home Assistant patterns.
