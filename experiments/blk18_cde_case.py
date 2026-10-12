"""Offline route references from Blk 18 to Coll of Design & Engrg; no API calls."""
from __future__ import annotations

import argparse
from collections import Counter
import csv
from dataclasses import asdict, dataclass
import hashlib
import json
import math
from pathlib import Path

from data.real.build_subset import RAW, load_rows, select_pattern
from sg_transit.adaptive import JourneyState, SharedSuffixPolicy, StructuralState
from sg_transit.models import Stop, TransitNetwork, TransitService, validate_route
from sg_transit.reference import clock_minutes, estimate, shortlist, window_status
from sg_transit.routing import RoutingParameters, SearchBudgetExceeded, enumerate_routes, expected_time, route_key


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "results/blk18_cde_reference"
ORIGIN, DESTINATION = "42161", "16159"
SEGMENTS = (
    ("41", "1", ORIGIN, "28109"), ("173", "1", ORIGIN, "17009"),
    ("106", "1", "28109", "17159"), ("106A", "1", "28109", "28019"),
    ("963", "1", "28109", "28019"), ("105", "2", "28019", "17159"),
    ("183", "1", "28019", DESTINATION), ("188", "1", "28019", DESTINATION),
    ("96", "1", "17009", DESTINATION),
)
LIMITED = ("106A-D1",)
DISCLAIMER = ("This project is an independent research project and is not affiliated with,\n"
              "endorsed by, or sponsored by the Land Transport Authority of Singapore,\n"
              "Google, or Citymapper.")


@dataclass(frozen=True)
class Settings:
    speed_kmh: float = 20
    headway: float = 15
    delay_max: float = 3
    transfer_buffer: float = 3
    departure: str = "10:00"
    day: str = "weekday"
    max_transfers: int = 5
    max_trip_minutes: float = 120
    max_transfer_gap: float = 45
    max_candidates: int = 10000
    max_expansions: int = 100000

    def __post_init__(self):
        for value in (self.speed_kmh, self.headway, self.max_trip_minutes, self.max_transfer_gap):
            if not math.isfinite(value) or value <= 0:
                raise ValueError("Speed, headway and time limits must be positive and finite")
        for value in (self.delay_max, self.transfer_buffer):
            if not math.isfinite(value) or value < 0:
                raise ValueError("Delay and buffer must be nonnegative and finite")
        if clock_minutes(self.departure) >= 1440 or self.day not in {"weekday", "saturday", "sunday"}:
            raise ValueError("Use a day type and a 00:00-23:59 departure")
        for value, minimum in ((self.max_transfers, 0), (self.max_candidates, 1), (self.max_expansions, 1)):
            if not isinstance(value, int) or value < minimum:
                raise ValueError("Invalid search bound")

    def routing(self):
        return RoutingParameters(max_transfers=self.max_transfers, max_trip_minutes=self.max_trip_minutes,
                                 max_transfer_gap=self.max_transfer_gap, transfer_walk_minutes=self.transfer_buffer,
                                 max_candidates=self.max_candidates, max_expansions=self.max_expansions)


def build_network(settings=Settings()):
    source_path = ROOT / "data/real/sources.json"
    source = json.loads(source_path.read_text(encoding="utf-8"))
    hashes = {name: hashlib.sha256((RAW / name).read_bytes()).hexdigest()
              for name in ("BusRoutes.csv", "BusStops.csv")}
    if any(source["raw_sha256"][name] != digest for name, digest in hashes.items()):
        raise ValueError("Frozen source hash mismatch")
    rows = load_rows(RAW / "BusRoutes.csv")
    stops = {r["BusStopCode"]: r for r in load_rows(RAW / "BusStops.csv")}
    services, windows, patterns = [], {}, {}
    for number, direction, start, end in SEGMENTS:
        pattern = select_pattern(rows, number, direction, start, end)
        key = f"{number}-D{direction}"
        distances = [float(r["Distance"]) for r in pattern]
        if any(not math.isfinite(v) for v in distances) or any(b < a for a, b in zip(distances, distances[1:])):
            raise ValueError("Invalid cumulative route distance")
        services.append(TransitService(key, tuple(r["BusStopCode"] for r in pattern),
            tuple(max(.5, (b-a)*60/settings.speed_kmh) for a, b in zip(distances, distances[1:])),
            settings.headway, settings.delay_max))
        windows[key] = {r["BusStopCode"]: {k: v for k, v in r.items() if k.endswith(("_FirstBus", "_LastBus"))}
                        for r in pattern}
        patterns[key] = {"service_no": number, "direction": direction, "start": start, "end": end,
                         "ordered_source_rows": pattern}
    codes = sorted({s for service in services for s in service.stops})
    network = TransitNetwork([Stop(s, stops[s]["Description"], float(stops[s]["Longitude"]),
                                   float(stops[s]["Latitude"])) for s in codes], services)
    provenance = {"data_kind": "historical_topology_with_assumed_timing", "raw_sha256": hashes,
                  "source_url": source["source_url"], "raw_urls": source["raw_urls"],
                  "accessed_at": source["accessed_at"], "source_commit": source["commit"],
                  "sources_manifest_sha256": hashlib.sha256(source_path.read_bytes()).hexdigest(),
                  "scope": "Nine declared directed service fragments; no area-wide or island-wide completeness claim",
                  "processing": "Keep every original stop; rides=max(0.5min, distance_delta*60/speed_kmh)",
                  "api_calls": 0, "new_collection_scheduled": False}
    return network, windows, patterns, provenance


def route_text(row, network):
    parts = [f"{l['service_id']}: {network.stops[l['board_stop']].name} ({l['board_stop']}) -> "
             f"{network.stops[l['alight_stop']].name} ({l['alight_stop']})" for l in row["legs"]]
    return " | ".join(parts) or "Already at destination"


def prefix_state(routes, network, stop, onboard, now, departure, *, waiting=False):
    """Use a searched route to supply a legal history, not a hand-written itinerary."""
    for route in sorted(routes, key=lambda r: (r.transfers, expected_time(r, network), route_key(r))):
        used, visited = set(), {route.origin}
        for leg in route.legs:
            service = network.services[leg.service_id]
            a, b = service.stops.index(leg.board_stop), service.stops.index(leg.alight_stop)
            used.add(service.id)
            for node in service.stops[a+1:b+1]:
                visited.add(node)
                if node == stop and service.id == onboard:
                    return JourneyState(StructuralState(stop, None if waiting else onboard,
                                        frozenset(used), frozenset(visited)), now, departure, now), route
    return None, None


def compare_local(policy, state, departures, windows, day):
    allowed, excluded = set(), []
    for arc, _, continuing in policy.transitions(state.structure):
        board = state.now if continuing else departures.get(arc.service_id)
        if continuing or (board is not None and window_status(windows.get(arc.service_id, {}).get(arc.start, {}), board, day) == "within_historical_window"):
            allowed.add((arc.service_id, arc.end))
        else:
            excluded.append({"service": arc.service_id, "end": arc.end,
                             "reason": "no_current_synthetic_eta_or_unverified_operating_window"})
    alternatives = []
    for key in sorted(allowed):
        choice = policy.update(state, departures, allowed_arcs={key})
        if choice is not None and math.isfinite(choice.estimated_remaining_score):
            alternatives.append({"service": choice.arc.service_id, "next_stop": choice.arc.end,
                "continuing": choice.continuing, "board_minute": choice.board_time,
                "wait_including_buffer_minutes": choice.board_time - state.now,
                "new_boarding_delay_minutes": 0 if choice.continuing else policy.network.services[choice.arc.service_id].delay_max_minutes/2,
                "new_transfer": bool(state.structure.used) and not choice.continuing,
                "remaining_score": choice.estimated_remaining_score})
    selected = policy.update(state, departures, allowed_arcs=allowed)
    selection = None
    if selected is not None and math.isfinite(selected.estimated_remaining_score):
        selection = next(a for a in alternatives if (a["service"], a["next_stop"]) == (selected.arc.service_id, selected.arc.end))
    return {"alternatives": alternatives, "selected": selection, "excluded": excluded}


def local_examples(network, routes, windows, settings):
    if not routes or (routes[0].origin, routes[0].destination) != (ORIGIN, DESTINATION):
        return {"status": "not_applicable", "examples": []}
    parameters = settings.routing()
    policy = SharedSuffixPolicy(network, routes, parameters, value_samples=64, value_seed=29)
    b = settings.transfer_buffer
    specs = [
        ("onboard_173_at_depot", "28109", "173-D1", False, 25, {"106-D1": b+.5, "963-D1": b+6}),
        ("direct_services_soon", "28019", "173-D1", True, 30,
         {"183-D1": b+.5, "188-D1": b+1, "105-D2": b+5, "106-D1": b+6}),
        ("feeder_services_soon", "28019", "173-D1", True, 30,
         {"183-D1": b+18, "188-D1": b+20, "105-D2": b+.5, "106-D1": b+1}),
        ("onboard_106_at_toh_tuck", "28019", "106-D1", False, 30,
         {"183-D1": b+18, "188-D1": b+20, "105-D2": b+1}),
        ("onboard_183_at_blk365", "17159", "183-D1", False, 45, {"96-D1": b+.5}),
    ]
    examples = []
    try:
        for name, stop, onboard, waiting, elapsed, offsets in specs:
            start = clock_minutes(settings.departure)
            state, prefix_route = prefix_state(routes, network, stop, onboard, start+elapsed, start, waiting=waiting)
            if state is None:
                examples.append({"id": name, "status": "no_eligible_history"})
                continue
            departures = {s: state.now + delta for s, delta in offsets.items()}
            examples.append({"id": name, "status": "synthetic_reference", "stop": stop,
                "onboard": state.structure.onboard, "previous_service": onboard,
                "now_minute": state.now, "elapsed_minutes": elapsed,
                "used": sorted(state.structure.used), "visited": sorted(state.structure.visited),
                "history_route": asdict(prefix_route), "departures": departures,
                **compare_local(policy, state, departures, windows, settings.day)})
    except SearchBudgetExceeded as exc:
        return {"status": "value_budget_exceeded", "error": str(exc), "examples": examples}
    return {"status": "completed", "candidate_count": len(routes), "value_states": policy.value_state_count,
            "value_samples": 64, "value_seed": 29, "transfer_penalty": parameters.transfer_penalty,
            "note": "Synthetic local clocks, not observations. Existing stationary downstream mean-plus-transfer score; not arrival time or a catch probability. Shared arcs can recombine candidate routes; future operating windows are not guaranteed by this stationary score.",
            "examples": examples}


def run(output=OUTPUT, settings=Settings(), *, origin=ORIGIN, destination=DESTINATION, make_plot=True):
    network, windows, patterns, provenance = build_network(settings)
    parameters, stats = settings.routing(), {}
    report = {"schema_version": 1, "origin": origin, "destination": destination,
              "settings": asdict(settings), "parameters": asdict(parameters), "provenance": provenance,
              "network": {"stops": [asdict(s) for s in network.stops.values()],
                          "services": [asdict(s) for s in network.services.values()]},
              "patterns": patterns, "limited_services": list(LIMITED),
              "search": stats, "candidate_search_complete": False, "candidates": [], "shortlist": []}
    routes = []
    try:
        routes = enumerate_routes(network, origin, destination, parameters, stats=stats)
        report.update(status="completed" if routes else "no_route_in_declared_network", candidate_search_complete=True)
    except SearchBudgetExceeded as exc:
        report.update(status="search_budget_exceeded", error=str(exc))
    for index, route in enumerate(routes):
        validate_route(route, network)
        row = estimate(route, network, windows, parameters, departure=clock_minutes(settings.departure),
                       day=settings.day, limited=LIMITED)
        row["id"] = f"R{index+1:05d}"
        row["text"] = route_text(row, network)
        report["candidates"].append(row)
    report["shortlist"] = shortlist(report["candidates"])
    eligible = [r for r, v in zip(routes, report["candidates"]) if v["recommendable"]]
    report["recommendable_count"] = len(eligible)
    report["exclusion_counts"] = dict(Counter(reason for r in report["candidates"] for reason in r["exclusion_reasons"]))
    report["local_choices"] = local_examples(network, eligible, windows, settings)
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    (output / "reference.json").write_text(json.dumps(report, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    columns = ["id", "text", "estimated_total_minutes", "ride_minutes", "wait_minutes", "buffer_minutes",
               "delay_minutes", "transfers", "recommendable", "exclusion_reasons"]
    with (output / "candidates.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=columns)
        writer.writeheader()
        for row in report["candidates"]:
            writer.writerow({k: ";".join(row[k]) if k == "exclusion_reasons" else row[k] for k in columns})
    (output / "report.md").write_text(render(report, network, plotted=make_plot), encoding="utf-8")
    if make_plot:
        plot_network(network, output / "routes.png")
    return report


def render(report, network, *, plotted=True):
    settings = report["settings"]
    lookup = {r["id"]: r for r in report["candidates"]}
    stop_name = lambda s: f"{network.stops[s].name} ({s})"
    lines = ["# Blk 18 to Coll of Design & Engrg", "", DISCLAIMER, "",
             "## Reference, not a guaranteed trip", "",
             f"{stop_name(report['origin'])} -> {stop_name(report['destination'])}.",
             f"Reference: {settings['day']} {settings['departure']} Singapore service-day clock; not a dated timetable or live forecast.",
             "Historical ordered topology and operating windows; every ride/wait/delay below is modeled.",
             "No API calls, scheduled collection, field trip or Google comparison is required or performed.",
             "This is one selected corridor, not a search of every service in Singapore.", "",
             f"Search status: **{report['status']}**; complete within declared bounds: {report['candidate_search_complete']}.",
             f"Candidates: {len(report['candidates'])}; eligible for default references: {report['recommendable_count']}.",
             f"Expansions: {report['search'].get('expansions', 0)}. Budget: {settings['max_candidates']} candidates / {settings['max_expansions']} expansions.",
             f"Exclusion reasons (overlap possible): {json.dumps(report['exclusion_counts'], sort_keys=True)}.",
             "Excluded candidates remain in candidates.csv/reference.json. Unknown timing/operation does not erase topology feasibility.",
             "106A is retained only as a limited-service topology alternative, never in the default shortlist or local scoring pool.", "",
             "## Route references", "",
             "Mean model minutes, not observed journey times. Delay is separate from waiting and counted once per boarding.",
             "A displayed family merges identical service sequences, not different services; transfer-stop variants remain available below.", "",
             "| ID | Services | Total | Riding | Waiting | Buffer | Delay | Transfers | Variants |",
             "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |"]
    for family in report["shortlist"]:
        r = lookup[family["representative_id"]]
        lines.append(f"| {r['id']} | {' -> '.join(r['services']) or 'Already there'} | {r['estimated_total_minutes']:.2f} | {r['ride_minutes']:.2f} | {r['wait_minutes']:.2f} | {r['buffer_minutes']:.2f} | {r['delay_minutes']:.2f} | {r['transfers']} | {len(family['variant_ids'])} |")
    if not report["shortlist"]:
        lines += ["", "No default recommendation. Inspect the search status and exclusion reasons; this is not a claim of island-wide unreachability."]
    for family in report["shortlist"]:
        r = lookup[family["representative_id"]]
        lines += ["", f"### {r['id']}: {' -> '.join(r['services']) or 'Already there'}", "",
                  f"Selected for: {', '.join(family['selection_reasons'])}.", ""]
        for leg in r["legs"]:
            lines.append(f"- {leg['service_id']}: {stop_name(leg['board_stop'])} -> {stop_name(leg['alight_stop'])}; ride {leg['ride_minutes']:.2f} min, wait {leg['wait_minutes']:.2f}, buffer {leg['transfer_minutes']:.2f}, delay {leg['mean_boarding_delay_minutes']:.2f}.")
        lines += ["", f"<details><summary>All {len(family['variant_ids'])} eligible transfer-stop variants</summary>", "",
                  "| ID | Interchanges (service before transfer) | Total minutes |", "| --- | --- | ---: |"]
        for identifier in family["variant_ids"]:
            variant = lookup[identifier]
            changes = "; ".join(f"{l['service_id']} at {stop_name(l['alight_stop'])}" for l in variant["legs"][:-1]) or "None"
            lines.append(f"| {identifier} | {changes} | {variant['estimated_total_minutes']:.2f} |")
        lines += ["", "</details>"]
    lines += ["", "## Along-the-way choices", "",
              "Every eligible candidate participates, not just the eight displayed families. These local ETA examples are deliberately synthetic.",
              "The full legal history is taken from a searched route. The local clock and arrival offsets are scenario inputs, not reconstructed observations.",
              "The score includes future model waiting and a five-minute transfer penalty; it is NOT an arrival-time prediction.",
              "Future waits use 64 fixed draws (seed 29). No Monte Carlo journey benchmark or catch probability is reported.",
              f"Local example status: {report['local_choices']['status']}.", ""]
    for item in report["local_choices"]["examples"]:
        lines += [f"### {item['id']}", ""]
        if item["status"] != "synthetic_reference":
            lines += [item["status"], ""]
            continue
        lines += [f"At {stop_name(item['stop'])}; onboard: {item['onboard'] or 'none (already alighted)'}. Elapsed scenario time: {item['elapsed_minutes']} minutes.",
                  "", "| Action | Next stop | Wait incl. buffer | New boarding delay | New transfer | Remaining score |",
                  "| --- | --- | ---: | ---: | --- | ---: |"]
        for a in item["alternatives"]:
            action = ("Stay on " if a["continuing"] else "Board ") + a["service"]
            lines.append(f"| {action} | {stop_name(a['next_stop'])} | {a['wait_including_buffer_minutes']:.2f} | {a['new_boarding_delay_minutes']:.2f} | {a['new_transfer']} | {a['remaining_score']:.2f} |")
        selected = item["selected"]
        lines += ["", "Selected: " + (("stay on " if selected["continuing"] else "board ") + selected["service"] if selected else "no feasible action in this scenario"), ""]
    lines += ["## Structure and assumptions", ""]
    if plotted:
        lines += ["![Directed service fragments and shared stops](routes.png)", ""]
    lines += ["All original intermediate stops are retained; same-stop transfers can occur wherever the fragments meet.",
              "173 may continue through Depot to Aft Toh Tuck Ave or Clementi Int. 106 may stay through to Blk 365.",
              "183 remains onboard through Blk 365 to the destination; continuing does not add waiting, delay or a transfer.",
              f"Ride assumption: {settings['speed_kmh']} km/h, >=0.5 min per original segment; headway {settings['headway']} min; boarding delay Uniform(0,{settings['delay_max']}).",
              f"Transfer buffer {settings['transfer_buffer']} min; max {settings['max_transfers']} transfers, {settings['max_transfer_gap']} min modeled gap, {settings['max_trip_minutes']} min trip.",
              "Search uses a minimum ride/buffer bound; default eligibility also checks estimated full time and transfer gaps.",
              "These are model constraints, not verified fare rules. Historical windows are checked at each estimated boarding time.",
              "Operating windows do not establish today's availability. Missing/invalid windows remain unknown, not fabricated.",
              "The shared policy uses legal history and current local inputs; recombined paths and future operating windows are not independently validated forecasts.",
              "Ordinary service numbers, not short-working variants, form the default opportunity set; no bonus is assigned just for service count.",
              "", "## Reproduce", "", "`python -m experiments.blk18_cde_case`", "",
              "CLI options configure speed, headway, delay, buffer, day/time and search bounds. reference.json records exact settings and frozen source hashes.",
              "candidates.csv/reference.json contain every completed-search candidate. No previous case artifacts are overwritten.", ""]
    return "\n".join(lines)


def plot_network(network, path):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import networkx as nx

    graph = nx.DiGraph()
    for service in network.services.values():
        graph.add_edges_from(zip(service.stops, service.stops[1:]))
    order = list(nx.lexicographical_topological_sort(graph))
    x = {stop: index for index, stop in enumerate(order)}
    colors = ["#00796b", "#c63d53", "#3366aa", "#888888", "#967000", "#318436", "#ac4d8e", "#444444", "#148299"]
    fig, ax = plt.subplots(figsize=(19, 9))
    for col in range(len(order)):
        ax.axvline(col, color="#dddddd", lw=.7, zorder=0)
    services = list(network.services.values())
    for i, (service, color) in enumerate(zip(services, colors)):
        y = len(services) - 1 - i
        ax.plot([x[s] for s in service.stops], [y]*len(service.stops),
                color=color, marker="o", ms=5, lw=2, linestyle="--" if service.id in LIMITED else "-")
        ax.annotate("", (x[service.stops[-1]]+.22, y), (x[service.stops[-1]], y),
                    arrowprops={"arrowstyle": "->", "color": color})
    ax.set_yticks(range(len(services)), [s.id + (" (limited)" if s.id in LIMITED else "") for s in reversed(services)])
    ax.set_xticks(range(len(order)), [f"{network.stops[s].name}\n{s}" for s in order], rotation=65, ha="right", fontsize=8)
    ax.set_xlim(-.5, len(order)-.5)
    ax.set_ylim(-.7, len(services)-.3)
    ax.set_title("Blk 18 -> Coll of Design & Engrg: directed service fragments", fontsize=17, loc="left", pad=25)
    ax.spines[["top", "right", "left"]].set_visible(False)
    ax.tick_params(axis="y", length=0)
    fig.text(.12, .04, "Left to right = travel direction. Only dots mark stops; a line crossing a column does not stop there.\nTransfer where service dots share a column. Spacing is schematic, not travel time. 106A is excluded from default references.", fontsize=10)
    fig.subplots_adjust(left=.12, right=.98, top=.88, bottom=.34)
    fig.savefig(path, dpi=140, metadata={"Software": "SG-Transit-Reliability"})
    plt.close(fig)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    for name in ("speed_kmh", "headway", "delay_max", "transfer_buffer", "max_trip_minutes", "max_transfer_gap"):
        parser.add_argument("--" + name.replace("_", "-"), type=float, default=getattr(Settings(), name))
    for name in ("max_transfers", "max_candidates", "max_expansions"):
        parser.add_argument("--" + name.replace("_", "-"), type=int, default=getattr(Settings(), name))
    parser.add_argument("--departure", default="10:00")
    parser.add_argument("--day", choices=["weekday", "saturday", "sunday"], default="weekday")
    args = vars(parser.parse_args())
    output = args.pop("output")
    report = run(output, Settings(**args))
    print(json.dumps({"status": report["status"], "candidates": len(report["candidates"]),
                      "recommendable": report["recommendable_count"], "families": len(report["shortlist"]),
                      "local_choices": report["local_choices"]["status"], "report": str(output / "report.md")}, indent=2))


if __name__ == "__main__":
    main()
