from pathlib import Path
import subprocess
import sys

import geopandas as gpd
import pandas as pd
import pytest
from shapely.geometry import box

import wealth
from test_prices import write_ppd


def test_strict_threshold_and_inclusive_filters():
    frame = pd.DataFrame({
        "sector": ["A", "B", "C", "D"], "layer": [2] * 4,
        "median_price": [114, 115, 150, 200], "neighbourhood_median": [100] * 4,
        "transaction_count": [20, 20, 19, 50], "ew_percentile": [70, 70, 80, 100],
        "pct_above_neighbourhood": [0.14000000000000012, 0.15, 0.5, 1],
    })
    selected = wealth.select_sectors(frame, 2, 0.14, 20, 70, 100)
    assert selected.sector.tolist() == ["D", "B"]
    assert wealth.select_sectors(frame, 2, 1.0, 1).empty
    with pytest.raises(ValueError, match="has not been analysed"):
        wealth.select_sectors(frame, layer=3)
    with pytest.raises(ValueError, match="cannot exceed"):
        wealth.select_sectors(frame, min_percentile=80, max_percentile=70)


def test_cli_end_to_end_from_cached_sources(tmp_path):
    data = tmp_path / "data"
    output = tmp_path / "output"
    data.mkdir()
    write_ppd(data / "pp-2023.csv", [
        {"postcode": "E16 1AA", "price": "200000"},
        {"postcode": "E16 2AA", "price": "100000"},
        {"postcode": "E16 3AA", "price": "100000"},
    ])
    areas = gpd.GeoDataFrame({"OA21CD": ["E00000001", "E00000002", "E00000003"]},
                            geometry=[box(500000 + i*100, 200000, 500100 + i*100, 200100)
                                      for i in range(3)], crs=27700)
    oa = data / "oa.gpkg"
    areas.to_file(oa)
    lookup = data / "lookup.csv"
    pd.DataFrame({"OA21CD": areas.OA21CD, "PCDS21CD": ["E16 1", "E16 2", "E16 3"]}).to_csv(lookup, index=False)
    script = str(Path(wealth.__file__).resolve())
    def run(*args):
        return subprocess.run([sys.executable, script, *args, "--data-dir", str(data),
                               "--output-dir", str(output)], capture_output=True, text=True, check=True)
    run("prices", "--years", "2023", "2023", "--min-sales", "20")
    run("geography", "--oa-file", str(oa), "--lookup-file", str(lookup))
    run("analyse", "--layers", "1", "2", "3")
    run("select", "--layer", "2", "--above", "0.20", "--min-sales", "1")
    selected = pd.read_csv(output / "selected.csv")
    assert selected.sector.tolist() == ["E16 1"]
    assert selected.iloc[0].neighbourhood_median == 100000
    assert selected.iloc[0].neighbour_count == 2
    assert selected.iloc[0].pct_above_neighbourhood == 1
    assert selected.low_transaction_count.all()
    assert pd.read_csv(output / "sector_wealth.csv").transaction_count.sum() == 3
    assert len(pd.read_csv(output / "neighbour_analysis.csv")) == 9
    assert len(pd.read_csv(output / "adjacency.csv")) == 2
    assert len(gpd.read_file(output / "sectors.geojson")) == 3
    run("select", "--layer", "2", "--above", "0.20", "--min-sales", "20")
    assert pd.read_csv(output / "selected.csv").empty


@pytest.mark.parametrize("args", [
    ["analyse", "--layers", "0"], ["select", "--above", "nan"],
    ["select", "--min-percentile", "101"], ["prices", "--years", "1990"],
])
def test_cli_rejects_invalid_arguments(args):
    with pytest.raises(SystemExit) as error:
        wealth.main(args)
    assert error.value.code == 2
