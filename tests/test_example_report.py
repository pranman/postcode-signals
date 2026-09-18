"""Exercise the offline showcase using tiny synthetic CSVs, without downloads."""
import csv
from decimal import Decimal

import pytest

from examples import area_shortlist


@pytest.fixture
def analysis_csv(tmp_path):
    columns = sorted(area_shortlist.REQUIRED_COLUMNS)
    base = dict(sector="A 1", layer=2, transaction_count=20, median_price="120.01",
                neighbourhood_median="100", ew_percentile="75", neighbour_count=3,
                priced_neighbour_count=2, low_count_neighbour_count=1,
                min_sales_threshold=20, analysis_status="ok")
    rows = [
        {**base, "sector": "OUTLIER 1", "transaction_count": 1, "median_price": "900"},
        {**base, "sector": "BOUNDARY 1", "median_price": "120"},
        {**base, "sector": "B 1", "median_price": "150", "transaction_count": 30},
        {**base, "sector": "A 1", "median_price": "150"},
        {**base, "sector": "FLOOR 1"},
        {**base, "sector": "MISSING 1", "analysis_status": "missing_geometry",
         "neighbourhood_median": "", "neighbour_count": 0, "priced_neighbour_count": 0,
         "low_count_neighbour_count": 0},
        {**base, "sector": "A 1", "layer": 1},
    ]
    path = tmp_path / "analysis.csv"
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)
    return path


def test_strict_boundary_sales_floor_and_stable_ties(analysis_csv):
    rows = area_shortlist.read_sectors(analysis_csv, 2)
    assert len(rows) == 6
    baseline = area_shortlist.shortlist(rows, Decimal("0.20"), 1)
    filtered = area_shortlist.shortlist(list(reversed(rows)), Decimal("0.20"), 20)
    assert [row.sector for row in baseline] == ["OUTLIER 1", "A 1", "B 1", "FLOOR 1"]
    assert [row.sector for row in filtered] == ["A 1", "B 1", "FLOOR 1"]


def test_report_counts_quality_and_bounded_examples(analysis_csv, tmp_path):
    destination = tmp_path / "report.md"
    assert area_shortlist.main(["--input", str(analysis_csv), "--output", str(destination), "--limit", "2"]) == 0
    text = destination.read_text(encoding="utf-8")
    assert "| Baseline: at least 1 sale | 4 | 80.0% |" in text
    assert "| Shortlist: at least 20 sales | 3 | 60.0% |" in text
    assert "**1 of 4 baseline candidates (25.0%)**" in text
    assert "**5 (83.3%)** have a usable comparison" in text
    assert "| `missing_geometry` | 1 |" in text
    assert "**3 of 3 shortlist sectors (100.0%)** have at least one low-sale neighbour" in text
    assert "**3 of 3 shortlist sectors (100.0%)** have graph neighbours without a usable price" in text
    assert "top 2 of 3 shortlist sectors" in text
    assert "| A 1 | 20 | £150 | £100 | 50.0% | 75.0 | 2 / 3 | 1 |" in text
    assert "OUTLIER 1" not in text
    assert "| FLOOR 1 |" not in text
    assert "Input SHA-256:" in text
    first_bytes = destination.read_bytes()
    area_shortlist.main(["--input", str(analysis_csv), "--output", str(destination), "--limit", "2"])
    assert destination.read_bytes() == first_bytes


def test_empty_shortlist_is_reported_without_division_by_zero(analysis_csv, tmp_path):
    destination = tmp_path / "empty.md"
    area_shortlist.main(["--input", str(analysis_csv), "--output", str(destination), "--above", "10"])
    text = destination.read_text(encoding="utf-8")
    assert "| Shortlist: at least 20 sales | 0 | 0.0% | n/a | n/a | n/a |" in text
    assert "No sectors meet the requested shortlist rule." in text


@pytest.mark.parametrize("arguments", [
    ["--min-sales", "0"], ["--layer", "0"], ["--limit", "21"],
    ["--above", "NaN"], ["--above", "-0.1"], ["--above", "Infinity"], ["--above", "invalid"],
])
def test_invalid_options_fail_before_writing(arguments, tmp_path):
    destination = tmp_path / "report.md"
    with pytest.raises(SystemExit) as error:
        area_shortlist.main(["--output", str(destination), *arguments])
    assert error.value.code == 2
    assert not destination.exists()


def test_input_cannot_be_overwritten(analysis_csv):
    original = analysis_csv.read_bytes()
    with pytest.raises(SystemExit):
        area_shortlist.main(["--input", str(analysis_csv), "--output", str(analysis_csv)])
    assert analysis_csv.read_bytes() == original


def test_missing_columns_and_absent_layer_fail_clearly(analysis_csv, tmp_path):
    malformed = tmp_path / "malformed.csv"
    malformed.write_text("sector,layer\nA 1,2\n", encoding="utf-8")
    with pytest.raises(ValueError, match="Missing required columns"):
        area_shortlist.read_sectors(malformed, 2)
    with pytest.raises(ValueError, match="No sectors found for layer 3"):
        area_shortlist.read_sectors(analysis_csv, 3)


def test_duplicate_sector_is_rejected(analysis_csv):
    text = analysis_csv.read_text(encoding="utf-8")
    analysis_csv.write_text(text + text.splitlines()[1] + "\n", encoding="utf-8")
    with pytest.raises(ValueError, match="duplicate sector"):
        area_shortlist.read_sectors(analysis_csv, 2)


@pytest.mark.parametrize("field,value,reason", [
    ("median_price", "NaN", "finite and positive"),
    ("neighbourhood_median", "0", "finite and positive"),
    ("priced_neighbour_count", "4", "neighbour counts are inconsistent"),
    ("transaction_count", "0", "comparable sectors require"),
])
def test_invalid_comparable_row_is_rejected(analysis_csv, field, value, reason):
    with analysis_csv.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        fields = reader.fieldnames
        rows = list(reader)
    rows[0][field] = value
    with analysis_csv.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    with pytest.raises(ValueError, match=reason):
        area_shortlist.read_sectors(analysis_csv, 2)
