import datetime

from flowerhub_portal_api_client.types import FlowerHubStatus


def test_flowerhub_status_age_seconds():
    fh = FlowerHubStatus(status="ok", message="hi", updated_at=None)
    assert fh.age_seconds() is None

    now = datetime.datetime.now(datetime.timezone.utc)
    fh.updated_at = now - datetime.timedelta(seconds=5)
    age = fh.age_seconds()
    assert age is not None and 4.0 <= age <= 6.0
