from experiments.information_technology_case import NETWORK, run_case
from sg_transit.io import load_network
from sg_transit.models import validate_route
from sg_transit.routing import RoutingParameters, enumerate_routes


def test_information_technology_corridor_has_both_reference_service_pairs():
    network, _ = load_network(NETWORK)
    routes = enumerate_routes(network, "16189", "42171", RoutingParameters(max_transfers=1))
    assert ("151-D2", "61-D2") in {route.services for route in routes}
    assert ("95-D1", "970-D2") in {route.services for route in routes}
    for route in routes:
        validate_route(route, network)
        assert route.transfers == 1


def test_case_uses_new_endpoints_and_discloses_missing_walks(tmp_path):
    report = run_case(NETWORK, tmp_path / "case.json", samples=32)
    assert report["origin"] == "16189"
    assert report["destination"] == "42171"
    assert report["parameters"]["max_transfers"] == 1
    assert report["evaluations"]["reliability_policy"]["summary"]["samples"] == 32
    assert report["evaluations"]["reference_95_970"]["policy"]["options"][0]["board"]["service_id"] == "95-D1"
    assert report["evaluations"]["reference_151_61"]["policy"]["options"][0]["board"]["service_id"] == "151-D2"
    assert any("cross-stop walks" in item for item in report["limitations"])
