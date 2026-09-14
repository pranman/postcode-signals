import csv

import pandas as pd
import pytest

import wealth


@pytest.mark.parametrize("postcode,sector", [
    ("E16 1AA", "E16 1"), ("SW1A 2AA", "SW1A 2"),
    (" w1a1aa ", "W1A 1"), ("M1 1AE", "M1 1"),
    ("B33 8TH", "B33 8"), ("CR2 6XH", "CR2 6"),
    ("DN55 1PT", "DN55 1"), ("GIR 0AA", "GIR 0"),
    ("QQ1 1AA", None), ("E16 1CI", None), ("SW1A 2", None),
    ("garbage", None), (None, None), ("E16 1AAA", None),
])
def test_postcode(postcode, sector):
    assert wealth.postcode_sector(postcode) == sector


def write_ppd(path, rows):
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        for i, row in enumerate(rows):
            values = dict(id=str(i), price="100000", date="2023-06-01 00:00",
                          postcode="E16 1AA", type="D", category="A", status="A")
            values.update(row)
            writer.writerow([values.get(col, "") for col in wealth.PPD_COLUMNS])


def test_ingestion_filters(tmp_path):
    path = tmp_path / "pp-2023.csv"
    write_ppd(path, [*[{"type": t} for t in "DSTF"], {"type": "O"},
                    {"category": "B"}, {"postcode": "invalid"}, {"price": "0"},
                    {"price": "nan"}, {"price": "inf"}, {"status": "D"},
                    {"date": "2022-01-01"}, {"date": "bad"}])
    sales, audit = wealth.read_transactions([path], [2023])
    assert sales.sector.tolist() == ["E16 1"] * 4
    assert audit == dict(source_rows=13, eligible_rows=5, invalid_postcode_rows=1, accepted_rows=4)


def test_cache_never_requests_existing_source(tmp_path, monkeypatch):
    path = tmp_path / "source.csv"
    path.write_text("cached")
    monkeypatch.setattr(wealth.requests, "Session", lambda: pytest.fail("network called"))
    assert wealth.download("https://example.test/data", path) == path


def test_failed_download_does_not_poison_cache(tmp_path, monkeypatch):
    class Response:
        status_code = 200
        headers = {"Content-Length": "20"}
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def raise_for_status(self): pass
        def iter_content(self, size): yield b"short"
    monkeypatch.setattr(wealth.requests.Session, "get", lambda *a, **k: Response())
    path = tmp_path / "source.csv"
    with pytest.raises(ValueError, match="Incomplete"):
        wealth.download("https://example.test/data", path)
    assert not path.exists()
    assert not path.with_suffix(".csv.part").exists()
