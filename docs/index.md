# Flowerhub Portal API Client

Lightweight Python client (sync + async) for Flowerhub Portal API, designed for Home Assistant integrations.

## Version 1.0.0 Highlights

- **12+ API endpoints**: Complete coverage including assets, uptime metrics, revenue, invoices, consumption, and profiles
- **Type-safe architecture**: All result types extend `StandardResult` base class with consistent envelope fields
- **Uptime monitoring**: Dedicated endpoints with automatic ratio calculations and historical data
- **Production-ready**: Fully tested with Home Assistant integration (32/32 tests passing)

## Key Features

- Async-friendly methods with refresh, retries, and timeouts
- Dict-based results conforming to `TypedDict` contracts with required envelope fields
- Automatic authentication error handling with `AuthenticationError` exceptions
- Minimal dependencies and clear error handling
- Comprehensive type hints and IDE support

See `Usage` and `Library interface reference` sections for details on the library.
See `REST_API_reference` for specification of flowerhub portal REST API endpoints etc.
