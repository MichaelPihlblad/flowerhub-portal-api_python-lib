# Usage

## Async Client

```python
import aiohttp
from flowerhub_portal_api_client.async_client import AsyncFlowerhubClient
from flowerhub_portal_api_client.types import UptimePieSlice

async def main():
    async with aiohttp.ClientSession() as session:
        client = AsyncFlowerhubClient(session=session)
        await client.async_login("user@example.com", "password")
        result = await client.async_readout_sequence(asset_owner_id=42)
        print(result["asset_id"], client.flowerhub_status)
        if result["uptime_pie_resp"]:
            ratio = UptimePieSlice.calculate_uptime_ratio(result["uptime_pie_resp"]["slices"])
            print(f"Uptime ratio: {ratio:.1f}%")
```

## Error Handling
- `raise_on_error=True`: Raises `ApiError` for HTTP/validation issues.
- `on_auth_failed`: Callback on refresh failure (re-auth required).
- `on_api_error`: Callback invoked before raising `ApiError`.

## Timeouts & Retries
- `timeout_total`: Per-call override for total timeout.
- `retry_5xx_attempts`: Retries for server errors; honors `Retry-After`.
