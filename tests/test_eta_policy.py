from datetime import timedelta

import pytest

from sg_transit.eta_matching import instant
from sg_transit.eta_policy import SuffixReplaySelector, expand_paths
from sg_transit.eta_replay import ReplayLimits, Ride, Walk
from sg_transit.models import Stop, TransitNetwork, TransitService
from sg_transit.routing import RoutingParameters

START = instant("2026-10-04T14:30:00+08:00")


def fixture():
    network = TransitNetwork([Stop("A", "A"), Stop("B", "B")], [
        TransitService("slow", ("A", "B"), (10,), 15),
        TransitService("fast", ("A", "B"), (1,), 15)])
    paths, routes = expand_paths([[Ride("slow", "A", "B")], [Ride("fast", "A", "B")]], network)
    selector = SuffixReplaySelector(network, routes, RoutingParameters())
    return paths, selector


def test_adapter_uses_existing_score_instead_of_first_bus():
    _, selector = fixture()
    candidates = [(START + timedelta(seconds=t), s, "B", Ride(s, "A", "B"), None, None, False)
                  for s, t in (("slow", 20), ("fast", 30))]
    selected, detail = selector.choose(candidates, stop="A", now=START, departure=START,
        onboard=None, used=frozenset(), visited=frozenset({"A"}), alighted=None, limits=ReplayLimits())
    assert selected[1] == "fast"
    assert detail["stationary_expected_remaining_score"] == pytest.approx(1.5)
    assert selector.policy.local_updates == 1


def test_restricted_arcs_are_not_replaced_by_unobserved_better_route():
    _, selector = fixture()
    state = selector.policy.initial_state(0)
    choice = selector.policy.update(state, {"slow": 0, "fast": 0}, allowed_arcs={("slow", "B")})
    assert choice.arc.service_id == "slow"
    assert selector.policy.update(state, {"slow": 0}, allowed_arcs=set()) is None


def test_policy_and_replay_must_share_constraints():
    _, selector = fixture()
    with pytest.raises(ValueError, match="constraints"):
        selector.choose([], stop="A", now=START, departure=START, onboard=None,
            used=frozenset(), visited=frozenset({"A"}), alighted=None,
            limits=ReplayLimits(transfer_seconds=60))


def test_expansion_exposes_continuation_without_inventing_transfer():
    network = TransitNetwork([Stop(s, s) for s in "ABC"], [TransitService("61", tuple("ABC"), (2, 3), 15)])
    paths, routes = expand_paths([[Ride("61", "A", "C")]], network)
    assert paths == [[Ride("61", "A", "B"), Ride("61", "B", "C")]]
    assert routes[0].transfers == 0
    with pytest.raises(ValueError, match="bus-only"):
        expand_paths([[Walk("A", "C", 5)]], network)
