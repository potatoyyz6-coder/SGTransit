import json
from pathlib import Path

from sg_transit.io import load_network


def test_real_subset_has_frozen_validation_endpoints_and_provenance():
    path = Path("data/real/network.json")
    document = json.loads(path.read_text(encoding="utf-8"))
    network, _ = load_network(path)

    endpoints = document["validation_endpoints"]
    assert endpoints["origin"] in network.stops
    assert endpoints["destination"] in network.stops
    assert document["provenance"]["commit"] == "5b9ed168436b4efe260feef997e66aa39932996e"
    assert all(
        service["timing_quality"] == "estimated_from_distance_and_assumed_headway"
        for service in document["services"]
    )
