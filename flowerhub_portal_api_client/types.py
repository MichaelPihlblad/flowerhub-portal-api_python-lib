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
class UptimePieSlice:
    """Pie slice for uptime distribution over a period.

    `name` can be values like "uptime", "downtime", "noData".
    `value` represents seconds in the period.
    """

    name: str
    value: Optional[float]

    @staticmethod
    def calculate_uptime_ratio(slices: List["UptimePieSlice"]) -> Optional[float]:
        """Calculate uptime ratio (percentage) from a list of slices.

        Args:
            slices: List of UptimePieSlice objects.

        Returns:
            Uptime percentage (0-100) or None if no data available.

        Example:
            >>> ratio = UptimePieSlice.calculate_uptime_ratio(result["slices"])
            >>> print(f"Uptime: {ratio:.1f}%")
        """
        if not slices:
            return None

        uptime = downtime = no_data = 0.0
        for slice_item in slices:
            if slice_item.value is None:
                continue
            if slice_item.name == "uptime":
                uptime = slice_item.value
            elif slice_item.name == "downtime":
                downtime = slice_item.value
            elif slice_item.name == "noData":
                no_data = slice_item.value

        total = uptime + downtime + no_data
        if total == 0:
            return None
        return (uptime / total) * 100.0

    @staticmethod
    def get_slice_value(slices: List["UptimePieSlice"], name: str) -> Optional[float]:
        """Get the value (seconds) for a specific slice name.

        Args:
            slices: List of UptimePieSlice objects.
            name: Slice name ("uptime", "downtime", or "noData").

        Returns:
            Value in seconds or None if not found.

        Example:
            >>> uptime_sec = UptimePieSlice.get_slice_value(result["slices"], "uptime")
        """
        for slice_item in slices:
            if slice_item.name == name:
                return slice_item.value
        return None


@dataclass
class Revenue:
    """Revenue summary for the last invoice of an asset.

    Mirrors GET /asset/{assetId}/revenue.
    """

    id: Optional[int] = None
    minAvailablePower: Optional[float] = None
    compensation: Optional[float] = None
    compensationPerKW: Optional[float] = None


class AssetIdResult(TypedDict):
    """Result for asset ID discovery.

    Fields:
    - status_code: HTTP status code
    - asset_id: Parsed integer asset id or None
    - error: Error message when not raising, else None
    """

    status_code: int
    asset_id: Optional[int]
    error: Optional[str]


class AssetFetchResult(TypedDict):
    """Result for asset fetch.

    Fields:
    - status_code: HTTP status code
    - asset_info: Raw asset payload dict or None
    - flowerhub_status: Parsed `FlowerHubStatus` or None
    - error: Error message when not raising, else None
    """

    status_code: int
    asset_info: Optional[Dict[str, Any]]
    flowerhub_status: Optional[FlowerHubStatus]
    error: Optional[str]


class AgreementResult(TypedDict):
    """Result for electricity agreement fetch.

    Fields:
    - status_code: HTTP status code
    - agreement: Parsed `ElectricityAgreement` or None
    - json: Raw response payload
    - text: Raw response text
    - error: Error message when not raising, else None
    """

    status_code: int
    agreement: Optional[ElectricityAgreement]
    json: Any
    text: str
    error: Optional[str]


class InvoicesResult(TypedDict):
    """Result for invoices fetch.

    Fields:
    - status_code: HTTP status code
    - invoices: List of parsed `Invoice` or None
    - json: Raw response payload
    - text: Raw response text
    - error: Error message when not raising, else None
    """

    status_code: int
    invoices: Optional[List[Invoice]]
    json: Any
    text: str
    error: Optional[str]


class ConsumptionResult(TypedDict):
    """Result for consumption fetch.

    Fields:
    - status_code: HTTP status code
    - consumption: List of parsed `ConsumptionRecord` or None
    - json: Raw response payload
    - text: Raw response text
    - error: Error message when not raising, else None
    """

    status_code: int
    consumption: Optional[List[ConsumptionRecord]]
    json: Any
    text: str
    error: Optional[str]


class UptimeAvailableMonthsResult(TypedDict):
    """Result for uptime available months fetch.

    Fields:
    - status_code: HTTP status code
    - months: List of parsed `UptimeMonth` or None
    - json: Raw response payload
    - text: Raw response text
    - error: Error message when not raising, else None
    """

    status_code: int
    months: Optional[List[UptimeMonth]]
    json: Any
    text: str
    error: Optional[str]


class UptimeHistoryResult(TypedDict):
    """Result for uptime monthly ratio history fetch.

    Fields:
    - status_code: HTTP status code
    - history: List of parsed `UptimeHistoryEntry` or None
    - json: Raw response payload
    - text: Raw response text
    - error: Error message when not raising, else None
    """

    status_code: int
    history: Optional[List[UptimeHistoryEntry]]
    json: Any
    text: str
    error: Optional[str]


class UptimePieResult(TypedDict):
    """Result for uptime pie-chart endpoint.

    Fields:
    - status_code: HTTP status code
    - slices: List of parsed `UptimePieSlice` or None
    - uptime_ratio: Derived uptime percentage (0-100) or None
    - json: Raw response payload
    - text: Raw response text
    - error: Error message when not raising, else None
    """

    status_code: int
    slices: Optional[List[UptimePieSlice]]
    uptime_ratio: Optional[float]
    json: Any
    text: str
    error: Optional[str]


class RevenueResult(TypedDict):
    """Result for asset revenue fetch.

    Fields:
    - status_code: HTTP status code
    - revenue: Parsed `Revenue` or None
    - json: Raw response payload
    - text: Raw response text
    - error: Error message when not raising, else None
    """

    status_code: int
    revenue: Optional[Revenue]
    json: Any
    text: str
    error: Optional[str]


class ProfileResult(TypedDict):
    """Result for asset owner profile fetch.

    Fields:
    - status_code: HTTP status code
    - profile: Parsed `AssetOwnerProfile` or None
    - json: Raw response payload
    - text: Raw response text
    - error: Error message when not raising, else None
    """

    status_code: int
    profile: Optional[AssetOwnerProfile]
    json: Any
    text: str
    error: Optional[str]


class AssetOwnerDetailsResult(TypedDict):
    """Result for asset owner details fetch.

    Fields:
    - status_code: HTTP status code
    - details: Parsed `AssetOwnerDetails` or None
    - json: Raw response payload
    - text: Raw response text
    - error: Error message when not raising, else None
    """

    status_code: int
    details: Optional[AssetOwnerDetails]
    json: Any
    text: str
    error: Optional[str]


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
    "UptimePieSlice",
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
