"""Relative postcode-sector affluence from residential sale prices."""

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

PRICE_URL = "https://price-paid-data.publicdata.landregistry.gov.uk/pp-{year}.csv"
# Standard UK outward-code forms and restricted inward-code letters.
OUTWARD = r"(?:[A-PR-UWYZ][0-9]{1,2}|[A-PR-UWYZ][A-HK-Y][0-9]{1,2}|[A-PR-UWYZ][0-9][A-HJKPSTUW]|[A-PR-UWYZ][A-HK-Y][0-9][ABEHMNPRVWXY])"
POSTCODE = re.compile(rf"^(?P<outward>{OUTWARD})\s*(?P<inward>[0-9])[ABD-HJLNP-UW-Z]{{2}}$")
SECTOR = re.compile(rf"^({OUTWARD})\s*([0-9])$")
PPD_COLUMNS = [
    "id", "price", "date", "postcode", "type", "new_build", "tenure",
    "paon", "saon", "street", "locality", "town", "district", "county",
    "category", "status",
]


def postcode_sector(value):
    """Return a canonical sector, or None for an invalid/missing full postcode."""
    if not isinstance(value, str):
        return None
    value = value.strip().upper()
    if re.fullmatch(r"GIR\s*0AA", value):
        return "GIR 0"
    match = POSTCODE.fullmatch(value)
    return f"{match['outward']} {match['inward']}" if match else None


def download(url, path):
    """Cache complete downloads atomically, with retries and source metadata."""
    path = Path(path)
    if path.exists() and path.stat().st_size:
        print(f"Using cached {path}", flush=True)
        return path
    path.parent.mkdir(parents=True, exist_ok=True)
    part = path.with_name(path.name + ".part")
    session = requests.Session()
    session.mount("https://", HTTPAdapter(max_retries=Retry(
        total=5, backoff_factor=1, status_forcelist=[429, 500, 502, 503, 504]
    )))
    print(f"Downloading {url}", flush=True)
    try:
        with session.get(url, stream=True, timeout=(30, 180)) as response:
            response.raise_for_status()
            if response.status_code != 200:
                raise ValueError(f"Download is not ready: HTTP {response.status_code}: {url}")
            content_type = response.headers.get("Content-Type", "")
            if "text/html" in content_type or "application/json" in content_type:
                raise ValueError(f"Expected a data file, received {content_type}: {url}")
            with part.open("wb") as handle:
                for chunk in response.iter_content(1024 * 1024):
                    handle.write(chunk)
            expected = response.headers.get("Content-Length")
            if not part.stat().st_size or (expected and not response.headers.get("Content-Encoding")
                                          and part.stat().st_size != int(expected)):
                raise ValueError(f"Incomplete download: {url}")
            part.replace(path)
            path.with_suffix(path.suffix + ".json").write_text(json.dumps({
                "url": url, "resolved_url": response.url,
                "downloaded_at": datetime.now(timezone.utc).isoformat(),
                "bytes": path.stat().st_size,
                "last_modified": response.headers.get("Last-Modified"),
                "etag": response.headers.get("ETag"),
            }, indent=2), encoding="utf-8")
    finally:
        part.unlink(missing_ok=True)
        session.close()
    return path


def read_transactions(paths, years):
    """Read current yearly snapshots; monthly change files are not supported."""
    frames = []
    audit = {"source_rows": 0, "eligible_rows": 0, "invalid_postcode_rows": 0}
    for path in paths:
        print(f"Reading {path}", flush=True)
        for chunk in pd.read_csv(path, names=PPD_COLUMNS, header=None,
                                 usecols=[1, 2, 3, 4, 14, 15], dtype=str,
                                 chunksize=200_000, keep_default_na=False):
            audit["source_rows"] += len(chunk)
            price = pd.to_numeric(chunk.price, errors="coerce")
            dates = pd.to_datetime(chunk.date, errors="coerce")
            eligible = (chunk.category.eq("A") & chunk.type.isin(list("DSTF"))
                        & chunk.status.ne("D") & price.gt(0) & price.lt(float("inf"))
                        & dates.dt.year.isin(years))
            chosen = chunk.loc[eligible, ["postcode"]].copy()
            chosen["price"] = price[eligible]
            chosen["sector"] = chosen.postcode.map(postcode_sector)
            audit["eligible_rows"] += len(chosen)
            audit["invalid_postcode_rows"] += int(chosen.sector.isna().sum())
            frames.append(chosen.dropna(subset=["sector"])[["sector", "price"]])
    sales = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame(columns=["sector", "price"])
    audit["accepted_rows"] = len(sales)
    print(json.dumps(audit), flush=True)
    if sales.empty:
        raise ValueError("No qualifying residential transactions in the requested years")
    return sales, audit


def aggregate_prices(sales, min_sales=20):
    """Keep all observed sectors; rank sector medians equally across E&W."""
    grouped = sales.groupby("sector").price
    result = grouped.agg(transaction_count="count", median_price="median", mean_price="mean")
    result["p25_price"] = grouped.quantile(0.25)
    result["p75_price"] = grouped.quantile(0.75)
    result["ew_percentile"] = result.median_price.rank(method="average", pct=True) * 100
    result["low_transaction_count"] = result.transaction_count.lt(min_sales)
    result["min_sales_threshold"] = min_sales
    return result.reset_index()


def prices_command(args):
    years = sorted(set(args.years))
    paths = [download(PRICE_URL.format(year=y), args.data_dir / f"pp-{y}.csv") for y in years]
    sales, audit = read_transactions(paths, years)
    result = aggregate_prices(sales, args.min_sales)
    result.to_csv(args.output_dir / "sector_wealth.csv", index=False)
    (args.output_dir / "prices_run.json").write_text(json.dumps({
        "years": years, "min_sales": args.min_sales, "sectors": len(result), **audit,
    }, indent=2), encoding="utf-8")
    print(f"Wrote {len(result):,} sectors to {args.output_dir / 'sector_wealth.csv'}")


OA_URL = "https://open-geography-portalx-ons.hub.arcgis.com/api/download/v1/items/6beafcfd9b9c4c9993a06b6b199d7e6d/shapefile?layers=0"
LOOKUP_URL = "https://open-geography-portalx-ons.hub.arcgis.com/api/download/v1/items/cf826bd3d29947ef9dcda7cd9753f7a8/csv?layers=0"


def normalize_sector(value):
    if not isinstance(value, str):
        return None
    match = SECTOR.fullmatch(value.strip().upper())
    return f"{match[1]} {match[2]}" if match else None


def dissolve_sectors(areas, lookup):
    """Validate OA coverage before dissolving; never silently drop an OA."""
    areas = areas.rename(columns={c: c.upper() for c in areas.columns if c != "geometry"})
    lookup = lookup.rename(columns=str.upper)
    sector_column = next((c for c in ["PCDS21CD", "PCDS"] if c in lookup), None)
    if "OA21CD" not in areas or "OA21CD" not in lookup or sector_column is None:
        raise ValueError("Expected OA21CD and PCDS21CD (or PCDS) source fields")
    if areas.crs is None:
        raise ValueError("Output Area polygons must declare a CRS")
    if areas.OA21CD.isna().any() or lookup.OA21CD.isna().any():
        raise ValueError("Missing OA codes")
    if areas.OA21CD.duplicated().any() or lookup.OA21CD.duplicated().any():
        raise ValueError("Duplicate OA codes in boundaries or lookup")
    if not areas.OA21CD.str.match(r"^[EW][0-9]{8}$").all():
        raise ValueError("Expected only England/Wales Output Areas")
    if set(areas.OA21CD) != set(lookup.OA21CD):
        raise ValueError("OA coverage differs between boundaries and lookup")
    lookup = lookup[["OA21CD", sector_column]].copy()
    lookup["sector"] = lookup[sector_column].map(normalize_sector)
    if lookup.sector.isna().any():
        bad = lookup.loc[lookup.sector.isna(), sector_column].unique()[:10]
        raise ValueError(f"Invalid postcode sectors in lookup: {bad}")
    areas = areas[["OA21CD", "geometry"]].to_crs(27700)

    if areas.geometry.isna().any() or areas.geometry.is_empty.any():
        raise ValueError("Missing or empty OA polygons")
    invalid = ~areas.geometry.is_valid
    if invalid.any():
        print(f"Repairing {invalid.sum():,} invalid OA geometries", flush=True)
        areas.loc[invalid, "geometry"] = areas.loc[invalid, "geometry"].make_valid()
    if not areas.geom_type.isin(["Polygon", "MultiPolygon"]).all():
        raise ValueError("OA geometries must be polygonal after repair")
    joined = areas.merge(lookup[["OA21CD", "sector"]], on="OA21CD", validate="one_to_one")
    print(f"Dissolving {len(joined):,} Output Areas into sectors", flush=True)
    sectors = joined[["sector", "geometry"]].dissolve(by="sector", as_index=False)
    if not sectors.geometry.is_valid.all():
        raise ValueError("Invalid dissolved sector polygons")
    return sectors.sort_values("sector").reset_index(drop=True)


def geography_command(args):
    import geopandas as gpd

    oa_path = args.oa_file or download(OA_URL, args.data_dir / "oa21_ew_bgc_v2.zip")
    lookup_path = args.lookup_file or download(LOOKUP_URL, args.data_dir / "oa21_pcds21.csv")
    print(f"Reading Output Area polygons from {oa_path}", flush=True)
    areas = gpd.read_file(oa_path)
    lookup = pd.read_csv(lookup_path, dtype=str)
    sectors = dissolve_sectors(areas, lookup)
    sectors.to_crs(4326).to_file(args.output_dir / "sectors.geojson", driver="GeoJSON")
    print(f"Wrote {len(sectors):,} sector polygons", flush=True)
    edges = build_adjacency(sectors)
    edges.to_csv(args.output_dir / "adjacency.csv", index=False)
    print(f"Wrote {len(edges):,} adjacency edges", flush=True)
    return sectors


def build_adjacency(sectors):
    """Rook adjacency: disjoint interiors and positive shared boundary length."""
    import shapely

    if sectors.crs is None or sectors.crs.to_epsg() != 27700:
        raise ValueError("Adjacency requires EPSG:27700 metre coordinates")
    if sectors.sector.duplicated().any() or not sectors.geometry.is_valid.all():
        raise ValueError("Adjacency requires unique sectors and valid polygons")
    sectors = sectors.sort_values("sector").reset_index(drop=True)
    geoms = sectors.geometry.array
    left, right = sectors.sindex.query(geoms, predicate="intersects")
    keep = left < right
    left, right = left[keep], right[keep]
    # DE-9IM: interiors do not intersect and boundaries intersect in a line.
    edges = shapely.relate_pattern(geoms[left], geoms[right], "F***1****")
    left, right = left[edges], right[edges]
    lengths = shapely.length(shapely.intersection(
        shapely.boundary(geoms[left]), shapely.boundary(geoms[right])))
    names = sectors.sector.to_numpy()
    result = pd.DataFrame({"sector_a": names[left], "sector_b": names[right],
                           "shared_boundary_m": lengths})
    return result.loc[result.shared_boundary_m.gt(0)].sort_values(
        ["sector_a", "sector_b"]).reset_index(drop=True)
