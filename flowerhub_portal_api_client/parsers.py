"""Parsing and validation helpers for the Flowerhub client."""

from __future__ import annotations

import datetime
import logging
from typing import Any, Dict, List, Optional, Tuple

from .exceptions import ApiError
from .types import (
    AgreementState,
    AssetOwnerProfile,
    ConsumptionRecord,
    ElectricityAgreement,
    FlowerHubStatus,
    InstallerInfo,
    Invoice,
    InvoiceLine,
    PostalAddress,
)

_LOGGER = logging.getLogger(__name__)


def safe_int(value: Any) -> Optional[int]:
    try:
        return int(value)
    except (ValueError, TypeError):
        return None


def safe_float(value: Any) -> Optional[float]:
    try:
        return float(value)
    except (ValueError, TypeError):
        return None


def parse_agreement_state(payload: Dict[str, Any]) -> AgreementState:
    return AgreementState(
        stateCategory=payload.get("stateCategory"),
        stateId=safe_int(payload.get("stateId")),
        siteId=safe_int(payload.get("siteId")),
        startDate=payload.get("startDate"),
        terminationDate=payload.get("terminationDate"),
    )


def parse_electricity_agreement(data: Any) -> Optional[ElectricityAgreement]:
    if not isinstance(data, dict):
        return None
    consumption = data.get("consumption")
    production = data.get("production")
    return ElectricityAgreement(
        consumption=(
            parse_agreement_state(consumption)
            if isinstance(consumption, dict)
            else None
        ),
        production=(
            parse_agreement_state(production) if isinstance(production, dict) else None
        ),
    )


def parse_invoice_line(payload: Dict[str, Any]) -> InvoiceLine:
    return InvoiceLine(
        item_id=str(payload.get("item_id", "")),
        name=payload.get("name", ""),
        description=payload.get("description", ""),
        price=str(payload.get("price", "")),
        volume=str(payload.get("volume", "")),
        amount=str(payload.get("amount", "")),
        settlements=payload.get("settlements", []),
    )


def parse_invoice(payload: Dict[str, Any]) -> Invoice:
    lines: List[InvoiceLine] = []
    for entry in payload.get("invoice_lines", []):
        if isinstance(entry, dict):
            lines.append(parse_invoice_line(entry))

    sub_invoices: List[Invoice] = []
    for sub in payload.get("sub_group_invoices", []):
        if isinstance(sub, dict):
            sub_invoices.append(parse_invoice(sub))

    return Invoice(
        id=str(payload.get("id", "")),
        due_date=payload.get("due_date"),
        ocr=payload.get("ocr"),
        invoice_status=payload.get("invoice_status"),
        invoice_has_settlements=payload.get("invoice_has_settlements"),
        invoice_status_id=payload.get("invoice_status_id"),
        invoice_create_date=payload.get("invoice_create_date"),
        invoiced_month=payload.get("invoiced_month"),
        invoice_period=payload.get("invoice_period"),
        invoice_date=payload.get("invoice_date"),
        total_amount=payload.get("total_amount"),
        remaining_amount=payload.get("remaining_amount"),
        invoice_lines=lines,
        invoice_pdf=payload.get("invoice_pdf"),
        invoice_type_id=payload.get("invoice_type_id"),
        invoice_type=payload.get("invoice_type"),
        claim_status=payload.get("claim_status"),
        claim_reminder_pdf=payload.get("claim_reminder_pdf"),
        site_id=payload.get("site_id"),
        sub_group_invoices=sub_invoices,
        current_payment_type_id=payload.get("current_payment_type_id"),
        current_payment_type_name=payload.get("current_payment_type_name"),
    )


def parse_invoices(data: Any) -> Optional[List[Invoice]]:
    if not isinstance(data, list):
        return None
    invoices: List[Invoice] = []
    for item in data:
        if isinstance(item, dict):
            invoices.append(parse_invoice(item))
    return invoices


def parse_consumption(data: Any) -> Optional[List[ConsumptionRecord]]:
    if not isinstance(data, list):
        return None
    records: List[ConsumptionRecord] = []
    for item in data:
        if not isinstance(item, dict):
            continue
        records.append(
            ConsumptionRecord(
                site_id=str(item.get("site_id", "")),
                valid_from=item.get("valid_from", ""),
                valid_to=item.get("valid_to") or None,
                invoiced_month=item.get("invoiced_month", ""),
                volume=safe_float(item.get("volume")),
                type=item.get("type", ""),
                type_id=safe_int(item.get("type_id")),
            )
        )
    return records


def ensure_dict(
    data: Any,
    *,
    context: str,
    status_code: int,
    url: str,
    raise_on_error: bool,
) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    if isinstance(data, dict):
        return data, None
    msg = f"Unexpected response format for {context} (expected dict)"
    _LOGGER.error(msg)
    if raise_on_error:
        raise ApiError(msg, status_code=status_code, url=url, payload=data)
    return None, msg


def ensure_list(
    data: Any,
    *,
    context: str,
    status_code: int,
    url: str,
    raise_on_error: bool,
) -> Tuple[Optional[List[Any]], Optional[str]]:
    if isinstance(data, list):
        return data, None
    msg = f"Unexpected response type for {context} (expected list)"
    _LOGGER.error(msg)
    if raise_on_error:
        raise ApiError(msg, status_code=status_code, url=url, payload=data)
    return None, msg


def require_field(
    data: Dict[str, Any],
    field_name: str,
    *,
    status_code: int,
    url: str,
    raise_on_error: bool,
) -> Tuple[Optional[Any], Optional[str]]:
    if field_name in data:
        return data[field_name], None
    msg = f"Response missing {field_name} field"
    _LOGGER.error(msg)
    if raise_on_error:
        raise ApiError(msg, status_code=status_code, url=url, payload=data)
    return None, msg


def parse_asset_id_value(
    value: Any,
    *,
    status_code: int,
    url: str,
    payload: Any,
    raise_on_error: bool,
) -> Tuple[Optional[int], Optional[str]]:
    try:
        return int(value), None
    except (ValueError, TypeError) as err:
        msg = f"Failed to parse assetId from response: {err}"
        _LOGGER.error(msg)
        if raise_on_error:
            raise ApiError(
                msg, status_code=status_code, url=url, payload=payload
            ) from err
        return None, msg


def validate_flowerhub_status(
    fhs: Any,
    *,
    status_code: int,
    url: str,
    payload: Any,
    raise_on_error: bool,
) -> Tuple[Optional[FlowerHubStatus], Optional[str]]:
    if not isinstance(fhs, dict):
        msg = "Asset response missing flowerHubStatus"
        _LOGGER.error(msg)
        if raise_on_error:
            raise ApiError(msg, status_code=status_code, url=url, payload=payload)
        return None, msg
    status_val = fhs.get("status")
    if status_val is None or (isinstance(status_val, str) and status_val.strip() == ""):
        msg = "flowerHubStatus.status is required and must be non-empty"
        _LOGGER.error(msg)
        if raise_on_error:
            raise ApiError(msg, status_code=status_code, url=url, payload=payload)
        return None, msg
    now = datetime.datetime.now(datetime.timezone.utc)
    return (
        FlowerHubStatus(
            status=str(status_val), message=fhs.get("message"), updated_at=now
        ),
        None,
    )


def parse_postal_address(payload: Any) -> PostalAddress:
    if not isinstance(payload, dict):
        return PostalAddress()
    return PostalAddress(
        street=payload.get("street"),
        postalCode=payload.get("postalCode"),
        city=payload.get("city"),
    )


def parse_installer_info(payload: Any) -> InstallerInfo:
    if not isinstance(payload, dict):
        return InstallerInfo()
    return InstallerInfo(
        id=safe_int(payload.get("id")),
        name=payload.get("name"),
        address=parse_postal_address(payload.get("address")),
    )


def parse_asset_owner_profile(data: Any) -> Optional[AssetOwnerProfile]:
    """Parse asset owner profile dict into AssetOwnerProfile dataclass.

    Returns None if input is not a dict.
    """
    if not isinstance(data, dict):
        return None
    ao_id = safe_int(data.get("id"))
    if ao_id is None:
        return None
    return AssetOwnerProfile(
        id=ao_id,
        firstName=data.get("firstName"),
        lastName=data.get("lastName"),
        mainEmail=data.get("mainEmail"),
        contactEmail=data.get("contactEmail"),
        phone=data.get("phone"),
        address=parse_postal_address(data.get("address")),
        accountStatus=data.get("accountStatus"),
        installer=parse_installer_info(data.get("installer")),
    )


__all__ = [
    "safe_int",
    "safe_float",
    "parse_agreement_state",
    "parse_electricity_agreement",
    "parse_invoice_line",
    "parse_invoice",
    "parse_invoices",
    "parse_consumption",
    "ensure_dict",
    "ensure_list",
    "require_field",
    "parse_asset_id_value",
    "validate_flowerhub_status",
    "parse_postal_address",
    "parse_installer_info",
    "parse_asset_owner_profile",
]
