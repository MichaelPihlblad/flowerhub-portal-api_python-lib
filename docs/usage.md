# Usage

## Async Client

```python
import aiohttp
from flowerhub_portal_api_client.async_client import AsyncFlowerhubClient

async def main():
    async with aiohttp.ClientSession() as session:
        client = AsyncFlowerhubClient(session=session)
        await client.async_login("user@example.com", "password")

        # Fetch complete readout including uptime
        result = await client.async_readout_sequence()
        print(f"Asset ID: {result['asset_id']}")
        print(f"Status: {client.flowerhub_status}")

        # Access uptime data (automatically included in readout)
        if result["uptime_pie_resp"]:
            pie = result["uptime_pie_resp"]
            print(f"Uptime ratio: {pie['uptime_ratio']:.1f}%")
            print(f"Uptime: {pie['uptime']/3600:.1f}h")
            print(f"Downtime: {pie['downtime']/3600:.1f}h")
            print(f"No data: {pie['noData']/3600:.1f}h")

        # Fetch specific month uptime
        pie_result = await client.async_fetch_uptime_pie(period="2026-01")
        if pie_result["uptime_ratio"]:
            print(f"January 2026 uptime: {pie_result['uptime_ratio']:.2f}%")
```

## Error Handling
- `raise_on_error=True`: Raises `ApiError` for HTTP/validation issues.
- `on_auth_failed`: Callback on refresh failure (re-auth required).
- `on_api_error`: Callback invoked before raising `ApiError`.

## Timeouts & Retries
- `timeout_total`: Per-call override for total timeout.
- `retry_5xx_attempts`: Retries for server errors; honors `Retry-After`.
