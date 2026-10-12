# Candidate checks and optional evaluation

The primary deliverable is a useful set of possible routes and en-route choices,
not a demonstrated speed advantage over Google Maps. The repository does not
automate Google Maps or treat it as ground truth.

## Required candidate checks

- Verify directed stop order and connected boarding/alighting points in the stated
  network. Identify historical topology and limited operating-hour services.
- Apply declared transfer, cycle and search bounds, exposing truncation rather
  than claiming exhaustive coverage. Compare staying onboard with transferring.
- Label timing as sourced ETA, model estimate or unknown. Keep observation time,
  assumptions and current-operation uncertainty visible in experiment output.
- A missing actual outcome or vehicle association does not invalidate a topology
  candidate. It limits the claims that may be made about that candidate's timing.

Existing `python -m sg_transit plan` produces candidates and model evaluations
without requiring a Google record or a completed real journey. The stricter ETA
replay is a separate retrospective evaluation, not a gate on route discovery.
Field validation and ETA-error calibration are optional unless making a claim
that specifically requires them, such as an empirically calibrated catch rate.

## Optional historical comparison: 2026-09-28 16:00

Use the exact same:

- origin: NUS Central Library or the stop selected in the frozen network;
- destination: Jurong East Bus Interchange or the selected destination stop;
- mode: public transport / bus-only where applicable;
- departure: an explicit Singapore `+08:00` timestamp.

Do not silently replace NUS Central Library with National Library Building. They are different places. The template uses IDs from the actual network file, not display names guessed in advance.

## Procedure

1. Run `python -m experiments.run_all` for the reproducible synthetic experiment.
2. Run `python -m sg_transit plan` with the fixed network, endpoint IDs and departure timestamp.
3. In Google Maps, choose public transport and enter the identical endpoint and departure timestamp.
4. Record the first one to three suggested routes in `data/validation/google_maps_template.csv`.
5. Record only the minimum manually observed timing and route-label fields. Do not scrape or commit screenshots or bulk route content; follow AGENTS.md.
6. Leave `observed_actual_minutes` empty unless independent, appropriately anonymized evidence is available. Do not collect passenger identities or personal trip histories; manual riding is not required.
7. Run `python -m sg_transit compare` only after filling `network_sha256`, endpoints, mode, departure and `google_total_minutes`.

The comparison output is a prediction comparison. It must not be described as proof that the model is faster, because Google Maps and the model may use different data, walking assumptions and real-time information.

The current model result for this case uses a static network topology plus estimated headways. The LTA API collector is a separate evidence path: it records live ETA snapshots for later calibration and backtesting. A live snapshot cannot reconstruct the historical traffic state at an earlier departure time.

For optional model comparisons, report means and tails together with assumptions.
P90/P95 and failure metrics computed by simulation describe that model, not verified
real-world reliability. Reducing modeled tail risk is one research question, not
a prerequisite for publishing useful candidate routes and negative results.

## Suggested holdout slots

Use weekday 08:00, 10:00, 13:00, 17:30 and 20:00, plus Saturday 11:00 and Sunday 15:00. Do not tune scoring weights on this validation file; reserve new dates or time slots for final evaluation.
