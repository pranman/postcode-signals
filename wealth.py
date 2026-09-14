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
