# Flowerhub Portal Python Client (example)

This small client demonstrates how to replicate a browser-based session for the Flowerhub portal API using cookie-based JWT authentication.

Features:
- Login via `/auth/login` that sets Authentication (access) and Refresh cookies
- Calls to protected endpoints using the same session (cookies sent automatically)
- Refresh via `/auth/refresh-token` when a 401 Unauthorized is returned
- Displays decoded JWT claims for access/refresh cookies for debugging

Usage:

1) Install dependencies (virtualenv or similar):

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

2) Run the example (replace credentials):

```bash
export FH_USER="you@example.com"
export FH_PASSWORD="hunter2"
python run_example.py
```

Quick Start (run the async example)
----------------------------------
These quick commands set up a virtual environment, install the async dependency (`aiohttp`) via the package extra, and run the async example in `run_example.py`:

```bash
# create and activate venv
python -m venv .venv
source .venv/bin/activate

# upgrade packaging tools (recommended)
pip install --upgrade pip setuptools wheel

# install test/dev deps and optional async dependency via extras
pip install -r requirements.txt
pip install -e ".[async]"   # installs aiohttp

# run the example (set credentials via env or secrets.json)
export FH_USER="you@example.com"
export FH_PASSWORD="hunter2"
python run_example.py
```

Tip: if you prefer not to use editable installs, run `pip install ".[async]"` instead.

Developing / Linting
--------------------
If you're contributing or developing locally, install the dev tools and enable the `pre-commit` hooks to automatically run linters and formatters on each commit:

```bash
# create and activate your venv (if not already done)
python -m venv .venv
source .venv/bin/activate

# install base deps and development tools
pip install -r requirements.txt
pip install -r dev-requirements.txt

# install pre-commit hooks into your local repo
pre-commit install

# run hooks on all files (useful to format everything once)
pre-commit run --all-files

# optionally run formatters/linters directly
python -m ruff check --fix .
python -m black .
python -m isort .
```

Running the pre-commit hooks locally and in CI helps keep the codebase consistent and avoids style-related PR churn.

Alternatively, specify credentials using a secrets JSON file (recommended for local dev only - do not commit this file):

Create a local `secrets.json` or `~/.flowerhub_secrets.json` (kept out of git) using the sample file `secrets.example.json` included in this repo.

`secrets.json` or `~/.flowerhub_secrets.json` (format):

```json
{
	"username": "you@example.com",
	"password": "hunter2"
}
```

If no secrets file or environment variables are present, the script will prompt for username/password interactively.

Notes:
- This client deliberately decodes JWTs without signature verification (for debugging purposes). Do not use the accounting decode method for authentication decisions in production.
- Some endpoints are CORS-protected; we set the `Origin` header in the requests to mimic a browser context so that servers expecting that header will accept the requests.
- If the API supports a Bearer Authorization header, a modern API integration could instead store the access token and use `Authorization: Bearer <access_token>` for API calls. The HAR shows cookies are used and CORS credentials are enabled.

## API Documentation

For detailed information about the API endpoints used by the FlowerHub Python client library, request/response formats, and data structures, see [`API_DOCUMENTATION.md`](API_DOCUMENTATION.md).

This documentation includes:
- Complete endpoint specifications for endpoints used by the library
- Request/response schemas with example data
- Authentication requirements
- Error handling
- Data types and status values

Extending for Home Assistant:
- Use `aiohttp` and `DataUpdateCoordinator` for an async integration; adapt the `login` and `refresh` flows to use `aiohttp.ClientSession` and manage cookies using `CookieJar`.

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

Breaking change / migration note ⚠️
---------------------------------
This project now provides an async-only client API. The previously available
`FlowerhubClient` (synchronous) has been removed; please migrate to
`AsyncFlowerhubClient` and use an `aiohttp.ClientSession`. See the example
above for a quick migration snippet.
```

`FlowerHubStatus` fields:
- `status` — textual status (e.g., "Connected")
- `message` — human-friendly message
- `updated_at` — UTC datetime when the status was recorded
- `age_seconds()` — helper returning the age in seconds (float) or `None` if timestamp missing


Home Assistant integration example (DataUpdateCoordinator) ⚙️
----------------------------------------------------------------
Below is a minimal example showing how to integrate the async client with
Home Assistant using a `DataUpdateCoordinator`. This pattern centralizes polling
and makes it easy to create platform entities (sensors, binary sensors, etc.).

```py
from datetime import timedelta
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from flowerhub_portal_api_client import AsyncFlowerhubClient


async def async_setup_entry(hass, entry):
	session = async_get_clientsession(hass)
	client = AsyncFlowerhubClient(base_url=entry.data["base_url"], session=session)

	async def async_fetch() -> dict:
		# perform the readout and return relevant data for your entities
		await client.async_readout_sequence()
		status = client.flowerhub_status
		return {"status": status.status if status else None, "message": status.message if status else None}

	coordinator = DataUpdateCoordinator(
		hass,
		logger=logging.getLogger(__name__),
		name="flowerhub",
		update_method=async_fetch,
		update_interval=timedelta(seconds=60),
	)

	# Do an initial fetch so entities can be populated immediately
	await coordinator.async_refresh()

	hass.data.setdefault("flowerhub", {})[entry.entry_id] = {"client": client, "coordinator": coordinator}

	# forward platforms (e.g., sensor)
	hass.config_entries.async_setup_platforms(entry, ["sensor"])

```

Entity classes then use `CoordinatorEntity` and reference `coordinator.data` for state.
This keeps all refresh logic centralized and HA-friendly.
