# Methodology and reproducibility

A small Python CLI using residential sale prices as an affluence proxy. The delivered result is **[output/selected.csv](../output/selected.csv)**: 2023–2025 sales, more than 20% above the median of sector medians within two graph steps. Low-sale sectors are retained and flagged.

## Run locally

Python 3.12 was used. Create and activate a virtual environment, then:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m pytest -q
python wealth.py prices --years 2023 2024 2025 --min-sales 20
python wealth.py geography
python wealth.py analyse --layers 1 2 3
python wealth.py select --layer 2 --above 0.20 --min-sales 1
```

The final command deliberately retains all observed qualifying sectors, including those below 20 sales. To require at least 20 sales or restrict national percentiles:

```powershell
python wealth.py select --layer 2 --above 0.20 --min-sales 20
python wealth.py select --layer 2 --above 0.30 --min-sales 20 --min-percentile 70 --max-percentile 100
```

Each selection overwrites `output/selected.csv`. `select` defaults to 20 sales; `prices --min-sales` controls flags without discarding values. Percentile bounds are inclusive; `--above` is strict and expressed as a fraction, so 0.20 means 20%. Re-run `analyse` after changing prices or geography, and `select` after changing analysis.

All commands accept `--data-dir` and `--output-dir` after the command name. Geography accepts `--oa-file PATH --lookup-file PATH` for offline inputs. Dependencies from the delivery run are recorded in `requirements.lock.txt`; install that file to reproduce those versions.

## Exact sources

HM Land Registry yearly Price Paid CSVs (no header):

- [2023](https://price-paid-data.publicdata.landregistry.gov.uk/pp-2023.csv)
- [2024](https://price-paid-data.publicdata.landregistry.gov.uk/pp-2024.csv)
- [2025](https://price-paid-data.publicdata.landregistry.gov.uk/pp-2025.csv)
- [Yearly downloads and conditions](https://www.gov.uk/government/statistical-data-sets/price-paid-data-yearly-file)
- [Field definitions and limitations](https://www.gov.uk/guidance/about-the-price-paid-data)

Other years use `https://price-paid-data.publicdata.landregistry.gov.uk/pp-{year}.csv`.

ONS Output Areas (December 2021), England and Wales, BGC V2: generalised to 20 metres and clipped to the coastline at mean high water.

- [Exact shapefile ZIP download](https://open-geography-portalx-ons.hub.arcgis.com/api/download/v1/items/6beafcfd9b9c4c9993a06b6b199d7e6d/shapefile?layers=0)
- [Dataset metadata](https://www.arcgis.com/home/item.html?id=6beafcfd9b9c4c9993a06b6b199d7e6d)
- [Feature service](https://services1.arcgis.com/ESMARspQHYMw9BZ9/arcgis/rest/services/Output_Areas_2021_EW_BGC_V2/FeatureServer/0)

ONS Output Area (2021) to Postcode Sector (May 2021) best-fit lookup, England and Wales:

- [Exact CSV download](https://open-geography-portalx-ons.hub.arcgis.com/api/download/v1/items/cf826bd3d29947ef9dcda7cd9753f7a8/csv?layers=0)
- [Dataset metadata](https://www.arcgis.com/home/item.html?id=cf826bd3d29947ef9dcda7cd9753f7a8)
- [Feature service](https://services1.arcgis.com/ESMARspQHYMw9BZ9/arcgis/rest/services/OA21_PCDS21_EW_LU/FeatureServer/0)

The live lookup uses `OA21CD` and `PCDS`; the code also accepts the documented `PCDS21CD` name. The lookup allocates OAs using population-weighted centroids. Downloads are cached in `data/` with URL, retrieval time, size and HTTP metadata. New downloads record SHA-256 checksums. Cached downloads with metadata validate source URL, size and any recorded checksum before reuse. Legacy metadata without a checksum validates URL and size; manually supplied caches without metadata remain trusted local inputs. Reuse requires no network request. Incomplete downloads never replace the cache. To refresh a source, remove its cached file and rerun the relevant command. Historic price files are revised by the publisher; a later fresh download can change results.

## Methodology and columns

1. Pool transactions from the requested years, using the transfer date in each row. Keep Category A and property types D, S, T and F. Exclude O, deleted records, nonpositive/nonfinite prices, invalid dates and missing/invalid postcodes. Yearly snapshots are expected; monthly change files are not supported. Full postcodes are validated with UK postcode regex forms and restricted letters, then named outward-code and inward-digit groups produce sectors such as `SW1A 2`. There is no postcode-position slicing.
2. Group by sector. `transaction_count`, `median_price`, `mean_price`, `p25_price` and `p75_price` use all retained transactions, in nominal pounds, across the pooled years. Quartiles use pandas linear interpolation. No inflation, property mix, floor area or tenure adjustment is applied. Median sale price is the sole wealth metric; it describes sold housing, not household income or net worth.
3. `ew_percentile = 100 * average_rank(sector median) / number_of_observed_sectors`. Every sector with a valid observed price has equal weight, including flagged sectors and those without polygons. Tied medians share the average rank. The top unique median is 100; the minimum rank is greater than zero.
4. Validate unique, complete OA codes across the polygon and lookup files. Repair invalid geometries with Shapely `make_valid`, then dissolve by sector in EPSG:27700 (British National Grid). Export polygons as WGS84 GeoJSON. These are **approximate analysis polygons, not authoritative Royal Mail postcode boundaries**. A sector can have multiple disconnected pieces.
5. Use a spatial index to find polygon pairs. Require disjoint interiors and a shared boundary line with positive length (DE-9IM `F***1****`). Point contacts, overlaps and self-edges do not qualify. No buffering or gap bridging is applied. `adjacency.csv` stores each undirected pair once as `sector_a,sector_b,shared_boundary_m`. Edge lengths are measured in metres before GeoJSON reprojection. An edge is geographical contact, not a road/ferry connection.
6. For each sector and layer, collect every distinct sector with shortest graph distance from 1 through that layer. Exclude the subject. Take the unweighted median of available neighbouring sector medians; low-sale observed medians remain included. Calculate `pct_above_neighbourhood = median_price / neighbourhood_median - 1`.
7. `neighbour_count` includes all graph neighbours at the requested cumulative depth. `priced_neighbour_count` counts those contributing a median; `low_count_neighbour_count` reports contributors below the price-run sales threshold. Unpriced nodes remain available for traversing the graph. Missing values are never imputed. No usable neighbours gives blank neighbourhood median and premium.
8. `low_transaction_count` flags a count below `min_sales_threshold` (20 for this run). Analysis covers the union of observed price sectors and polygon sectors. `has_geometry` and `analysis_status` expose unavailable comparisons: `missing_geometry`, `missing_price` or `no_priced_neighbours`; otherwise `ok`. A 2021 best-fit lookup cannot represent every sector in later sales data. A sector with no sales has count zero and blank prices/percentile.

## Outputs and delivered coverage

- `data/`: cached source files and download metadata (kept local).
- `output/sector_wealth.csv`: observed sector statistics and low-sale flags.
- `output/sectors.geojson`: 8,087 dissolved analysis polygons (generated locally, excluded from Git because of size).
- `output/adjacency.csv`: 23,318 undirected shared-edge connections.
- `output/neighbour_analysis.csv`: 24,723 rows covering 8,241 sectors at depths 1–3.
- `output/selected.csv`: **1,607 sectors**, including **55 below 20 sales**; 1,552 have at least 20 sales.
- `output/prices_run.json`, `output/selection_run.json` and `output/run_manifest.json`: input counts, parameters, source hashes and validation results.

The 14 September 2026 run read 2,745,967 source rows and retained 2,265,966 transactions across 8,219 observed price sectors. It rejected 447 otherwise eligible rows with invalid/missing postcodes. All 188,880 OAs matched the lookup; 17 invalid OA geometries were repaired. At depth 2, 8,064 sectors have a usable comparison; 154 observed-price sectors lack polygons, 22 polygon sectors lack qualifying sales, and one priced island sector has no priced neighbours. Unavailable comparisons remain flagged in `neighbour_analysis.csv` and cannot enter the selected file.

## Attribution and reuse

See [data licences and attribution](../DATA_LICENSE.md). Original code and documentation are [MIT licensed](../LICENSE).

## Reference snapshot and fresh runs

The checked-in outputs and run_manifest.json describe the 14 September 2026 delivery at commit 68d7d3f6af96a6764d3edaf3fc2609867310062a. The manifest records the original Windows working-file bytes (CRLF) of wealth.py for that revision, along with its environment. Git stores the historical source with LF line endings; converting that blob to CRLF reproduces the recorded code digest. Later code changes do not retroactively describe that run. Stage commands do not generate or update run_manifest.json. Use a separate output directory for experiments. A later fresh source download may differ because publishers revise their files.

Run `python scripts/verify_snapshot.py` to validate the six published data files offline. Add `--include-local` to require and verify all original source files and the original generated GeoJSON too. These checks establish byte integrity, not authenticity or analytical validity; independent output tests provide a separate semantic check.

The six data-output files preserve the exact bytes recorded in the original manifest. Git text conversion is disabled for those files so Linux and Windows checkouts agree.
