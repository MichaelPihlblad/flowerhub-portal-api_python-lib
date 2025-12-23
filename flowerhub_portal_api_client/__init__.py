"""flowerhub_client package

Exports the async client API suitable for Home Assistant integrations.
"""

from .async_client import AsyncFlowerhubClient
from .exceptions import ApiError, AuthenticationError
from .types import (
    AgreementState,
    Asset,
    AssetOwner,
    Battery,
    ConsumptionRecord,
    ElectricityAgreement,
    FlowerHubStatus,
    Inverter,
    Invoice,
    InvoiceLine,
    LoginResponse,
    Manufacturer,
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
    "Inverter",
    "Battery",
    "Manufacturer",
    "AgreementState",
    "ElectricityAgreement",
    "ConsumptionRecord",
    "Invoice",
    "InvoiceLine",
]
