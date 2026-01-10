import datetime

import pytest

from flowerhub_portal_api_client.exceptions import ApiError
from flowerhub_portal_api_client.parsers import (
    ensure_dict,
    ensure_list,
    parse_asset_id_value,
    parse_asset_model,
    parse_asset_owner_details,
    parse_asset_owner_profile,
    parse_compensation,
    parse_installer_info,
    parse_postal_address,
    parse_revenue,
    parse_simple_distributor,
    parse_simple_installer,
    parse_uptime_available_months,
    parse_uptime_history,
    require_field,
    validate_flowerhub_status,
)


def test_ensure_dict_non_dict_no_raise():
    data, err = ensure_dict(
        "oops", context="ctx", status_code=400, url="/ctx", raise_on_error=False
    )
    assert data is None
    assert "expected dict" in err


def test_ensure_dict_non_dict_raises():
    with pytest.raises(ApiError):
        ensure_dict(
            "oops", context="ctx", status_code=400, url="/ctx", raise_on_error=True
        )


def test_ensure_list_non_list_no_raise():
    data, err = ensure_list(
        "oops", context="ctx", status_code=400, url="/ctx", raise_on_error=False
    )
    assert data is None
    assert "expected list" in err


def test_ensure_list_non_list_raises():
    with pytest.raises(ApiError):
        ensure_list(
            "oops", context="ctx", status_code=400, url="/ctx", raise_on_error=True
        )


def test_require_field_missing_no_raise():
    value, err = require_field(
        {"foo": 1},
        "bar",
        status_code=400,
        url="/ctx",
        raise_on_error=False,
    )
    assert value is None
    assert "missing bar" in err


def test_require_field_missing_raises():
    with pytest.raises(ApiError):
        require_field(
            {"foo": 1}, "bar", status_code=400, url="/ctx", raise_on_error=True
        )


def test_parse_asset_id_value_invalid_no_raise():
    value, err = parse_asset_id_value(
        "abc",
        status_code=400,
        url="/ctx",
        payload={"assetId": "abc"},
        raise_on_error=False,
    )
    assert value is None
    assert "Failed to parse assetId" in err


def test_validate_flowerhub_status_non_dict_raises():
    with pytest.raises(ApiError):
        validate_flowerhub_status(
            "bad", status_code=400, url="/ctx", payload={}, raise_on_error=True
        )


def test_validate_flowerhub_status_missing_status_no_raise():
    status, err = validate_flowerhub_status(
        {"message": "hi"},
        status_code=400,
        url="/ctx",
        payload={},
        raise_on_error=False,
    )
    assert status is None
    assert "status is required" in err


def test_validate_flowerhub_status_success():
    status, err = validate_flowerhub_status(
        {"status": "ok", "message": "hi"},
        status_code=200,
        url="/ctx",
        payload={},
        raise_on_error=True,
    )
    assert err is None
    assert status is not None
    assert status.status == "ok"
    assert isinstance(status.updated_at, datetime.datetime)


def test_parse_postal_address_empty_and_basic():
    assert parse_postal_address("bad") == parse_postal_address(None)
    addr = parse_postal_address({"street": "s", "postalCode": "p", "city": "c"})
    assert addr.street == "s"
    assert addr.postalCode == "p"
    assert addr.city == "c"


def test_parse_installer_info_variants():
    empty = parse_installer_info("bad")
    assert empty.id is None
    populated = parse_installer_info(
        {
            "id": "5",
            "name": "n",
            "address": {"street": "s", "postalCode": "p", "city": "c"},
        }
    )
    assert populated.id == 5
    assert populated.name == "n"
    assert populated.address.street == "s"


def test_parse_asset_owner_profile_missing_and_success():
    assert parse_asset_owner_profile("bad") is None
    assert parse_asset_owner_profile({"id": None}) is None
    profile = parse_asset_owner_profile(
        {
            "id": "10",
            "firstName": "f",
            "lastName": "l",
            "mainEmail": "m",
            "contactEmail": "c",
            "phone": "p",
            "address": {"street": "s"},
            "accountStatus": "ok",
            "installer": {"id": "2", "name": "inst"},
        }
    )
    assert profile is not None
    assert profile.id == 10
    assert profile.installer.id == 2


def test_simple_helpers_and_models():
    assert parse_simple_installer("bad").id is None
    assert parse_simple_distributor("bad").id is None
    model = parse_asset_model({"id": "3", "name": "m", "manufacturer": "man"})
    assert model.id == 3


def test_parse_compensation_and_revenue():
    comp = parse_compensation({"status": "ok", "message": "hi"})
    assert comp.status == "ok"
    assert parse_compensation("bad").status is None

    assert parse_revenue("bad") is None
    assert parse_revenue({"id": None}) is None
    revenue = parse_revenue(
        {
            "id": "7",
            "minAvailablePower": "1.1",
            "compensation": "2.2",
            "compensationPerKW": "3.3",
        }
    )
    assert revenue.id == 7
    assert revenue.minAvailablePower == 1.1


def test_parse_asset_owner_details_missing_and_success():
    assert parse_asset_owner_details("bad") is None
    assert parse_asset_owner_details({"id": None}) is None
    details = parse_asset_owner_details(
        {
            "id": "9",
            "firstName": "f",
            "lastName": "l",
            "installer": {"id": "1", "name": "inst"},
            "distributor": {"id": "2", "name": "dist"},
            "asset": {"id": "3", "serialNumber": "sn", "assetModel": {}},
            "compensation": {"status": "ok", "message": "m"},
            "bessCompensationStartDate": "2024-01-01",
        }
    )
    assert details is not None
    assert details.id == 9
    assert details.installer.id == 1
    assert details.distributor.id == 2
    assert details.compensation.status == "ok"


def test_parse_uptime_helpers():
    assert parse_uptime_available_months("bad") is None
    months = parse_uptime_available_months(
        [{"value": "2024-01", "label": "Jan"}, "bad"]
    )
    assert months is not None and months[0].value == "2024-01"

    assert parse_uptime_history("bad") is None
    history = parse_uptime_history([{"date": "2024-01", "uptime": "99.9"}, "bad"])
    assert history is not None and history[0].uptime == 99.9
