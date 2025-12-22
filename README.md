# Flowerhub Portal Python Client

[![CI](https://github.com/MichaelPihlblad/flowerhub-portal-api_python-lib/actions/workflows/ci.yml/badge.svg)](https://github.com/MichaelPihlblad/flowerhub-portal-api_python-lib/actions/workflows/ci.yml)
[![Code Coverage](https://img.shields.io/badge/coverage-84%25-brightgreen)](https://github.com/MichaelPihlblad/flowerhub-portal-api_python-lib)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)

A lightweight, Python client for the [Flowerhub portal](https://portal.flowerhub.se) API with cookie-based JWT authentication.

**Related Projects:**
- [Home Assistant Custom Integration](https://github.com/MichaelPihlblad/homeassistant-flowerhub)

## Features

- Cookie-based JWT authentication with automatic token refresh
- Async/await support via `aiohttp`
- Client provides asset, consumption, and invoice data from API endpoints
- Designed for Home Assistant integrations and similar use cases


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

- `async_login(..)`
- `async_fetch_asset_id(...)`
- `async_fetch_asset(...)`
- `async_readout_sequence(...)` - Fetches assetID then asset info
- `async_fetch_electricity_agreement(...)`
- `async_fetch_invoices(...)`
- `async_fetch_consumption(...)`
- `async_fetch_system_notification(...)` - Unclear purpose, provides some status for flower/zavann systems, possibly for the user. Flower is electrical energy provider, Zavann seems to be the billing system.
- `start_periodic_asset_fetch(...)`
- `stop_periodic_asset_fetch(...)`
- `is_asset_fetch_running(...)`

### Data Models and Types

- Exceptions: `AuthenticationError`, `ApiError`.
- Status/model classes: `FlowerHubStatus`, `ElectricityAgreement`, `Invoice`, `ConsumptionRecord`, etc. (see `types.py`).
- Typed results: `AssetIdResult`, `AssetFetchResult`, `AgreementResult`, `InvoicesResult`, `ConsumptionResult`.

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
