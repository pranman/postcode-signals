"""Independently audit delivered CSVs using set expansion instead of NetworkX."""
import json
from collections import defaultdict
from decimal import Decimal
from pathlib import Path
from statistics import median

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1] / "output"


def test_delivered_outputs_are_complete_and_consistent():
    if not (ROOT / "selected.csv").exists():
        pytest.skip("National pipeline has not been run")
    prices = pd.read_csv(ROOT / "sector_wealth.csv").set_index("sector")
    analysis = pd.read_csv(ROOT / "neighbour_analysis.csv")
    edges = pd.read_csv(ROOT / "adjacency.csv")
    selected = pd.read_csv(ROOT / "selected.csv")
    selection = json.loads((ROOT / "selection_run.json").read_text())
    assert prices.index.is_unique
    assert not analysis.duplicated(["sector", "layer"]).any()
    assert not edges.duplicated(["sector_a", "sector_b"]).any()
    assert edges.sector_a.lt(edges.sector_b).all()
    assert edges.shared_boundary_m.gt(0).all()
    assert prices.p25_price.le(prices.median_price).all()
    assert prices.p75_price.ge(prices.median_price).all()
    pd.testing.assert_series_equal(prices.ew_percentile,
        (prices.median_price.rank(pct=True, method="average") * 100).rename("ew_percentile"))
    links = defaultdict(set)
    for edge in edges.itertuples():
        links[edge.sector_a].add(edge.sector_b)
        links[edge.sector_b].add(edge.sector_a)
    medians = prices.median_price.to_dict()
    for sector, rows in analysis.groupby("sector", sort=False):
        seen = {sector}
        frontier = {sector}
        depth = 0
        for row in rows.sort_values("layer").itertuples():
            while depth < row.layer:
                frontier = {n for node in frontier for n in links[node]} - seen
                seen.update(frontier)
                depth += 1
            neighbours = seen - {sector}
            observations = [medians[n] for n in neighbours if n in medians]
            assert row.neighbour_count == len(neighbours), (sector, row.layer)
            assert row.priced_neighbour_count == len(observations)
            if observations:
                baseline = median(observations)
                assert row.neighbourhood_median == baseline
                if sector in medians:
                    assert row.pct_above_neighbourhood == pytest.approx(medians[sector] / baseline - 1)
            else:
                assert pd.isna(row.neighbourhood_median)
                assert pd.isna(row.pct_above_neighbourhood)
            if sector in prices.index:
                assert row.median_price == prices.at[sector, "median_price"]
                assert row.transaction_count == prices.at[sector, "transaction_count"]
            else:
                assert pd.isna(row.median_price)
                assert row.transaction_count == 0
            assert row.low_transaction_count == (row.transaction_count < row.min_sales_threshold)
    assert analysis.groupby("sector").size().eq(analysis.layer.nunique()).all()
    expected = set()
    for row in analysis[analysis.layer.eq(selection["layer"])].itertuples():
        if pd.notna(row.median_price) and pd.notna(row.neighbourhood_median):
            if (row.transaction_count >= selection["min_sales"]
                and selection["min_percentile"] <= row.ew_percentile <= selection["max_percentile"]
                and Decimal(str(row.median_price)) > (Decimal(1) + Decimal(str(selection["above"]))) * Decimal(str(row.neighbourhood_median))):
                expected.add(row.sector)
    assert set(selected.sector) == expected
    assert selected.sector.is_unique
    assert selected.layer.eq(selection["layer"]).all()
    assert selected.analysis_status.eq("ok").all()
    assert selected.pct_above_neighbourhood.is_monotonic_decreasing
    pd.testing.assert_frame_equal(
        selected.sort_values("sector").reset_index(drop=True),
        analysis[analysis.layer.eq(selection["layer"]) & analysis.sector.isin(expected)].sort_values("sector").reset_index(drop=True),
    )
