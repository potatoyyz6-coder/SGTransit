# Agent Boundaries

These rules apply to agents and contributors working on SG-Transit-Reliability.

## Project scope

- Treat this repository as an independent research and open-source experiment.
- Keep the first-party scope limited to route-planning algorithms, simulation,
  reproducible experiments, and clearly documented analysis.
- Do not present the project as an official LTA, Google, or Singapore
  government product.
- Do not build or enable passenger tracking, profiling, or collection of
  personally identifiable information.
- Do not turn the project into a public navigation or safety-critical service
  without a separate legal and product review.

## Routing objective and evidence

- Prioritize useful feasible route candidates and en-route alternatives, including
  staying on the current vehicle versus transferring. Be explicit about the
  network, operating-time assumptions, search bounds and missing coverage.
- Beating Google Maps or Citymapper is not a completion criterion. Manual external
  comparisons, field observations and calibrated ETA errors are optional evaluation
  work, not prerequisites for candidate generation or model-based references.
- Keep topology feasibility, operating-time applicability, predicted connection
  feasibility and observed outcomes separate. An unknown ETA replay outcome must
  not be presented as either an impossible route or a successful actual journey.
- When ETA evidence is missing, retain otherwise valid topology candidates with
  clearly labeled modeled or unknown timing and availability. Never invent live
  arrivals, current operation, verified catch probabilities or guarantees.
- Do not relax evidence gates in retrospective validation just to complete a trip.
  Improving reference planning does not require declaring historical replay truth.

## LTA DataMall

- Use LTA DataMall only according to its current API Terms of Service and the
  Singapore Open Data Licence.
- Keep the DataMall API Access Key in environment variables or local secret
  storage.
- Distinguish the DataMall API Access Key from the Extended OBU SDK Account
  Key. The SDK Account Key must never be used to authenticate DataMall APIs.
- Never commit either key, API tokens, `.env` files, or raw authenticated
  request headers.
- Do not bypass rate limits, evade access controls, impersonate clients, or
  deliberately overload LTA services.
- Preserve source, access date, endpoint, and processing metadata for
  downloaded datasets.
- Keep raw data, cleaned data, model parameters, and derived results in
  separate directories.

## Google Maps and third-party route results

- Google Maps is an external reference baseline only.
- Do not scrape, bulk-download, cache, or redistribute Google Maps route
  content.
- Do not commit Google Maps screenshots or large route-response payloads unless
  a separately reviewed licence permits it.
- Record only the minimum manually observed comparison fields needed for an
  experiment, such as origin, destination, query time, service label, and
  displayed duration.
- Do not use Google Maps results to train a replacement routing dataset or
  claim parity with Google Maps or Citymapper.

## Output and claims

- Label synthetic, observed, LTA-derived, and third-party data separately.
- State assumptions, collection dates, limitations, and uncertainty.
- Do not claim that a result is official, guaranteed, real-time, or safe for
  emergency use.
- Before adding commercial deployment, a public user-facing service, new
  third-party data, or personally identifiable data, stop and request a
  legal/privacy review.

## Required disclaimer

Public-facing documentation should include:

> This project is an independent research project and is not affiliated with,
> endorsed by, or sponsored by the Land Transport Authority of Singapore,
> Google, or Citymapper.
