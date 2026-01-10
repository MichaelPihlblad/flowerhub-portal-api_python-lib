"""Example: Handling authentication errors and automatic re-login.

This example demonstrates how to use the AuthenticationError exception
and on_auth_failed callback to detect when:
  - Login fails (invalid credentials - 401 response)
  - Token refresh fails during subsequent API calls
Re-authentication is then required in both cases.
"""

import asyncio

import aiohttp

from flowerhub_portal_api_client import AsyncFlowerhubClient, AuthenticationError


async def example_with_exception_handling():
    """Example 1: Using try/except to catch AuthenticationError.

    AuthenticationError can be raised during login (invalid credentials)
    or during API calls (token refresh failed).
    """
    username = "user@example.com"
    password = "password"

    async with aiohttp.ClientSession() as session:
        client = AsyncFlowerhubClient(session=session)

        # Initial login - can raise AuthenticationError if credentials are invalid
        try:
            await client.async_login(username, password)
        except AuthenticationError:
            print("Login failed: Invalid credentials")
            return

        try:
            # This will automatically retry with refresh token on 401
            # If refresh fails and retry still returns 401, raises AuthenticationError
            await client.async_fetch_asset_id()
        except AuthenticationError:
            print("Token refresh failed, re-authenticating...")
            # Re-login and retry
            try:
                await client.async_login(username, password)
                await client.async_fetch_asset_id()
            except AuthenticationError:
                print("Re-login failed: Credentials are no longer valid")


async def example_with_callback():
    """Example 2: Using callback for automatic re-authentication.

    The callback is invoked when token refresh fails during API calls.
    For login failures, you still need try/except.
    """
    username = "user@example.com"
    password = "password"
    needs_reauth = {"flag": False}

    def auth_failed_callback():
        """Called when token refresh fails during API calls."""
        print("Token refresh failed, setting re-auth flag")
        needs_reauth["flag"] = True

    async with aiohttp.ClientSession() as session:
        client = AsyncFlowerhubClient(
            session=session, on_auth_failed=auth_failed_callback
        )

        # Initial login - wrap in try/except for login failures
        try:
            await client.async_login(username, password)
        except AuthenticationError:
            print("Login failed: Invalid credentials")
            return

        try:
            await client.async_fetch_asset_id()
        except AuthenticationError:
            # Callback was already invoked
            if needs_reauth["flag"]:
                print("Re-authenticating due to callback signal")
                try:
                    await client.async_login(username, password)
                    needs_reauth["flag"] = False
                    await client.async_fetch_asset_id()
                except AuthenticationError:
                    print("Re-login failed: Credentials are no longer valid")


async def home_assistant_pattern():
    """Example 3: Pattern suitable for Home Assistant integration.

    In Home Assistant, you would typically use this pattern in your
    DataUpdateCoordinator._async_update_data method.

    Note: Wrap async_login() in try/except to catch both login failures
    and token refresh failures.
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

        # Initial login - wrap in try/except for login failures
        try:
            await client.async_login(username, password)
        except AuthenticationError:
            print("Initial login failed: Invalid credentials")
            # Signal reauth is needed
            request_reauth()
            return

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
                # Otherwise re-login and retry (token refresh failed)
                try:
                    await client.async_login(username, password)
                    # Retry the data fetch
                    data = await client.async_readout_sequence()
                    print(f"Fetched data after re-login: {data}")
                    reauth_needed["flag"] = False
                except AuthenticationError:
                    print("Re-login failed: Credentials are no longer valid")
                    request_reauth()
                    break

            # Wait before next update
            await asyncio.sleep(60)


if __name__ == "__main__":
    print("Example 1: Exception handling")
    asyncio.run(example_with_exception_handling())

    print("\nExample 2: Callback pattern")
    asyncio.run(example_with_callback())

    print("\nExample 3: Home Assistant pattern")
    asyncio.run(home_assistant_pattern())
