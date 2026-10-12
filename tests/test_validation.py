import csv

from sg_transit.__main__ import compare_case, plan_case


def test_google_comparison_accepts_a_completed_same_case_observation(tmp_path):
    plan_path = tmp_path / "case.json"
    plan_case(
        "data/real/network.json",
        "16181",
        "28009",
        "2026-09-14T08:00:00+08:00",
        plan_path,
        samples=32,
        seed=100,
        selection_seed=7,
        selection_samples=16,
    )
    import json

    document = json.loads(plan_path.read_text(encoding="utf-8"))
    observations = tmp_path / "observations.csv"
    fields = [
        "case_id",
        "origin_stop_id",
        "destination_stop_id",
        "mode",
        "departure",
        "google_route_rank",
        "google_total_minutes",
        "observed_actual_minutes",
        "network_sha256",
    ]
    with observations.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=fields)
        writer.writeheader()
        writer.writerow(
            {
                "case_id": "CL-JE-test",
                "origin_stop_id": document["origin"],
                "destination_stop_id": document["destination"],
                "mode": document["mode"],
                "departure": document["departure"],
                "google_route_rank": "1",
                "google_total_minutes": "60",
                "observed_actual_minutes": "",
                "network_sha256": document["network_sha256"],
            }
        )
    output = tmp_path / "comparison.json"
    report = compare_case(plan_path, observations, output)
    assert report["comparisons"][0]["google_estimate"] == 60
