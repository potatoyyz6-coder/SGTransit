from copy import deepcopy
import json

import pytest

from experiments.pei_hwa_details import OBSERVATIONS, build_extended, components, exact_route
from sg_transit.models import validate_route


def test_detailed_times_reconcile_and_walk_is_not_double_counted():
    rows = json.loads(OBSERVATIONS.read_text())["routes"]
    assert [components(row)["total"] for row in rows] == [48, 52, 63, 65]
    assert [components(row)["ride"] for row in rows] == [17, 19, 35, 32]
    assert components(rows[1])["transfer_wait_after_walk"] == 12
    for row in rows:
        c = components(row)
        assert c["initial_wait"] + c["ride"] + c["transfer_wait_after_walk"] + c["walk"] == c["total"]
    bad = deepcopy(rows[0])
    bad["total_minutes"] = 53
    with pytest.raises(ValueError):
        components(bad)


def test_static_extension_uses_original_timing_and_exact_transfer_stops(tmp_path):
    network, doc = build_extended(tmp_path / "network.json")
    assert network.services["95-D1"].stops[-2:] == ("11401", "11261")
    assert all(s.headway_minutes == 15 for s in network.services.values())
    assert doc["timing_parameters"]["speed_kmh"] == 20
    for first, second, transfer in (("151-D2", "61-D2", "42141"), ("95-D1", "970-D2", "11261")):
        route = exact_route(network, first, second, transfer)
        validate_route(route, network)
        assert route.legs[0].alight_stop == route.legs[1].board_stop == transfer
