"""Example: Handling authentication errors and automatic re-login.

This example demonstrates how to use the AuthenticationError exception
and on_auth_failed callback to detect when token refresh fails and
re-authentication is required.
"""

import asyncio

import aiohttp

from flowerhub_portal_api_client import AsyncFlowerhubClient, AuthenticationError


async def example_with_exception_handling():
    """Example 1: Using try/except to catch AuthenticationError."""
    username = "user@example.com"
    password = "password"

    async with aiohttp.ClientSession() as session:
        client = AsyncFlowerhubClient(session=session)

        # Initial login
        await client.async_login(username, password)

        try:
            # This will automatically retry with refresh token on 401
            # If refresh fails and retry still returns 401, raises AuthenticationError
            await client.async_fetch_asset_id()
        except AuthenticationError:
            print("Token refresh failed, re-authenticating...")
            # Re-login and retry
            await client.async_login(username, password)
            await client.async_fetch_asset_id()


async def example_with_callback():
    """Example 2: Using callback for automatic re-authentication."""
    username = "user@example.com"
    password = "password"
    needs_reauth = {"flag": False}

    def auth_failed_callback():
        """Called when token refresh fails."""
        print("Authentication failed, setting re-auth flag")
        needs_reauth["flag"] = True

    async with aiohttp.ClientSession() as session:
        client = AsyncFlowerhubClient(
            session=session, on_auth_failed=auth_failed_callback
        )

        # Initial login
        await client.async_login(username, password)

        try:
            await client.async_fetch_asset_id()
        except AuthenticationError:
            # Callback was already invoked
            if needs_reauth["flag"]:
                print("Re-authenticating due to callback signal")
                await client.async_login(username, password)
                needs_reauth["flag"] = False
                await client.async_fetch_asset_id()


async def home_assistant_pattern():
    """Example 3: Pattern suitable for Home Assistant integration.

    In Home Assistant, you would typically use this pattern in your
    DataUpdateCoordinator._async_update_data method.
    """
    username = "user@example.com"
    password = "password"

    async with aiohttp.ClientSession() as session:
        reauth_needed = {"flag": False}

        def request_reauth():
            """Signal that re-authentication flow should be triggered."""
            reauth_needed["flag"] = True
            # In HA, you would trigger a reauth flow here:
            # self.hass.async_create_task(
            #     self.hass.config_entries.flow.async_init(
            #         DOMAIN,
            #         context={"source": "reauth"},
            #         data=self.config_entry.data,
            #     )
            # )

        client = AsyncFlowerhubClient(session=session, on_auth_failed=request_reauth)

        # Initial login
        await client.async_login(username, password)

        # In your coordinator update loop
        while True:
            try:
                # Fetch data
                data = await client.async_readout_sequence()
                print(f"Fetched data: {data}")

                # Reset flag on success
                reauth_needed["flag"] = False

            except AuthenticationError:
                if reauth_needed["flag"]:
                    print("Waiting for user to re-authenticate...")
                    # In HA, this would raise ConfigEntryAuthFailed
                    # which triggers the reauth flow UI
                    break
                # Otherwise re-login and retry
                await client.async_login(username, password)

            # Wait before next update
            await asyncio.sleep(60)


if __name__ == "__main__":
    print("Example 1: Exception handling")
    asyncio.run(example_with_exception_handling())

    print("\nExample 2: Callback pattern")
    asyncio.run(example_with_callback())

    print("\nExample 3: Home Assistant pattern")
    asyncio.run(home_assistant_pattern())
