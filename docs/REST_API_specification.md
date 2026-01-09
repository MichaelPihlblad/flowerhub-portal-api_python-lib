# FlowerHub API Documentation

This document describes the API endpoints including the complete data structures returned by each endpoint.


## Base URL
```
https://api.portal.flowerhub.se
```

## Authentication

All API requests (except login) require authentication via HTTP cookies set during login.

### Cookie Handling
- The API authenticates via HTTP cookies (`Authentication` and `Refresh`) set by the `POST /auth/login` response using `Set-Cookie` headers.
- Clients should use an HTTP client that maintains a cookie jar (e.g., `requests.Session` or `aiohttp.ClientSession`) rather than manually copying cookie values.
- Cookies are set with `HttpOnly`, `Secure`, and `SameSite` attributes; `HttpOnly` means the cookie cannot be read by scripts and should be sent automatically by the HTTP client.
- For cross-site scenarios, servers may require the `Origin: https://portal.flowerhub.se` header and `credentials` enabled (cookie-based requests).

curl example:
```bash
curl \
  -H "Origin: https://portal.flowerhub.se" \
  -H "Cookie: Authentication=<ACCESS_TOKEN>; Refresh=<REFRESH_TOKEN>" \
  "https://api.portal.flowerhub.se/asset-owner/{assetOwnerId}/withAssetId"
```
Notes

- The `Refresh` cookie is generally `HttpOnly` and used by the server to mint a new access token; clients should not send it manually beyond relying on the cookie jar.
- A `401 Unauthorized` may trigger a refresh flow (the client can re-call `/auth/refresh-token`);

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
Notes: IDs and roles are numeric; date-time values are ISO-8601 UTC.

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

### GET /asset-owner/{assetOwnerId}
Get complete asset owner details including installer, distributor, asset, and compensation information.

**Response:**
```json
{
  "id": <number>,
  "firstName": <string>,
  "lastName": <string>,
  "installer": {
    "id": <number>,
    "name": <string>
  },
  "distributor": {
    "id": <number>,
    "name": <string>
  },
  "asset": {
    "id": <number>,
    "serialNumber": <string>,
    "assetModel": {
      "id": <number>,
      "name": <string>,
      "manufacturer": <string>
    }
  },
  "compensation": {
    "status": <string>,
    "message": <string>
  },
  "bessCompensationStartDate": <string>
}
```
Notes: `compensation.status` is typically "Qualified"; dates are in ISO format (YYYY-MM-DD).

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
### GET /asset-owner/{assetOwnerId}/profile
Fetch profile details for the specified asset owner.

**Response:**
```json
{
  "id": <number>,
  "firstName": <string>,
  "lastName": <string>,
  "mainEmail": <string>,
  "contactEmail": <string|null>,
  "phone": <string>,
  "address": {
    "street": <string>,
    "postalCode": <string>,
    "city": <string>
  },
  "accountStatus": <string>,
  "installer": {
    "id": <number>,
    "name": <string>,
    "address": {
      "street": <string>,
      "postalCode": <string>,
      "city": <string>
    }
  }
}
```
Notes: `id` equals the asset owner id; typical `accountStatus` is "Verified".

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

### GET /asset-uptime/available-months/{assetId}
List months for which uptime info is available for the asset.

**Response:**
An array of objects, one per available month:

```json
[
  {"value": <string>, "label": <string>}
]
```
Notes: `value` is in `YYYY-MM` format (e.g., "2025-03"); `label` is a human-readable month name and year (e.g., "March 2025"). Uptime measurement appears to start around March 2025, and the last element is the current month.

### GET /asset-uptime/bar-chart/history/{assetId}
List monthly uptime ratios (percent) per month for the asset.

**Response:**
An array of objects:

```json
[
  {"date": <string>, "uptime": <number>}
]
```
Notes: `date` is in `YYYY-MM` format; `uptime` is a percentage (0–100). Values may vary by month; examples include values like 100, 99, 92.

### GET /asset-uptime/pie-chart/{assetId}?period=YYYY-MM
Get uptime distribution (in seconds) for the specified period.

**Response:**
An array of objects:

```json
[
  {"name": "uptime", "value": <number>},
  {"name": "downtime", "value": <number>},
  {"name": "noData", "value": <number>}
]
```
Notes: `period` is required and must be in `YYYY-MM` format. `value` is measured in seconds for each category.


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
