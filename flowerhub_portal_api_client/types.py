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
    "AssetIdResult",
    "AssetFetchResult",
    "AgreementResult",
    "InvoicesResult",
    "ConsumptionResult",
]
