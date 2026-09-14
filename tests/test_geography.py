import geopandas as gpd
import pandas as pd
import pytest
from shapely.geometry import box

import wealth


def sample_areas():
    return gpd.GeoDataFrame({"OA21CD": ["E00000001", "E00000002", "W00000001"]},
                            geometry=[box(0, 0, 1, 1), box(1, 0, 2, 1), box(2, 0, 3, 1)],
                            crs=27700)


def sample_lookup():
    return pd.DataFrame({"OA21CD": ["E00000001", "E00000002", "W00000001"],
                         "PCDS": ["E16  1", "e161", "CF10 1"]})


def test_dissolve_normalizes_sectors_and_preserves_area():
    result = wealth.dissolve_sectors(sample_areas(), sample_lookup()).set_index("sector")
    assert set(result.index) == {"E16 1", "CF10 1"}
    assert result.loc["E16 1"].geometry.area == 2
    assert result.geometry.area.sum() == 3
    assert result.crs.to_epsg() == 27700
    assert result.geometry.is_valid.all()


def test_lookup_requires_complete_unique_coverage():
    with pytest.raises(ValueError, match="coverage"):
        wealth.dissolve_sectors(sample_areas(), sample_lookup().iloc[:2])
    with pytest.raises(ValueError, match="Duplicate"):
        wealth.dissolve_sectors(sample_areas(), pd.concat([sample_lookup()] * 2))


def test_invalid_lookup_sector_and_missing_crs():
    lookup = sample_lookup()
    lookup.loc[0, "PCDS"] = "bad"
    with pytest.raises(ValueError, match="Invalid postcode"):
        wealth.dissolve_sectors(sample_areas(), lookup)
    with pytest.raises(ValueError, match="CRS"):
        wealth.dissolve_sectors(sample_areas().set_crs(None, allow_override=True), sample_lookup())


def test_adjacency_excludes_corner_isolate_overlap_and_self():
    sectors = gpd.GeoDataFrame({"sector": ["A", "B", "C", "D", "E"]}, geometry=[
        box(0, 0, 1, 1), box(1, 0, 2, 1), box(1, 1, 2, 2),
        box(10, 10, 11, 11), box(0.5, 0.25, 1.5, 0.75),
    ], crs=27700)
    edges = wealth.build_adjacency(sectors)
    assert list(zip(edges.sector_a, edges.sector_b)) == [("A", "B"), ("B", "C")]
    assert edges.shared_boundary_m.tolist() == [1.0, 1.0]


def test_adjacency_accepts_short_real_edge_and_rejects_geographic_crs():
    sectors = gpd.GeoDataFrame({"sector": ["B", "A"]}, geometry=[
        box(1, 0.999, 2, 2), box(0, 0, 1, 1),
    ], crs=27700)
    edges = wealth.build_adjacency(sectors)
    assert len(edges) == 1
    assert edges.iloc[0].shared_boundary_m == pytest.approx(0.001)
    with pytest.raises(ValueError, match="27700"):
        wealth.build_adjacency(sectors.to_crs(4326))
