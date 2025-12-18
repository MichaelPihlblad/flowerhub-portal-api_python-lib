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

# Install pre-commit hooks
pre-commit install

# Run all checks
pre-commit run --all-files
pytest tests --cov=flowerhub_portal_api_client
```

## Running Examples

Set credentials via environment variables:

```bash
export FH_USER="you@example.com"
export FH_PASSWORD="your_password"
python examples/run_example.py
```

Or create `examples/secrets.json`:

```json
{
  "username": "you@example.com",
  "password": "your_password"
}
```

## API Documentation

For detailed information about the Flowerhub portal API endpoints used by this Python client library, such as request/response formats, and data structures, see [`API_DOCUMENTATION.md`](API_DOCUMENTATION.md).


Periodic status refresh (background polling) 💡
------------------------------------------
The client provides a convenience helper to periodically refresh the asset's
`flowerHubStatus` in a background asyncio Task and deliver updates to your code:

- `start_periodic_asset_fetch(interval_seconds=60, run_immediately=False, on_update=None, result_queue=None)`
  - `on_update` (callable) will be invoked with a `FlowerHubStatus` object on every successful refresh (called in the event loop).
  - `result_queue` (an `asyncio.Queue`) will receive `FlowerHubStatus` objects via non-blocking `put_nowait`.
  - `interval_seconds` must be >= 5 (default 60).

Example (simple async usage):

```py
import asyncio
import aiohttp
from flowerhub_portal_api_client import AsyncFlowerhubClient

async def main():
	async with aiohttp.ClientSession() as session:
		client = AsyncFlowerhubClient(base_url="https://api.portal.flowerhub.se", session=session)
		await client.async_login("user@example.com", "password")

		q = asyncio.Queue()
		client.start_periodic_asset_fetch(60, run_immediately=True, result_queue=q)
		try:
			while True:
				fhs = await q.get()
				print("Queued update:", fhs.status, fhs.message, f"age={fhs.age_seconds():.1f}s")
		finally:
			client.stop_periodic_asset_fetch()

asyncio.run(main())
```

If you prefer a callback approach, pass `on_update` which will be called with
a `FlowerHubStatus` instance each time the status is refreshed. Avoid blocking
operations in the callback because it's executed in the event loop.

```
`FlowerHubStatus` fields:
- `status` — textual status (e.g., "Connected")
- `message` — human-friendly message
- `updated_at` — UTC datetime when the status was recorded
- `age_seconds()` — helper returning the age in seconds (float) or `None` if timestamp missing
