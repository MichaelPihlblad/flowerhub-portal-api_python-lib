# FlowerHub API Documentation

This document describes the API endpoints used by the FlowerHub Python client library, including the complete data structures returned by each endpoint.

The Python client library provides typed dataclasses for all API response data. See the [dataclasses](#dataclasses) section below for the complete type definitions.

## Base URL
```
https://api.portal.flowerhub.se
```

## Authentication

All API requests (except login) require authentication via HTTP cookies set during login.

### POST /auth/login
Authenticate a user and receive JWT tokens.

**Request Body:**
```json
{
  "username": "string",
  "password": "string"
}
```

**Response:**
```json
{
  "user": {
    "id": 123,
    "email": "user@example.com",
    "role": 100,
    "name": null,
    "distributorId": null,
    "installerId": null,
    "assetOwnerId": 456
  },
  "refreshTokenExpirationDate": "2026-01-12T14:50:02.866Z"
}
```

**Cookies Set:**
- `Authentication`: JWT access token
- `Refresh`: JWT refresh token

### GET /auth/refresh-token
Refresh the access token using the refresh token cookie.

**Response:**
```json
{
  "ok": true
}
```

## Asset Owner Endpoints

### GET /asset-owner/{assetOwnerId}/withAssetId
Get asset owner information including associated asset ID.

**Response:**
```json
{
  "id": 456,
  "assetId": 789,
  "firstName": "John"
}
```

## Asset Endpoints

### GET /asset/{assetId}
Get detailed information about a specific asset including hardware specifications and status.

**Response:**
```json
{
  "id": 789,
  "inverter": {
    "manufacturerId": 1,
    "manufacturerName": "Huawei",
    "inverterModelId": 1,
    "name": "SUN2000 M1",
    "numberOfBatteryStacksSupported": 2,
    "capacityId": 6,
    "powerCapacity": 10
  },
  "battery": {
    "manufacturerId": 1,
    "manufacturerName": "Huawei",
    "batteryModelId": 1,
    "name": "LUNA2000 S0",
    "minNumberOfBatteryModules": 1,
    "maxNumberOfBatteryModules": 3,
    "capacityId": 3,
    "energyCapacity": 15,
    "powerCapacity": 5
  },
  "fuseSize": 0,
  "flowerHubStatus": {
    "status": "Connected",
    "message": "InverterDongleFoundAndComponentsAreRunning"
  },
  "isInstalled": true
}
```

## Data Types and Status Values

### FlowerHub Status Values
- `"Connected"`: System is online and functioning
- `"Disconnected"`: System is offline
- Other status values may exist

## Error Handling

- **401 Unauthorized**: Authentication required or token expired (triggers automatic refresh)
- **304 Not Modified**: Resource not changed since last request (ETag caching)
- **404 Not Found**: Resource does not exist
- **500 Internal Server Error**: Server error

## Caching

The API uses ETag headers for caching optimization. Clients should include `If-None-Match` headers with subsequent requests to leverage 304 Not Modified responses.

## Python Dataclasses

The `flowerhub_client` library provides typed dataclasses for all API response data structures. Import them from the main package:

```python
from flowerhub_portal_api_client import (
    User, LoginResponse, Asset, AssetOwner,
    FlowerHubStatus, Inverter, Battery, Manufacturer
)
```

### Available Dataclasses

- `User`: User account information
- `LoginResponse`: Complete login endpoint response
- `Asset`: Complete asset with inverter, battery, and status
- `AssetOwner`: Asset owner basic information
- `FlowerHubStatus`: System connection status
- `Inverter`: Inverter specifications
- `Battery`: Battery specifications
- `Manufacturer`: Manufacturer information

All dataclasses include proper type hints and documentation. Use these types in your applications for better IDE support, type checking, and code documentation.