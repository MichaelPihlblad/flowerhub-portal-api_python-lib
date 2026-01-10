# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).


## [1.0.0] - 2026-01-10

### Added
- New API endpoints
  - profile
  - asset-owner
  - revenue
  - uptime
    - response extended to include derived `uptime_ratio` (percentage) alongside raw slices.

### Changed
- **Authentication**: Login now raises `AuthenticationError` explicitly on 401 responses
- `async_readout_sequence` now also fetches the uptime pie endpoint and returns it as `uptime_pie_resp`
- Improved aiohttp import handling with `TYPE_CHECKING` guard and defensive timeout application.
- Code quality: All pylint errors resolved (10/10 rating); imports reorganized with proper ordering; datetime imported at module level for robustness.

### Fixed
- Type casting in `simulated_run.py` for better type hints.

### Notes
- Validated with Home Assistant integration: `AuthenticationError` is already handled throughout config_flow and coordinator patterns.

## [0.4.0] - 2025-12-23

### Changed
- Improved code readability, renamed internal variables
- Excluding test files from linting to focus on library code quality
- Documentation revised

### Fixed
- Mypy type error in `_should_retry_5xx` method: improved handling of `Optional[int]` comparison by explicitly checking for None

### CI Changes
- CI/CD improvements:
  - Updated GitHub Actions workflows to exclude tests from linting
  - Proper dependency installation in pre-commit workflow

## [0.4.0-beta] - 2025-12-22

### Breaking
- Public async fetch methods now return typed result dicts (e.g., `AssetFetchResult`) instead of aiohttp `ClientResponse` objects.
- `_request` raises `ApiError` on HTTP `>=400` by default (`raise_on_error=True`); set `raise_on_error=False` to preserve prior non-raising behavior.
- `async_fetch_asset_id` / `async_fetch_asset` now raise `ValueError` when required IDs are missing (previously returned `None`).

### Added
- Modularized exceptions (`exceptions.py`), parsers (`parsers.py`), and shared types (`types.py`) with `TypedDict` result contracts for async helpers.
- Per-call timeout override and default request timeout via `aiohttp.ClientTimeout` helper; linear backoff with jitter for 5xx/429 retries, plus optional 5xx retry limit.
- Optional callbacks: `on_api_error` (API errors) and existing `on_auth_failed` for reauth flows.
- Concurrency limiter via `set_max_concurrency` using an `asyncio.Semaphore`.

### Changed
- Hardened parsing/validation for asset, invoices, consumption, and electricity agreement responses (schema checks with informative errors).
- Improved 401 refresh flow; logs now emit clearer warnings/errors; status logging normalized across helpers.

### Fixed
- More robust handling of non-JSON responses; safer type conversions for asset IDs and status payloads.

## [0.3.2] - 2025-12-18

### Changed
- Version bump to avoid tag conflict with 0.3.1 (no code changes)

## [0.3.1] - 2025-12-18

### Fixed
- Release workflow: grant `contents: write` permissions and explicitly pass `GITHUB_TOKEN` and tag name to GitHub Release step

## [0.3.0] - 2025-12-18

### Added
- Authentication error handling:
  - `AuthenticationError` exception raised when token refresh fails
  - Authentication callback: Optional `on_auth_failed` callback parameter for custom reauth flows
- Improved logging
- More unit tests
- Enhanced 401 refresh-token retry logic
- CI/CD pipeline with GitHub Actions
- Pre-commit hooks for automated code quality checks:
  - Black (formatting)
  - isort (import sorting)
  - Ruff (linting and formatting)
  - Pylint (advanced static analysis)
  - mypy (type checking)
- GitHub release automation workflow to publish to PyPI
- Extended and revised API documentation

### Changed
- Improved async client type annotations for better IDE support
- Enhanced error handling in async request methods
- Refactored code to pass all linting/formatting checks (10/10 pylint score)
- Moved example scripts to examples folder
- Renamed example script simple_run.py to simulated_run.py

## [0.2.0] - Earlier

### Added
- async client implementation (for homeassistant integration)
- token refresh
- Methods for endpoints

## [0.1.0] - Initial

### Added
- Basic synchronous client
- Cookie-based JWT authentication
