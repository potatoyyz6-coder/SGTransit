# Data and Third-Party Notices

The root MIT license covers this project's original code and documentation,
not third-party datasets, manual external observations, or vendored assets.

## LTA historical topology

Contains information from LTA DataMall BusStops and BusRoutes, accessed from
the [Vorld/singapore-gtfs mirror](https://github.com/Vorld/singapore-gtfs/tree/5b9ed168436b4efe260feef997e66aa39932996e)
on 2026-09-27, made available under the
[Singapore Open Data Licence v1.0](https://datamall.lta.gov.sg/content/datamall/en/SingaporeOpenDataLicence.html).
The [upstream attribution](https://github.com/Vorld/singapore-gtfs/blob/5b9ed168436b4efe260feef997e66aa39932996e/NOTICE.md)
records its DataMall access on 2026-07-06. We did not collect these CSVs directly
from LTA. Source URLs, pinned revision and SHA-256 hashes are recorded in
[data/real/sources.json](data/real/sources.json).

Only the bus topology CSVs are included from that mirror, not its rail data,
transfer spreadsheets, code, or maps. The mirror's MIT code license does not
relicense LTA data. Old generated reports containing `"license": "MIT"` describe
the mirror's code license, not the data license; this notice corrects that
ambiguity without recalculating historical experimental results.

`data/real/network*.json` and `data/real/derived/` contain derived local networks.
Their topology has the same source attribution; time, headway and delay fields
are modeled unless explicitly marked as estimates from recorded ETA evidence.
Historical operating windows do not establish current service availability.
Project-generated route diagrams use these stop coordinates and service sequences,
not third-party map tiles. No accuracy or journey guarantee is made.

## Optional ETA and manual comparisons

Raw API captures, credentials and private historical snapshots are excluded.
Live requests require the user's own DataMall key and explicit confirmation.
Use remains subject to the [DataMall API Terms of Service](https://datamall.lta.gov.sg/content/datamall/en/API-TOS.html)
and the Singapore Open Data Licence. Reports distinguish predictions from
observed arrivals; private-capture analyses cannot be reproduced without the
corresponding local records. Synthetic fixtures test those code paths offline.

`data/validation/` holds limited manually supplied comparison fields and derived
checks, not an API response archive, screenshots, a routing dataset or training
data. Google Maps and Citymapper are external references only. Their names and
content are not relicensed by our MIT license. No third-party scraping occurs.

## Lucide

`experiments/web/vendor/lucide.min.js` is the unmodified Lucide 1.55.0 UMD build.
The favicon uses its BusFront icon. Preserve the bundled
[ISC/MIT notices](experiments/web/vendor/LICENSE-lucide).
Python dependencies retain their own licenses and are installed separately.

This project is an independent research project and is not affiliated with,
endorsed by, or sponsored by the Land Transport Authority of Singapore,
Google, or Citymapper.
