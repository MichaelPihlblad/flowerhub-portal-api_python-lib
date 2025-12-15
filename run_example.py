"""Async example script using AsyncFlowerhubClient.

Demonstrates login, readout sequence and a simple periodic poll that mirrors
how an integration (e.g., Home Assistant) would poll and handle updates.
"""

from __future__ import annotations

import asyncio
import getpass
import json
import os
from pathlib import Path

try:
    import aiohttp
except Exception:  # pragma: no cover - optional dependency
    aiohttp = None

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


async def async_main():
    username, password = get_credentials()
    if aiohttp is None:
        raise RuntimeError(
            "aiohttp is required for the async example (install extras 'flowerhub-client[async]')"
        )
    async with aiohttp.ClientSession() as sess:
        client = AsyncFlowerhubClient(session=sess)
        await client.async_login(username, password)
        print("Logged in; asset_owner_id:", client.asset_owner_id)

        if not client.asset_owner_id:
            print("Error: assetOwnerId not found; cannot continue readout")
            return

        ro = await client.async_readout_sequence()
        with_resp = ro.get("with_asset_resp")
        asset_resp = ro.get("asset_resp")
        print(
            f"/asset-owner/{client.asset_owner_id}/withAssetId ->",
            getattr(with_resp, "status", None),
        )
        if asset_resp:
            print(f"/asset/{client.asset_id} ->", getattr(asset_resp, "status", None))

        # Periodic demo: start task that polls the asset every 5s and prints updates
        def _print_update(fh):
            if fh is None:
                print("Periodic update: no status available yet")
                return
            age = fh.age_seconds() if fh else None
            print(
                "Periodic update:",
                f"status={fh.status!r}",
                f"message={fh.message!r}",
                f"updated_timestamp={fh.updated_timestamp}",
                f"age_s={age:.1f}" if age is not None else "age_s=?",
            )

        print("Starting periodic asset fetch (5s, run_immediately=True)")
        client.start_periodic_asset_fetch(
            5, run_immediately=True, on_update=_print_update
        )
        try:
            await asyncio.sleep(16)
        except asyncio.CancelledError:
            print("Interrupted")
        finally:
            client.stop_periodic_asset_fetch()
            print("Periodic fetch stopped")


def main():
    asyncio.run(async_main())


if __name__ == "__main__":
    main()
