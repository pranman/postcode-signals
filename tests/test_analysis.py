import pandas as pd
import pytest

import wealth


def fixture_prices():
    return wealth.aggregate_prices(pd.DataFrame({
        "sector": ["A", "B", "C", "D", "Z"], "price": [1000, 100, 300, 900, 700],
    }), min_sales=2)


def test_cumulative_shortest_paths_exclude_self_and_deduplicate_cycles():
    edges = pd.DataFrame({"sector_a": ["A", "B", "C", "D", "C"],
                          "sector_b": ["B", "C", "D", "B", "U"]})
    result = wealth.analyse_neighbourhoods(fixture_prices(), list("ABCDUI"), edges, [3, 1, 2])
    a = result[result.sector.eq("A")].set_index("layer")
    assert a.neighbour_count.tolist() == [1, 3, 4]
    assert a.priced_neighbour_count.tolist() == [1, 3, 3]
    assert a.neighbourhood_median.tolist() == [100, 300, 300]
    assert a.loc[2, "pct_above_neighbourhood"] == pytest.approx(1000 / 300 - 1)
    assert a.loc[2, "low_count_neighbour_count"] == 3
    assert a.low_transaction_count.all()
    z = result[result.sector.eq("Z")]
    assert z.analysis_status.eq("missing_geometry").all()
    assert z.pct_above_neighbourhood.isna().all()
    isolate = result[result.sector.eq("I")]
    assert isolate.transaction_count.eq(0).all()
    assert isolate.median_price.isna().all()
    assert isolate.neighbour_count.eq(0).all()


def test_unpriced_sectors_remain_in_graph_paths():
    edges = pd.DataFrame({"sector_a": ["A", "U"], "sector_b": ["U", "B"]})
    result = wealth.analyse_neighbourhoods(fixture_prices(), ["A", "U", "B", "D"], edges, [1, 2])
    a = result[result.sector.eq("A")].set_index("layer")
    assert a.loc[1, "analysis_status"] == "no_priced_neighbours"
    assert pd.isna(a.loc[1, "neighbourhood_median"])
    assert a.loc[2, "neighbourhood_median"] == 100
    assert a.loc[2, "neighbour_count"] == 2
    assert a.loc[2, "priced_neighbour_count"] == 1
    u = result[result.sector.eq("U")]
    assert u.median_price.isna().all()
    assert u.analysis_status.eq("missing_price").all()


def test_graph_validation():
    with pytest.raises(ValueError, match="unknown"):
        wealth.analyse_neighbourhoods(fixture_prices(), ["A"],
                                     pd.DataFrame({"sector_a": ["A"], "sector_b": ["B"]}), [1])


@pytest.mark.parametrize("threshold", [3, 0, 1.5, float("nan"), float("inf")])
def test_analysis_rejects_mixed_or_invalid_price_thresholds(threshold):
    prices = fixture_prices().astype({"min_sales_threshold": float})
    prices.loc[0, "min_sales_threshold"] = threshold
    edges = pd.DataFrame({"sector_a": ["A"], "sector_b": ["B"]})
    with pytest.raises(ValueError, match="one positive integer min_sales_threshold"):
        wealth.analyse_neighbourhoods(prices, ["A", "B"], edges, [1])


def test_analysis_rejects_empty_prices():
    edges = pd.DataFrame({"sector_a": [], "sector_b": []})
    with pytest.raises(ValueError, match="No price sectors"):
        wealth.analyse_neighbourhoods(fixture_prices().iloc[:0], ["A"], edges, [1])
