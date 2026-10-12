import csv
import json
from pathlib import Path

from sg_transit.models import Stop, TransitNetwork, TransitService
from sg_transit.routing import route_min_ride_time, route_min_transfers, route_reliable, route_shortest_time
from sg_transit.simulation import simulate_route


def build_demo_network() -> TransitNetwork:
    stops = [Stop(f"S{i}", f"Stop {i}", i, 0) for i in range(1, 9)]
    services = [
        TransitService("B10", ("S1", "S2", "S3", "S4"), (8, 8, 8), 18),
        TransitService("B20", ("S1", "S5", "S6"), (10, 10), 10),
        TransitService("B30", ("S4", "S7", "S8"), (8, 8), 12),
        TransitService("B40", ("S6", "S7", "S8"), (9, 9), 20),
        TransitService("B50", ("S3", "S6"), (12,), 8),
    ]
    return TransitNetwork(stops, services)


def main() -> None:
    network = build_demo_network()
    routes = {
        "shortest_time": route_shortest_time(network, "S1", "S8"),
        "min_transfers": route_min_transfers(network, "S1", "S8"),
        "min_ride_time": route_min_ride_time(network, "S1", "S8"),
    }
    routes["reliable"] = route_reliable(network, "S1", "S8", samples=10000)
    output = Path(__file__).resolve().parents[1] / "results"
    output.mkdir(exist_ok=True)
    rows = []
    for name, route in routes.items():
        if route is None:
            continue
        summary = simulate_route(route, network, samples=10000)
        rows.append({"strategy": name, "services": " -> ".join(route.services), **summary.__dict__})
    with (output / "demo_results.csv").open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)
    (output / "demo_routes.json").write_text(json.dumps({name: route.services for name, route in routes.items() if route}, indent=2), encoding="utf-8")
    print("Generated results/demo_results.csv")
    for row in rows:
        print(f"{row['strategy']:16} {row['services']:12} mean={row['mean_minutes']:.1f} p95={row['p95_minutes']:.1f}")


if __name__ == "__main__":
    main()
