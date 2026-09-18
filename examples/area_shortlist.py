"""Build an offline decision-support report from the committed sector analysis.

Run from the repository root: python examples/area_shortlist.py
Uses only the Python standard library; never downloads or changes pipeline outputs.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import os
from collections import Counter
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path
from statistics import median


@dataclass(frozen=True)
class Sector:
    sector: str
    transaction_count: int
    median_price: Decimal | None
    neighbourhood_median: Decimal | None
    ew_percentile: Decimal | None
    neighbour_count: int
    priced_neighbour_count: int
    low_count_neighbour_count: int
    min_sales_threshold: int
    analysis_status: str

    @property
    def premium(self) -> Decimal:
        assert self.median_price is not None and self.neighbourhood_median is not None
        return self.median_price / self.neighbourhood_median - 1


STATUSES = ("ok", "missing_geometry", "missing_price", "no_priced_neighbours")
DECIMAL_FIELDS = {"median_price", "neighbourhood_median", "ew_percentile"}
COUNT_FIELDS = {
    "transaction_count", "neighbour_count", "priced_neighbour_count",
    "low_count_neighbour_count", "min_sales_threshold",
}
REQUIRED_COLUMNS = {"sector", "layer", "analysis_status"} | DECIMAL_FIELDS | COUNT_FIELDS


def read_sectors(path: Path, layer: int) -> list[Sector]:
    """Read one graph depth, rejecting malformed or ambiguous source rows."""
    sectors = []
    seen = set()
    with path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        missing = REQUIRED_COLUMNS - set(reader.fieldnames or [])
        if missing:
            raise ValueError(f"Missing required columns: {', '.join(sorted(missing))}")
        for line, raw in enumerate(reader, start=2):
            try:
                if int(raw["layer"]) != layer:
                    continue
                name = raw["sector"].strip()
                if not name or name in seen:
                    raise ValueError("empty or duplicate sector at the requested layer")
                counts = {field: int(raw[field]) for field in COUNT_FIELDS}
                if any(value < 0 for value in counts.values()):
                    raise ValueError("counts must be nonnegative")
                values = {
                    field: Decimal(raw[field]) if raw[field] else None
                    for field in DECIMAL_FIELDS
                }
                if any(value is not None and (not value.is_finite() or value <= 0)
                       for value in values.values()):
                    raise ValueError("prices and percentiles must be finite and positive")
                if values["ew_percentile"] is not None and values["ew_percentile"] > 100:
                    raise ValueError("percentile must not exceed 100")
                if not (counts["low_count_neighbour_count"] <= counts["priced_neighbour_count"]
                        <= counts["neighbour_count"]):
                    raise ValueError("neighbour counts are inconsistent")
                status = raw["analysis_status"]
                if status not in STATUSES:
                    raise ValueError(f"unknown analysis status: {status}")
                if status == "ok" and (any(value is None for value in values.values())
                                       or counts["transaction_count"] == 0
                                       or counts["priced_neighbour_count"] == 0):
                    raise ValueError("comparable sectors require prices, sales and priced neighbours")
                sectors.append(Sector(name, **counts, **values, analysis_status=status))
                seen.add(name)
            except (ValueError, TypeError, AttributeError, InvalidOperation) as exc:
                raise ValueError(f"Invalid source row {line}: {exc}") from exc
    if not sectors:
        raise ValueError(f"No sectors found for layer {layer}")
    return sectors


def shortlist(sectors: list[Sector], above: Decimal, min_sales: int) -> list[Sector]:
    """Apply the strict price threshold before ranking; break ties by sector."""
    candidates = [
        row for row in sectors
        if row.analysis_status == "ok"
        and row.transaction_count >= min_sales
        and row.median_price > (1 + above) * row.neighbourhood_median
    ]
    return sorted(candidates, key=lambda row: (-row.premium, row.sector))


def share(part: int, total: int) -> str:
    return f"{100 * part / total:.1f}%" if total else "n/a"


def money(value: Decimal) -> str:
    return f"£{value:,.0f}"


def cohort_line(label: str, rows: list[Sector], comparable_count: int) -> str:
    if not rows:
        return f"| {label} | 0 | {share(0, comparable_count)} | n/a | n/a | n/a |"
    return (
        f"| {label} | {len(rows):,} | {share(len(rows), comparable_count)} "
        f"| {median(row.transaction_count for row in rows):,.0f} "
        f"| {money(median(row.median_price for row in rows))} "
        f"| {100 * median(row.premium for row in rows):.1f}% |"
    )


def markdown_cell(value: str) -> str:
    return value.replace("\\", "\\\\").replace("|", "\\|").replace("\n", " ").replace("\r", " ")


def decimal_argument(value: str) -> Decimal:
    try:
        return Decimal(value)
    except InvalidOperation as exc:
        raise argparse.ArgumentTypeError("must be a decimal fraction, such as 0.20") from exc


def report(sectors: list[Sector], *, layer: int, above: Decimal, min_sales: int,
           limit: int, source: Path, destination: Path) -> str:
    baseline = shortlist(sectors, above, 1)
    filtered = shortlist(sectors, above, min_sales)
    statuses = Counter(row.analysis_status for row in sectors)
    comparable_count = statuses["ok"]
    removed = len(baseline) - len(filtered)
    flagged_neighbours = sum(row.low_count_neighbour_count > 0 for row in filtered)
    incomplete_neighbours = sum(row.priced_neighbour_count < row.neighbour_count for row in filtered)
    thresholds = ", ".join(str(value) for value in sorted({row.min_sales_threshold for row in sectors}))
    source_link = Path(os.path.relpath(source, destination.parent)).as_posix()
    digest = hashlib.sha256(source.read_bytes()).hexdigest()
    lines = [
        "# Geographic campaign test shortlist", "",
        "An offline example of turning area-level housing data into a reviewable market-research decision. "
        "It identifies postcode sectors with higher recorded median sale prices than their surrounding sectors. "
        "It does not estimate individual income or wealth, audience size, campaign response or marketing lift.", "",
        "## Decision and selection rule", "",
        "Use the shortlist to propose geographies for a controlled campaign test or to compare local market conditions. "
        "Validate customer demand, service coverage, channel reach and unit economics before allocating a budget.", "",
        f"Select a sector when its median sold-home price is **strictly more than {100 * above:g}%** above "
        f"the unweighted median of available sector medians within **{layer} cumulative graph steps**, "
        f"excluding itself. Compare the baseline (at least 1 sale) with a shortlist requiring **at least {min_sales} sales**. "
        "No national-percentile restriction is applied.", "",
        "| Cohort | Sectors | Share of comparable sectors | Median sales per sector | Median of sector prices | Median local premium |",
        "| --- | ---: | ---: | ---: | ---: | ---: |",
        cohort_line("Baseline: at least 1 sale", baseline, comparable_count),
        cohort_line(f"Shortlist: at least {min_sales} sales", filtered, comparable_count), "",
        f"The sales floor removes **{removed:,} of {len(baseline):,} baseline candidates "
        f"({share(removed, len(baseline))})**. It reduces exposure to sparse observations; "
        "it is not a confidence interval or proof of stability. Cohort medians give each sector equal weight.", "",
        "## Coverage and quality", "",
        f"At graph depth {layer}, the source contains **{len(sectors):,} sectors**. "
        f"**{comparable_count:,} ({share(comparable_count, len(sectors))})** have a usable comparison. "
        "Unavailable comparisons are excluded from both cohorts.", "",
        "| Analysis status | Sectors |", "| --- | ---: |",
    ]
    lines.extend(f"| `{status}` | {statuses[status]:,} |" for status in STATUSES)
    lines.extend([
        "", f"- **{flagged_neighbours:,} of {len(filtered):,} shortlist sectors "
        f"({share(flagged_neighbours, len(filtered))})** have at least one low-sale neighbour contributing to their comparison.",
        f"- **{incomplete_neighbours:,} of {len(filtered):,} shortlist sectors "
        f"({share(incomplete_neighbours, len(filtered))})** have graph neighbours without a usable price.",
        f"- Neighbour low-count flags use the source price-run threshold(s): **{thresholds} sales**. "
        "The subject-sector sales floor does not filter neighbours or recompute their medians.",
        "- Prices are nominal pooled sale prices, with no adjustment for property mix, inflation, floor area or tenure. "
        "Sector polygons are approximations; shared borders are not travel connections.", "",
        f"## Bounded examples: top {min(limit, len(filtered)):,} of {len(filtered):,} shortlist sectors", "",
        "Ordered by local price premium, with sector name as the tie-breaker. These are examples for investigation, "
        "not recommended audiences. The sales floor applies to every displayed row.", "",
        "| Sector | Sales | Median sale price | Neighbour median | Local premium | E&W percentile | Priced / all neighbours | Low-sale neighbours |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ])
    for row in filtered[:limit]:
        lines.append(
            f"| {markdown_cell(row.sector)} | {row.transaction_count:,} | {money(row.median_price)} "
            f"| {money(row.neighbourhood_median)} | {100 * row.premium:.1f}% | {row.ew_percentile:.1f} "
            f"| {row.priced_neighbour_count:,} / {row.neighbour_count:,} | {row.low_count_neighbour_count:,} |"
        )
    if not filtered:
        lines.extend(["", "No sectors meet the requested shortlist rule."])
    lines.extend([
        "", "## From shortlist to an experiment", "",
        "1. Join sector-level business measures such as aggregate demand, delivery coverage and acquisition cost; "
        "review missing coverage and sparse neighbour comparisons.",
        "2. Form comparable geographic test and control groups. Account for adjacent-area spillover and "
        "channel targeting resolution; choose the allocation before seeing outcomes.",
        "3. Predefine a success measure, budget and stopping rule. Measure incremental conversions or contribution "
        "against the control, then decide whether to expand, revise or stop.",
        "4. Keep housing-price context separate from customer-level attributes. This dataset alone cannot establish "
        "who lives in an area, what they can afford, or whether a campaign will work.", "",
        "## Reproduce offline", "",
        "Run from the repository root with Python 3.12 or later. The example uses only the standard library. "
        "It reads the analysis CSV and writes this Markdown report; it does not modify the pipeline outputs.", "",
        "```console",
        f'python examples/area_shortlist.py --input "{source.as_posix()}" --output "{destination.as_posix()}" '
        f"--layer {layer} --above {above} --min-sales {min_sales} --limit {limit}",
        "```", "",
        f"Input: [{source.name}]({source_link}). Output: `{destination.as_posix()}`.", "",
        f"Input SHA-256: `{digest}`. The report has no generation timestamp; unchanged inputs and arguments "
        "produce identical text.", "",
        "Contains HM Land Registry data © Crown copyright and database right 2021. "
        "Source: Office for National Statistics licensed under the Open Government Licence v.3.0. "
        "Contains OS data © Crown copyright and database right 2026. "
        "Contains Royal Mail data © Royal Mail copyright and database right 2026. "
        "See the repository README for source links, methodology and reuse conditions.", "",
    ])
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=Path("output/neighbour_analysis.csv"))
    parser.add_argument("--output", type=Path, default=Path("docs/examples/area-shortlist.md"))
    parser.add_argument("--layer", type=int, default=2)
    parser.add_argument("--above", type=decimal_argument, default=Decimal("0.20"), help="Strict premium, as a fraction")
    parser.add_argument("--min-sales", type=int, default=20)
    parser.add_argument("--limit", type=int, default=10, help="Displayed examples, from 1 to 20")
    args = parser.parse_args(argv)
    if args.layer < 1 or args.min_sales < 1 or not 1 <= args.limit <= 20:
        parser.error("layer and min-sales must be positive; limit must be between 1 and 20")
    if not args.above.is_finite() or args.above < 0:
        parser.error("above must be a finite, nonnegative fraction")
    if args.input.resolve() == args.output.resolve():
        parser.error("input and output must be different files")
    try:
        sectors = read_sectors(args.input, args.layer)
        rendered = report(sectors, layer=args.layer, above=args.above, min_sales=args.min_sales,
                          limit=args.limit, source=args.input, destination=args.output)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8", newline="\n")
    except (OSError, ValueError) as exc:
        parser.error(str(exc))
    print(f"Wrote {args.output.as_posix()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
