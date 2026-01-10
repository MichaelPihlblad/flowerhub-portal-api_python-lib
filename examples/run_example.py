"""Async example script using AsyncFlowerhubClient.

Demonstrates login, readout sequence and a simple periodic poll that mirrors
how an integration (e.g., Home Assistant) would poll and handle updates.
"""

from __future__ import annotations

import asyncio
import getpass
import json
import os
import sys
from pathlib import Path

# Add parent directory to path so we can import flowerhub_portal_api_client
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    import aiohttp
except Exception:  # pragma: no cover - optional dependency
    aiohttp = None

# pylint: disable=wrong-import-position
from flowerhub_portal_api_client import AsyncFlowerhubClient


def load_credentials_from_secrets() -> dict | None:
    project_file = Path(__file__).parent / "secrets.json"
    home_file = Path.home() / ".flowerhub_secrets.json"
    for p in (project_file, home_file):
        if p.exists():
            try:
                data = json.loads(p.read_text())
                if "username" in data and "password" in data:
                    return {"username": data["username"], "password": data["password"]}
            except Exception:
                continue
    return None


def get_credentials() -> tuple[str, str]:
    creds = load_credentials_from_secrets()
    if creds:
        return creds["username"], creds["password"]
    username = os.environ.get("FH_USER")
    password = os.environ.get("FH_PASSWORD")
    if username and password:
        return username, password
    print("Credentials not found in secrets file or environment variables.")
    username = input("Enter Flowerhub username/email: ").strip()
    password = getpass.getpass("Enter Flowerhub password: ")
    return username, password


async def _fetch_all_endpoints(client: AsyncFlowerhubClient) -> None:
    """Fetch all available endpoints to demonstrate API capabilities."""
    print("\n📡 Fetching additional endpoints...")

    # Asset owner profile
    owner_profile = await client.async_fetch_asset_owner_profile(raise_on_error=False)
    profile = owner_profile.get("profile") if owner_profile else None
    if profile:
        print(f"  ✓ asset_owner_profile: {profile.firstName} {profile.lastName}")

    # System notification
    notification = await client.async_fetch_system_notification(raise_on_error=False)
    if notification and notification.get("status_code") == 200:
        print(f"  ✓ system_notification: status {notification.get('status_code')}")

    # Electricity agreement
    agreement = await client.async_fetch_electricity_agreement(raise_on_error=False)
    agree = agreement.get("agreement") if agreement else None
    if agree:
        cons_state = (
            getattr(agree.consumption, "stateCategory", None)
            if agree.consumption
            else None
        )
        prod_state = (
            getattr(agree.production, "stateCategory", None)
            if agree.production
            else None
        )
        print(
            f"  ✓ electricity_agreement: consumption={cons_state}, production={prod_state}"
        )

    # Invoices
    invoices = await client.async_fetch_invoices(raise_on_error=False)
    inv_list = invoices.get("invoices") if invoices else None
    if inv_list:
        print(f"  ✓ invoices: {len(inv_list)} found")

    # Consumption
    consumption = await client.async_fetch_consumption(raise_on_error=False)
    cons_data = consumption.get("consumption") if consumption else None
    if cons_data:
        print(f"  ✓ consumption: {len(cons_data)} records")

    # Uptime history
    uptime_history = await client.async_fetch_uptime_history(raise_on_error=False)
    hist_data = uptime_history.get("history") if uptime_history else None
    if hist_data:
        print(f"  ✓ uptime_history: {len(hist_data)} months")

    # Available uptime months
    uptime_months = await client.async_fetch_available_uptime_months(
        raise_on_error=False
    )
    months = uptime_months.get("months") if uptime_months else None
    if months:
        print(f"  ✓ available_uptime_months: {len(months)} months")

    # Revenue (requires asset_id)
    revenue = await client.async_fetch_revenue(raise_on_error=False)
    rev = revenue.get("revenue") if revenue else None
    if rev:
        comp = getattr(rev, "compensation", None)
        comp_str = f"{comp:.2f}" if comp is not None else "N/A"
        print(f"  ✓ revenue: compensation={comp_str}")


async def async_main():
    username, password = get_credentials()
    if aiohttp is None:
        raise RuntimeError(
            "aiohttp is required for the async example (install extras 'flowerhub-client[async]')"
        )
    async with aiohttp.ClientSession() as sess:
        client = AsyncFlowerhubClient(session=sess)
        print(f"🔐 Logging in as: {username}")
        await client.async_login(username, password)
        print("✓ Logged in successfully")
        print(f"  asset_owner_id: {client.asset_owner_id}")

        if not client.asset_owner_id:
            print("✗ Error: assetOwnerId not found; cannot continue readout")
            return

        # Demonstrate core readout sequence
        print("\n📊 Fetching readout sequence...")
        ro = await client.async_readout_sequence()
        with_resp = ro.get("with_asset_resp")
        asset_resp = ro.get("asset_resp")
        uptime_pie_resp = ro.get("uptime_pie_resp")

        if with_resp:
            asset_id = with_resp.get("asset_id")
            print(
                f"  ✓ /asset-owner/{client.asset_owner_id}/withAssetId: status {with_resp.get('status_code', '?')}, asset_id={asset_id}"
            )
        if asset_resp:
            fh_status = asset_resp.get("flowerhub_status")
            conn_status = fh_status.status if fh_status else None
            conn_message = fh_status.message if fh_status else None
            print(
                f"  ✓ /asset/{client.asset_id}: status {asset_resp.get('status_code', '?')}, connection_status={conn_status!r}, message={conn_message!r}"
            )
        if uptime_pie_resp:
            ratio = uptime_pie_resp.get("uptime_ratio")
            ratio_str = f"{ratio:.1f}%" if ratio is not None else "N/A"
            uptime_secs = uptime_pie_resp.get("uptime")
            downtime_secs = uptime_pie_resp.get("downtime")
            print(
                f"  ✓ uptime_pie: {ratio_str} uptime ratio, uptime={uptime_secs}s, downtime={downtime_secs}s"
            )

        # Fetch all other endpoints
        await _fetch_all_endpoints(client)

        # Periodic demo: start task that polls the asset every 5s and prints updates
        def _print_update(fh):
            if fh is None:
                print("  [periodic] no status available yet")
                return
            age = fh.age_seconds() if fh else None
            age_str = f"{age:.1f}s" if age is not None else "?"
            print(
                f"  [periodic] {fh.status!r} | {fh.message!r} | updated {age_str} ago"
            )

        print("\n⏰ Starting periodic asset fetch (5s interval, run_immediately=True)")
        client.start_periodic_asset_fetch(
            5, run_immediately=True, on_update=_print_update
        )
        try:
            await asyncio.sleep(16)
        except asyncio.CancelledError:
            print("⚠ Interrupted")
        finally:
            client.stop_periodic_asset_fetch()
            print("✓ Periodic fetch stopped")


def main():
    asyncio.run(async_main())


if __name__ == "__main__":
    main()
