# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).


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
