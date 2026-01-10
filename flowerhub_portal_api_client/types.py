"""Data models and typed results for the Flowerhub client."""

from __future__ import annotations

import datetime
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, TypedDict


@dataclass
class User:
    id: int
    email: str
    role: int
    name: Optional[str]
    distributorId: Optional[int]
    installerId: Optional[int]
    assetOwnerId: int


@dataclass
class LoginResponse:
    user: User
    refreshTokenExpirationDate: str


@dataclass
class FlowerHubStatus:
    status: Optional[str] = None
    message: Optional[str] = None
    updated_at: Optional[datetime.datetime] = None

    @property
    def updated_timestamp(self) -> Optional[datetime.datetime]:
        return self.updated_at

    def age_seconds(self) -> Optional[float]:
        if not self.updated_at:
            return None
        return (
            datetime.datetime.now(datetime.timezone.utc) - self.updated_at
        ).total_seconds()


@dataclass
class Manufacturer:
    manufacturerId: int
    manufacturerName: str


@dataclass
class Inverter:
    manufacturerId: int
    manufacturerName: str
    inverterModelId: int
    name: str
    numberOfBatteryStacksSupported: int
    capacityId: int
    powerCapacity: int


@dataclass
class Battery:
    manufacturerId: int
    manufacturerName: str
    batteryModelId: int
    name: str
    minNumberOfBatteryModules: int
    maxNumberOfBatteryModules: int
    capacityId: int
    energyCapacity: int
    powerCapacity: int


@dataclass
class Asset:
    id: int
    inverter: Inverter
    battery: Battery
    fuseSize: int
    flowerHubStatus: FlowerHubStatus
    isInstalled: bool


@dataclass
class AssetOwner:
    id: int
    assetId: int
    firstName: str


@dataclass
class SimpleInstaller:
    """Minimal installer info (id and name only)."""

    id: Optional[int] = None
    name: Optional[str] = None


@dataclass
class SimpleDistributor:
    """Minimal distributor info (id and name only)."""

    id: Optional[int] = None
    name: Optional[str] = None


@dataclass
class AssetModel:
    """Asset model with manufacturer info."""

    id: Optional[int] = None
    name: Optional[str] = None
    manufacturer: Optional[str] = None


@dataclass
class AssetInfo:
    """Asset information with serial number and model."""

    id: Optional[int] = None
    serialNumber: Optional[str] = None
    assetModel: AssetModel = field(default_factory=AssetModel)


@dataclass
class Compensation:
    """Compensation status and message."""

    status: Optional[str] = None
    message: Optional[str] = None


@dataclass
class AssetOwnerDetails:
    """Complete asset owner details.

    Mirrors the response of GET /asset-owner/{assetOwnerId}.
    """

    id: int
    firstName: Optional[str] = None
    lastName: Optional[str] = None
    installer: SimpleInstaller = field(default_factory=SimpleInstaller)
    distributor: SimpleDistributor = field(default_factory=SimpleDistributor)
    asset: AssetInfo = field(default_factory=AssetInfo)
    compensation: Compensation = field(default_factory=Compensation)
    bessCompensationStartDate: Optional[str] = None


@dataclass
class PostalAddress:
    street: Optional[str] = None
    postalCode: Optional[str] = None
    city: Optional[str] = None


@dataclass
class InstallerInfo:
    id: Optional[int] = None
    name: Optional[str] = None
    address: PostalAddress = field(default_factory=PostalAddress)


@dataclass
class AssetOwnerProfile:
    """Profile details for an asset owner.

    Mirrors the response of GET /asset-owner/{assetOwnerId}/profile.
    """

    id: int
    firstName: Optional[str] = None
    lastName: Optional[str] = None
    mainEmail: Optional[str] = None
    contactEmail: Optional[str] = None
    phone: Optional[str] = None
    address: PostalAddress = field(default_factory=PostalAddress)
    accountStatus: Optional[str] = None
    installer: InstallerInfo = field(default_factory=InstallerInfo)


@dataclass
class AgreementState:
    stateCategory: Optional[str] = None
    stateId: Optional[int] = None
    siteId: Optional[int] = None
    startDate: Optional[str] = None
    terminationDate: Optional[str] = None


@dataclass
class ElectricityAgreement:
    consumption: Optional[AgreementState] = None
    production: Optional[AgreementState] = None


@dataclass
class InvoiceLine:
    item_id: str
    name: str
    description: str
    price: str
    volume: str
    amount: str
    settlements: Any


@dataclass
class Invoice:
    id: str
    due_date: Optional[str]
    ocr: Optional[str]
    invoice_status: Optional[str]
    invoice_has_settlements: Optional[str]
    invoice_status_id: Optional[str]
    invoice_create_date: Optional[str]
    invoiced_month: Optional[str]
    invoice_period: Optional[str]
    invoice_date: Optional[str]
    total_amount: Optional[str]
    remaining_amount: Optional[str]
    invoice_lines: List[InvoiceLine] = field(default_factory=list)
    invoice_pdf: Optional[str] = None
    invoice_type_id: Optional[str] = None
    invoice_type: Optional[str] = None
    claim_status: Optional[str] = None
    claim_reminder_pdf: Optional[str] = None
    site_id: Optional[str] = None
    sub_group_invoices: List["Invoice"] = field(default_factory=list)
    current_payment_type_id: Optional[str] = None
    current_payment_type_name: Optional[str] = None


@dataclass
class ConsumptionRecord:
    site_id: str
    valid_from: str
    valid_to: Optional[str]
    invoiced_month: str
    volume: Optional[float]
    type: str
    type_id: Optional[int]


@dataclass
class UptimeMonth:
    """Available uptime month item.

    Represents a single month entry with machine-readable value and human label.
    """

    value: str
    label: str


@dataclass
class UptimeHistoryEntry:
    """Monthly uptime ratio entry.

    Represents uptime ratio (percentage) for a given month.
    """

    date: str
    uptime: Optional[float]


@dataclass
class Revenue:
    """Revenue summary for the last invoice of an asset.

    Mirrors GET /asset/{assetId}/revenue.
    """

    id: Optional[int] = None
    minAvailablePower: Optional[float] = None
    compensation: Optional[float] = None
    compensationPerKW: Optional[float] = None


class StandardResult(TypedDict):
    """Base result with common fields returned by most endpoints.

    This serves as a structural baseline to make responses more consistent
    without removing endpoint-specific parsed data.

    Fields:
    - status_code: HTTP status code
    - json: Raw response payload
    - text: Raw response text
    - error: Error message when not raising, else None
    """

    status_code: int
    json: Any
    text: str
    error: Optional[str]


class AssetIdResult(StandardResult):
    """Result for asset ID discovery.

    Fields:
    - status_code: HTTP status code
    - asset_id: Parsed integer asset id or None
    - json: Raw response payload
    - text: Raw response text
    - error: Error message when not raising, else None
    """

    asset_id: Optional[int]


class AssetFetchResult(StandardResult):
    """Result for asset fetch.

    Fields:
    - status_code: HTTP status code
    - asset_info: Raw asset payload dict or None
    - flowerhub_status: Parsed `FlowerHubStatus` or None
    - json: Raw response payload
    - text: Raw response text
    - error: Error message when not raising, else None
    """

    asset_info: Optional[Dict[str, Any]]
    flowerhub_status: Optional[FlowerHubStatus]


class AgreementResult(StandardResult):
    """Result for electricity agreement fetch.

    Fields:
    - status_code: HTTP status code
    - agreement: Parsed `ElectricityAgreement` or None
    - json: Raw response payload
    - text: Raw response text
    - error: Error message when not raising, else None
    """

    agreement: Optional[ElectricityAgreement]


class InvoicesResult(StandardResult):
    """Result for invoices fetch.

    Fields:
    - status_code: HTTP status code
    - invoices: List of parsed `Invoice` or None
    - json: Raw response payload
    - text: Raw response text
    - error: Error message when not raising, else None
    """

    invoices: Optional[List[Invoice]]


class ConsumptionResult(StandardResult):
    """Result for consumption fetch.

    Fields:
    - status_code: HTTP status code
    - consumption: List of parsed `ConsumptionRecord` or None
    - json: Raw response payload
    - text: Raw response text
    - error: Error message when not raising, else None
    """

    consumption: Optional[List[ConsumptionRecord]]


class UptimeAvailableMonthsResult(StandardResult):
    """Result for uptime available months fetch.

    Fields:
    - status_code: HTTP status code
    - months: List of parsed `UptimeMonth` or None
    - json: Raw response payload
    - text: Raw response text
    - error: Error message when not raising, else None
    """

    months: Optional[List[UptimeMonth]]


class UptimeHistoryResult(StandardResult):
    """Result for uptime monthly ratio history fetch.

    Fields:
    - status_code: HTTP status code
    - history: List of parsed `UptimeHistoryEntry` or None
    - json: Raw response payload
    - text: Raw response text
    - error: Error message when not raising, else None
    """

    history: Optional[List[UptimeHistoryEntry]]


class UptimePieResult(StandardResult):
    """Result for uptime pie-chart endpoint.

    Fields:
    - status_code: HTTP status code
    - uptime: Uptime duration in seconds, or None
    - downtime: Downtime duration in seconds, or None
    - noData: No-data duration in seconds, or None
    - uptime_ratio: Derived uptime percentage (0-100) or None
    - json: Raw response payload
    - text: Raw response text
    - error: Error message when not raising, else None
    """

    uptime: Optional[float]
    downtime: Optional[float]
    noData: Optional[float]
    uptime_ratio: Optional[float]


class RevenueResult(StandardResult):
    """Result for asset revenue fetch.

    Fields:
    - status_code: HTTP status code
    - revenue: Parsed `Revenue` or None
    - json: Raw response payload
    - text: Raw response text
    - error: Error message when not raising, else None
    """

    revenue: Optional[Revenue]


class ProfileResult(StandardResult):
    """Result for asset owner profile fetch.

    Fields:
    - status_code: HTTP status code
    - profile: Parsed `AssetOwnerProfile` or None
    - json: Raw response payload
    - text: Raw response text
    - error: Error message when not raising, else None
    """

    profile: Optional[AssetOwnerProfile]


class AssetOwnerDetailsResult(StandardResult):
    """Result for asset owner details fetch.

    Fields:
    - status_code: HTTP status code
    - details: Parsed `AssetOwnerDetails` or None
    - json: Raw response payload
    - text: Raw response text
    - error: Error message when not raising, else None
    """

    details: Optional[AssetOwnerDetails]


# Type alias for system notification endpoint which returns only the standard envelope
SystemNotificationResult = StandardResult


__all__ = [
    "User",
    "LoginResponse",
    "FlowerHubStatus",
    "Manufacturer",
    "Inverter",
    "Battery",
    "Asset",
    "AssetOwner",
    "AgreementState",
    "ElectricityAgreement",
    "InvoiceLine",
    "Invoice",
    "ConsumptionRecord",
    "UptimeMonth",
    "UptimeHistoryEntry",
    "Revenue",
    "PostalAddress",
    "InstallerInfo",
    "AssetOwnerProfile",
    "SimpleInstaller",
    "SimpleDistributor",
    "AssetModel",
    "AssetInfo",
    "Compensation",
    "AssetOwnerDetails",
    "AssetIdResult",
    "AssetFetchResult",
    "AgreementResult",
    "InvoicesResult",
    "ConsumptionResult",
    "ProfileResult",
    "AssetOwnerDetailsResult",
    "UptimeAvailableMonthsResult",
    "UptimeHistoryResult",
    "UptimePieResult",
    "RevenueResult",
]
