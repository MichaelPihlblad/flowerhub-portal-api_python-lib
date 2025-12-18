# FlowerHub API Documentation

This document describes the API endpoints including the complete data structures returned by each endpoint.


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
    "id": <number>,
    "email": <string>,
    "role": <number>,
    "name": <string|null>,
    "distributorId": <number|null>,
    "installerId": <number|null>,
    "assetOwnerId": <number>
  },
  "refreshTokenExpirationDate": <ISO-8601 datetime string>
}
```
Notes: IDs and roles are numeric; emails are standard email strings; date-time values are ISO-8601 UTC.

**Cookies Set:**
- `Authentication`: JWT access token
- `Refresh`: JWT refresh token

### GET /auth/refresh-token
Refresh the access token using the refresh token cookie.

**Response:**
```json
{
  "id": <number>,
  "email": <string>,
  "role": <number>,
  "name": <string|null>,
  "distributorId": <number|null>,
  "installerId": <number|null>,
  "assetOwnerId": <number>
}
```

## Asset Owner Endpoints

### GET /asset-owner/{assetOwnerId}/withAssetId
Get asset owner information including associated asset ID.

**Response:**
```json
{
  "id": <number>,
  "assetId": <number>,
  "firstName": <string>
}
```
### GET /asset-owner/{assetOwnerId}/electricity-agreement
Fetch electricity agreement information for the specified asset owner.

**Response:**
```json
{
  "consumption": {
    "stateCategory": <string>,
    "stateId": <number>,
    "siteId": <number>,
    "startDate": <ISO-8601 datetime string>,
    "terminationDate": <ISO-8601 datetime string|null>
  },
  "production": {
    "stateCategory": <string>,
    "stateId": <number>,
    "siteId": <number>,
    "startDate": <ISO-8601 datetime string>,
    "terminationDate": <ISO-8601 datetime string|null>
  }
}
```
Notes: `stateCategory` is a status label (e.g., "Active")


### GET /asset-owner/{assetOwnerId}/invoice
Fetch invoice information for the specified asset owner.

**Response:**
An array of invoices. Invoices can contain nested `sub_group_invoices` (group invoice + per-site invoices) and detailed line items:

```json
[
  {
    "id": <string>,
    "due_date": <datetime string>,
    "ocr": <string>,
    "invoice_status": <string>,
    "invoice_status_id": <string>,
    "invoice_period": <string>,
    "total_amount": <string>,
    "remaining_amount": <string>,
    "invoice_lines": [
      {"item_id": <string>, "name": <string>, "description": <string|null>, "price": <string>, "volume": <string>, "amount": <string>, "settlements": <array|object>}
    ],
    "invoice_pdf": <string>,
    "invoice_type": <string>,
    "site_id": <string>,
    "sub_group_invoices": [
      {
        "id": <string>,
        "invoice_status": <string>,
        "invoice_period": <string>,
        "total_amount": <string>,
        "invoice_lines": [
          {"item_id": <string>, "name": <string>, "price": <string>, "volume": <string>, "amount": <string>, "settlements": <array|object>}
        ],
        "invoice_pdf": <string>,
        "invoice_type": <string>,
        "site_id": <string>
      }
    ]
  }
]
```
Notes: IDs/ocr/site_id are numeric strings; monetary and volume fields arrive as strings; `invoice_pdf` is a URL string; `invoice_period` names a month/year in natural language.

The async client returns the parsed list under the `invoices` key as `Invoice` dataclasses (with `InvoiceLine` children).

### GET /asset-owner/{assetOwnerId}/consumption
Fetch consumption data for the specified asset owner.

**Response:**
Array of historical readings and calculated values keyed by invoiced month:

```json
[
  {
    "site_id": <string>,
    "valid_from": <date string>,
    "valid_to": <date string|null>,
    "invoiced_month": <date string>,
    "volume": <string|number>,
    "type": <string>,
    "type_id": <string|number>
  },
  {
    "site_id": <string>,
    "valid_from": <date string>,
    "valid_to": <date string|null>,
    "invoiced_month": <date string>,
    "volume": <string|number>,
    "type": <string>,
    "type_id": <string|number>
  }
]
```
Notes: `site_id` is a numerical string; `valid_from/valid_to` and `invoiced_month` are date strings (YYYY-MM-DD); `type` is a label (e.g., "Reading", "Calculated").

## Asset Endpoints

### GET /asset/{assetId}
Get detailed information about a specific asset including hardware specifications and status.

**Response:**
```json
{
  "id": <number>,
  "inverter": {
    "manufacturerId": <number>,
    "manufacturerName": <string>,
    "inverterModelId": <number>,
    "name": <string>,
    "numberOfBatteryStacksSupported": <number>,
    "capacityId": <number>,
    "powerCapacity": <number>
  },
  "battery": {
    "manufacturerId": <number>,
    "manufacturerName": <string>,
    "batteryModelId": <number>,
    "name": <string>,
    "minNumberOfBatteryModules": <number>,
    "maxNumberOfBatteryModules": <number>,
    "capacityId": <number>,
    "energyCapacity": <number>,
    "powerCapacity": <number>
  },
  "fuseSize": <number>,
  "flowerHubStatus": {
    "status": <string>,
    "message": <string>
  },
  "isInstalled": <boolean>
}
```


## System Notification Endpoints

### GET /system-notification/{active-flower}
Fetch a system notification

**Response:**
- 200 OK with an empty body.

### GET /system-notification/{active-zavann}
Fetch a system notification

**Response:**
- 200 OK with an empty body.

## Data Types and Status Values

### FlowerHub Status Values
- `"Connected"`: System is online and functioning
- `"Disconnected"`: System is offline
- Other status values may exist

## Error Handling

- **401 Unauthorized**: Authentication required or token expired (triggers automatic refresh)
- **304 Not Modified**: Resource not changed since last request
- **404 Not Found**: Resource does not exist
- **500 Internal Server Error**: Server error

## Caching

The API uses ETag headers for caching optimization. Clients should include `If-None-Match` headers with subsequent requests to leverage 304 Not Modified responses.
