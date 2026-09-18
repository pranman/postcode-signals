"""Render real sector maps and a synthetic graph explanation without downloads.

Requires the regular project dependencies, requirements-figures.txt and the locally
generated output/sectors.geojson. From the repository root:
    python examples/make_figures.py
"""
from __future__ import annotations

import argparse
import hashlib
import json
from collections import defaultdict
from decimal import Decimal
from pathlib import Path

import geopandas as gpd
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd
from matplotlib.colors import LinearSegmentedColormap, LogNorm
from matplotlib.lines import Line2D
from matplotlib.patches import Rectangle
from matplotlib.ticker import FixedLocator, FuncFormatter


INK = "#18333D"
MUTED = "#536970"
PAPER = "#FAFBF8"
SUBJECT = "#CE592A"
FIRST = "#294B59"
SECOND = "#7C9096"
PICKS = [
    ("SE21 7", "QUALIFIES", "Higher-priced locally", "#14685B"),
    ("SW3 5", "DOES NOT QUALIFY", "High national price, small local gap", "#876121"),
    ("WC1A 1", "EXCLUDED BY SALES FLOOR", "Large apparent gap, sparse sales", "#8A4A47"),
]


def graph_distances(links: dict[str, set[str]], subject: str) -> dict[str, int]:
    """Distinct neighbours at shortest-path distance one and two, plus subject."""
    distance = {subject: 0}
    frontier = {subject}
    for depth in (1, 2):
        frontier = {node for parent in frontier for node in links[parent]} - distance.keys()
        distance.update({node: depth for node in frontier})
    return distance


def pounds(value: float) -> str:
    return f"£{value:,.0f}"


def abbreviated_pounds(value: float, position: int | None = None) -> str:
    return f"£{value / 1_000_000:g}m" if value >= 1_000_000 else f"£{value / 1_000:g}k"


def add_scale_bar(axis, bounds):
    xmin, ymin, xmax, ymax = bounds
    width, height = xmax - xmin, ymax - ymin
    options = [100, 200, 500, 1000, 2000, 5000]
    length = max(value for value in options if value <= width * 0.25)
    left, bottom = xmin + width * 0.05, ymin + height * 0.05
    axis.plot([left, left + length], [bottom, bottom], color=INK, linewidth=3, zorder=15)
    axis.text(left, bottom + height * 0.025,
              f"{length / 1000:g} km" if length >= 1000 else f"{length} m",
              fontsize=9, color=INK, zorder=16,
              bbox={"facecolor": PAPER, "edgecolor": "none", "pad": 2})
    axis.annotate("N", xy=(0.94, 0.96), xytext=(0.94, 0.83), xycoords="axes fraction",
                  ha="center", color=INK, fontsize=10,
                  arrowprops={"arrowstyle": "-|>", "color": INK, "linewidth": 1.5})


def save_figure(figure, path: Path):
    figure.savefig(path, dpi=180, facecolor=figure.get_facecolor(),
                   metadata={"Software": "examples/make_figures.py; Matplotlib"})
    plt.close(figure)


def plot_real_examples(geography, analysis, links, destination: Path):
    figure = plt.figure(figsize=(17.5, 11), facecolor=PAPER)
    figure.text(0.045, 0.953, "Which neighbourhoods qualify?", color=INK, fontsize=28, weight="bold")
    figure.text(0.045, 0.914,
                "Three real London examples show the difference between national price, local context and sales coverage.",
                color=MUTED, fontsize=13)
    figure.text(0.045, 0.875,
                "RULE   Median sale price > 1.20 × local median   •   At least 20 sales   •   Neighbours within 2 graph steps",
                color=INK, fontsize=12, weight="bold")
    colormap = LinearSegmentedColormap.from_list(
        "housing_prices", ["#EDF3F1", "#BCD5CD", "#75AA9E", "#34786E", "#104E49"])
    normalization = LogNorm(vmin=250_000, vmax=6_000_000, clip=True)
    summaries = []
    for index, (subject, outcome, title, badge_colour) in enumerate(PICKS):
        left = 0.045 + index * 0.313
        figure.text(left, 0.827, outcome, fontsize=10, weight="bold", color=badge_colour)
        figure.text(left, 0.792, subject, fontsize=22, weight="bold", color=INK)
        figure.text(left, 0.765, title, fontsize=11.5, color=MUTED)
        distances = graph_distances(links, subject)
        selected = geography.loc[sorted(distances)].copy()
        selected["depth"] = [distances[name] for name in selected.index]
        selected["median_price"] = analysis.reindex(selected.index).median_price
        xmin, ymin, xmax, ymax = selected.total_bounds
        span = max(xmax - xmin, ymax - ymin) * 1.10
        xmid, ymid = (xmin + xmax) / 2, (ymin + ymax) / 2
        bounds = (xmid - span / 2, ymid - span / 2, xmid + span / 2, ymid + span / 2)
        axis = figure.add_axes([left, 0.355, 0.285, 0.385], facecolor="#F0F2EF")
        backdrop = geography.cx[bounds[0]:bounds[2], bounds[1]:bounds[3]]
        backdrop.plot(ax=axis, facecolor="#E9EDEA", edgecolor="#D9DFDC", linewidth=0.4)
        for depth, edge, style, linewidth in [(2, SECOND, "--", 1.0), (1, FIRST, "-", 1.3), (0, SUBJECT, "-", 3.0)]:
            subset = selected[selected.depth.eq(depth)]
            subset.plot(ax=axis, column="median_price", cmap=colormap, norm=normalization,
                        edgecolor=edge, linestyle=style, linewidth=linewidth,
                        missing_kwds={"color": "#E6E6E3", "hatch": "///", "edgecolor": edge})
        point = selected.loc[subject].geometry.representative_point()
        axis.annotate(subject, xy=(point.x, point.y), xytext=(0, 0), textcoords="offset points",
                      ha="center", va="center", color=INK, fontsize=10, weight="bold", zorder=12,
                      bbox={"boxstyle": "round,pad=0.3", "facecolor": "white", "edgecolor": SUBJECT, "linewidth": 1.3})
        axis.set_xlim(bounds[0], bounds[2])
        axis.set_ylim(bounds[1], bounds[3])
        axis.set_aspect("equal")
        axis.set_axis_off()
        add_scale_bar(axis, bounds)
        row = analysis.loc[subject]
        premium = 100 * row.pct_above_neighbourhood
        figure.text(left, 0.322, f"{premium:+.1f}%", fontsize=25, weight="bold", color=badge_colour)
        figure.text(left + 0.116, 0.326, "versus local median", fontsize=10.5, color=MUTED)
        figure.text(left, 0.287,
                    f"Subject {pounds(row.median_price)}   /   Local {pounds(row.neighbourhood_median)}",
                    fontsize=10.5, color=INK)
        figure.text(left, 0.261,
                    f"{int(row.transaction_count):,} sales   •   E&W price percentile {row.ew_percentile:.2f}",
                    fontsize=11, color=INK)
        figure.text(left, 0.234,
                    f"{int(row.priced_neighbour_count)} / {int(row.neighbour_count)} neighbours priced; "
                    f"{int(row.low_count_neighbour_count)} below 20 sales", fontsize=10, color=MUTED)
        summaries.append({
            "sector": subject, "outcome": outcome, "layer": 2,
            "transaction_count": int(row.transaction_count), "median_price": float(row.median_price),
            "neighbourhood_median": float(row.neighbourhood_median),
            "pct_above_neighbourhood": float(row.pct_above_neighbourhood),
            "ew_percentile": float(row.ew_percentile),
            "neighbour_count": int(row.neighbour_count),
            "priced_neighbour_count": int(row.priced_neighbour_count),
            "low_count_neighbour_count": int(row.low_count_neighbour_count),
        })
    legend = [
        Line2D([], [], color=SUBJECT, linewidth=3, label="Subject sector"),
        Line2D([], [], color=FIRST, linewidth=1.5, label="1 graph step"),
        Line2D([], [], color=SECOND, linewidth=1.2, linestyle="--", label="2 graph steps"),
        Rectangle((0, 0), 1, 1, facecolor="#E9EDEA", edgecolor="#D9DFDC", label="Outside comparison"),
    ]
    figure.legend(handles=legend, loc="lower left", bbox_to_anchor=(0.04, 0.161), ncol=4,
                  fontsize=10, frameon=False, labelcolor=INK, handlelength=2.6, columnspacing=2)
    colour_axis = figure.add_axes([0.62, 0.17, 0.31, 0.016])
    colourbar = figure.colorbar(plt.cm.ScalarMappable(norm=normalization, cmap=colormap),
                               cax=colour_axis, orientation="horizontal", extend="both")
    colourbar.locator = FixedLocator([250_000, 500_000, 1_000_000, 2_000_000, 6_000_000])
    colourbar.formatter = FuncFormatter(abbreviated_pounds)
    colourbar.update_ticks()
    colourbar.ax.minorticks_off()
    colourbar.ax.tick_params(labelsize=9, colors=MUTED)
    colourbar.outline.set_visible(False)
    figure.text(0.62, 0.196, "Median sold-home price • shared logarithmic scale", fontsize=10, color=MUTED)
    figure.text(0.045, 0.115,
                "2023–2025 nominal sale prices • 2021 approximate sector boundaries • Different map extents; use scale bars",
                fontsize=10, color=MUTED)
    figure.text(0.045, 0.085,
                "Local median excludes the subject; priced sectors have equal weight. Low-sale neighbours remain included. Hatching = missing price.", fontsize=10, color=MUTED)
    figure.text(0.045, 0.055,
                "Area-level housing-price context; no inference about an individual’s wealth or a campaign’s expected return.",
                fontsize=10, color=INK)
    figure.text(0.045, 0.027,
                "Sources: HM Land Registry and ONS (OGL v3.0). Contains Crown, OS and Royal Mail data. Full attribution: docs/figures/README.md.",
                fontsize=8.5, color=MUTED)
    save_figure(figure, destination / "local-price-comparison.png")
    return summaries


def plot_graph_rules(destination: Path):
    figure = plt.figure(figsize=(15, 7.8), facecolor=PAPER)
    figure.text(0.05, 0.92, "What counts as a neighbourhood?", fontsize=26, weight="bold", color=INK)
    figure.text(0.05, 0.87, "Synthetic geometry illustrates the graph rules; these are not real postcode sectors.",
                fontsize=12, color=MUTED)
    left = figure.add_axes([0.045, 0.255, 0.43, 0.53])
    left.set_xlim(-0.2, 3.5)
    left.set_ylim(-0.5, 3.25)
    left.set_aspect("equal")
    left.set_axis_off()
    synthetic = [
        (0, 0, 1, 1, "S", "#F9DDCE"),
        (1, 0, 1, 1, "A", "#BCD5CD"),
        (1, 1, 1, 1, "B", "#E8ECE9"),
    ]
    for x, y, width, height, label, fill in synthetic:
        left.add_patch(Rectangle((x, y), width, height, facecolor=fill, edgecolor=INK, linewidth=1.8))
        left.text(x + width / 2, y + height / 2, label, ha="center", va="center", fontsize=19, weight="bold", color=INK)
    left.plot([1, 1], [0, 1], linewidth=5, color="#14685B")
    left.scatter([1], [1], s=90, color=SUBJECT, zorder=8)
    left.annotate("S–A: shared edge\nDirect neighbours", xy=(1, 0.45), xytext=(2.25, 0.0),
                  color="#14685B", fontsize=11, arrowprops={"arrowstyle": "->", "color": "#14685B"})
    left.annotate("S–B: corner only\nNo direct edge", xy=(1, 1), xytext=(0.0, 2.6),
                  color=SUBJECT, fontsize=11, arrowprops={"arrowstyle": "->", "color": SUBJECT})
    figure.text(0.065, 0.755, "01  Shared line, not just contact", fontsize=15, color=INK, weight="bold")
    figure.text(0.065, 0.25, "B still enters at depth 2 via A.\nCorner contact itself never creates a graph edge.",
                fontsize=11, color=MUTED, linespacing=1.7)
    right = figure.add_axes([0.52, 0.34, 0.43, 0.38])
    right.set_xlim(-0.6, 3.65)
    right.set_ylim(-0.6, 1.4)
    right.set_axis_off()
    for start in (0, 1, 2):
        right.plot([start, start + 1], [0.5, 0.5], color=SECOND, linewidth=2, zorder=1)
    for index, (label, price, fill) in enumerate([
        ("S", "£300k", "#F9DDCE"), ("A", "£100k", "#8ABDAF"),
        ("B", "£200k", "#D5E7DE"), ("C", "£900k", "#E8ECE9"),
    ]):
        right.scatter(index, 0.5, s=2200, facecolor=fill, edgecolor=INK, linewidth=1.6, zorder=2)
        right.text(index, 0.5, label, ha="center", va="center", color=INK, fontsize=18, weight="bold")
        right.text(index, -0.04, price, ha="center", color=INK, fontsize=12)
        right.text(index, -0.3, ["subject", "1 step", "2 steps", "3 steps"][index], ha="center", color=MUTED, fontsize=10)
    figure.text(0.525, 0.755, "02  Depth 2 includes steps 1 and 2", fontsize=15, color=INK, weight="bold")
    figure.text(0.545, 0.29, "Local baseline = median(£100k, £200k) = £150k", color=INK, fontsize=12, weight="bold")
    figure.text(0.545, 0.25, "Subject premium = £300k / £150k − 1 = +100%", color="#14685B", fontsize=12)
    figure.text(0.545, 0.178, "S is excluded from its own baseline. C is beyond depth 2.\nEach neighbour contributes once, even if several paths reach it.",
                color=MUTED, fontsize=10.5, linespacing=1.7)
    figure.text(0.05, 0.10,
                "The graph follows positive-length shared polygon boundaries with disjoint interiors. "
                "It measures adjacency, not driving distance or audience reach.", color=MUTED, fontsize=10.5)
    figure.text(0.05, 0.055,
                "Price comparisons use available sector medians with equal sector weight. Missing-price sectors can still connect paths.",
                color=MUTED, fontsize=10.5)
    save_figure(figure, destination / "neighbourhood-rule.png")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, default=Path("output"))
    parser.add_argument("--output-dir", type=Path, default=Path("docs/figures"))
    args = parser.parse_args(argv)
    inputs = [args.data_dir / name for name in ["sectors.geojson", "neighbour_analysis.csv", "adjacency.csv"]]
    for path in inputs:
        if not path.is_file():
            parser.error(f"Missing {path}. Rebuild geography with `python wealth.py geography`; "
                         "then rebuild analysis if inputs changed. This plotting script never downloads data.")
    geography = gpd.read_file(inputs[0]).to_crs(27700).set_index("sector")
    all_analysis = pd.read_csv(inputs[1])
    analysis = all_analysis[all_analysis.layer.eq(2)].set_index("sector")
    if not geography.index.is_unique or not analysis.index.is_unique:
        parser.error("Expected unique sectors in geography and layer-2 analysis")
    links = defaultdict(set)
    for edge in pd.read_csv(inputs[2]).itertuples():
        links[edge.sector_a].add(edge.sector_b)
        links[edge.sector_b].add(edge.sector_a)
    for index, (subject, _, _, _) in enumerate(PICKS):
        if subject not in analysis.index or subject not in geography.index:
            parser.error(f"Missing example sector: {subject}")
        row = analysis.loc[subject]
        premium_passes = Decimal(str(row.median_price)) > Decimal("1.20") * Decimal(str(row.neighbourhood_median))
        expected = [(True, True), (False, True), (True, False)][index]
        if (premium_passes, row.transaction_count >= 20) != expected or row.analysis_status != "ok":
            parser.error(f"{subject} no longer demonstrates the documented decision; update the example choices")
        if index == 1 and row.ew_percentile < 95:
            parser.error(f"{subject} no longer demonstrates a high national price percentile")
        distances = graph_distances(links, subject)
        neighbours = analysis.loc[sorted(set(distances) - {subject})]
        if (len(neighbours) != row.neighbour_count
                or neighbours.median_price.notna().sum() != row.priced_neighbour_count
                or neighbours.median_price.median() != row.neighbourhood_median):
            parser.error(f"{subject}: adjacency and analysis disagree; rebuild analysis")
    plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 11, "axes.unicode_minus": True})
    args.output_dir.mkdir(parents=True, exist_ok=True)
    summaries = plot_real_examples(geography, analysis, links, args.output_dir)
    plot_graph_rules(args.output_dir)
    manifest = {
        "description": "Real layer-2 examples and an explicitly synthetic graph schematic; no basemap or network calls.",
        "source_files": {path.name: {"sha256": hashlib.sha256(path.read_bytes()).hexdigest()} for path in inputs},
        "matplotlib_version": matplotlib.__version__, "examples": summaries,
    }
    (args.output_dir / "figure-data.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote local-price-comparison.png, neighbourhood-rule.png and figure-data.json to {args.output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
