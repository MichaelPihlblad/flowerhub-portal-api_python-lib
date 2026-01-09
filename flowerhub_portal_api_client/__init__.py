"""flowerhub_client package

Exports the async client API suitable for Home Assistant integrations.
"""

from .async_client import AsyncFlowerhubClient
from .exceptions import ApiError, AuthenticationError
from .types import (
    AgreementState,
    Asset,
    AssetOwner,
    AssetOwnerProfile,
    Battery,
    ConsumptionRecord,
    ElectricityAgreement,
    FlowerHubStatus,
    InstallerInfo,
    Inverter,
    Invoice,
    InvoiceLine,
    LoginResponse,
    Manufacturer,
    PostalAddress,
    User,
)

__all__ = [
    "AsyncFlowerhubClient",
    "AuthenticationError",
    "ApiError",
    "FlowerHubStatus",
    "User",
    "LoginResponse",
    "Asset",
    "AssetOwner",
    "AssetOwnerProfile",
    "Inverter",
    "Battery",
    "Manufacturer",
    "PostalAddress",
    "InstallerInfo",
    "AgreementState",
    "ElectricityAgreement",
    "ConsumptionRecord",
    "Invoice",
    "InvoiceLine",
]
