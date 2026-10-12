import json

import pytest

from sg_transit.lta import LTAApiError
from sg_transit.lta_static import collect_static


def test_static_pagination_and_provenance_without_secrets(tmp_path):
    calls, sleeps = [], []
    def transport(url, headers, timeout):
        calls.append(url)
        assert headers["AccountKey"] == "test-secret"
        return json.dumps({"value": [{"id": i} for i in range(500)] if len(calls) == 1 else [{"id": 500}]}).encode()
    output = tmp_path / "routes.json"
    result = collect_static("test-secret", "BusRoutes", output, transport=transport, sleep_fn=sleeps.append)
    assert len(result["value"]) == 501
    assert "%24skip=500" in calls[1]
    assert sleeps == [1.0]
    assert "test-secret" not in output.read_text()
    assert all(page["received_at"] and page["sha256"] for page in result["pagination"])
    with pytest.raises(ValueError, match="overwrite"):
        collect_static("test-secret", "BusRoutes", output)


def test_static_incomplete_and_repeated_pages_not_saved(tmp_path):
    transport = lambda *args: json.dumps({"value": [{"id": i} for i in range(500)]}).encode()
    output = tmp_path / "routes.json"
    with pytest.raises(LTAApiError, match="budget"):
        collect_static("key", "BusRoutes", output, transport=transport, max_pages=1)
    with pytest.raises(LTAApiError, match="Repeated"):
        collect_static("key", "BusRoutes", output, transport=transport, sleep_fn=lambda _: None)
    assert not output.exists()


def test_static_rejects_unexpected_response(tmp_path):
    with pytest.raises(LTAApiError):
        collect_static("key", "BusRoutes", tmp_path / "bad.json", transport=lambda *args: b'{"message": "denied"}')
    with pytest.raises(ValueError):
        collect_static("key", "Other", tmp_path / "other.json")
