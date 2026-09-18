# Geographic campaign test shortlist

An offline example of turning area-level housing data into a reviewable market-research decision. It identifies postcode sectors with higher recorded median sale prices than their surrounding sectors. It does not estimate individual income or wealth, audience size, campaign response or marketing lift.

## Decision and selection rule

Use the shortlist to propose geographies for a controlled campaign test or to compare local market conditions. Validate customer demand, service coverage, channel reach and unit economics before allocating a budget.

Select a sector when its median sold-home price is **strictly more than 20.00%** above the unweighted median of available sector medians within **2 cumulative graph steps**, excluding itself. Compare the baseline (at least 1 sale) with a shortlist requiring **at least 20 sales**. No national-percentile restriction is applied.

| Cohort | Sectors | Share of comparable sectors | Median sales per sector | Median of sector prices | Median local premium |
| --- | ---: | ---: | ---: | ---: | ---: |
| Baseline: at least 1 sale | 1,607 | 19.9% | 204 | £417,500 | 35.4% |
| Shortlist: at least 20 sales | 1,552 | 19.2% | 210 | £415,250 | 34.9% |

The sales floor removes **55 of 1,607 baseline candidates (3.4%)**. It reduces exposure to sparse observations; it is not a confidence interval or proof of stability. Cohort medians give each sector equal weight.

## Coverage and quality

At graph depth 2, the source contains **8,241 sectors**. **8,064 (97.9%)** have a usable comparison. Unavailable comparisons are excluded from both cohorts.

| Analysis status | Sectors |
| --- | ---: |
| `ok` | 8,064 |
| `missing_geometry` | 154 |
| `missing_price` | 22 |
| `no_priced_neighbours` | 1 |

- **278 of 1,552 shortlist sectors (17.9%)** have at least one low-sale neighbour contributing to their comparison.
- **59 of 1,552 shortlist sectors (3.8%)** have graph neighbours without a usable price.
- Neighbour low-count flags use the source price-run threshold(s): **20 sales**. The subject-sector sales floor does not filter neighbours or recompute their medians.
- Prices are nominal pooled sale prices, with no adjustment for property mix, inflation, floor area or tenure. Sector polygons are approximations; shared borders are not travel connections.

## Bounded examples: top 10 of 1,552 shortlist sectors

Ordered by local price premium, with sector name as the tie-breaker. These are examples for investigation, not recommended audiences. The sales floor applies to every displayed row.

| Sector | Sales | Median sale price | Neighbour median | Local premium | E&W percentile | Priced / all neighbours | Low-sale neighbours |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| W1J 8 | 21 | £8,345,273 | £2,137,500 | 290.4% | 100.0 | 18 / 20 | 10 |
| SE21 7 | 113 | £1,800,000 | £509,950 | 253.0% | 99.4 | 24 / 24 | 0 |
| W1U 4 | 68 | £4,688,325 | £1,517,125 | 209.0% | 99.9 | 18 / 18 | 5 |
| DE22 5 | 26 | £840,000 | £295,000 | 184.7% | 97.0 | 21 / 21 | 0 |
| WD3 4 | 120 | £1,373,250 | £490,000 | 180.3% | 99.0 | 28 / 28 | 0 |
| TS22 5 | 852 | £334,995 | £123,625 | 171.0% | 60.0 | 28 / 28 | 1 |
| BH13 7 | 275 | £825,000 | £315,000 | 161.9% | 96.9 | 10 / 10 | 0 |
| W1U 8 | 27 | £3,600,000 | £1,375,000 | 161.8% | 99.9 | 19 / 19 | 5 |
| CH48 1 | 50 | £862,500 | £330,000 | 161.4% | 97.3 | 21 / 21 | 1 |
| CH64 5 | 35 | £625,000 | £240,000 | 160.4% | 92.6 | 25 / 25 | 2 |

## From shortlist to an experiment

1. Join sector-level business measures such as aggregate demand, delivery coverage and acquisition cost; review missing coverage and sparse neighbour comparisons.
2. Form comparable geographic test and control groups. Account for adjacent-area spillover and channel targeting resolution; choose the allocation before seeing outcomes.
3. Predefine a success measure, budget and stopping rule. Measure incremental conversions or contribution against the control, then decide whether to expand, revise or stop.
4. Keep housing-price context separate from customer-level attributes. This dataset alone cannot establish who lives in an area, what they can afford, or whether a campaign will work.

## Reproduce offline

Run from the repository root with Python 3.12 or later. The example uses only the standard library. It reads the analysis CSV and writes this Markdown report; it does not modify the pipeline outputs.

```console
python examples/area_shortlist.py --input "output/neighbour_analysis.csv" --output "docs/examples/area-shortlist.md" --layer 2 --above 0.20 --min-sales 20 --limit 10
```

Input: [neighbour_analysis.csv](../../output/neighbour_analysis.csv). Output: `docs/examples/area-shortlist.md`.

Input SHA-256: `66dadf78bbe8891819580fedc30d26b9e47b03831c3d687517aebbd9c4e6d41d`. The report has no generation timestamp; unchanged inputs and arguments produce identical text.

Contains HM Land Registry data © Crown copyright and database right 2021. Source: Office for National Statistics licensed under the Open Government Licence v.3.0. Contains OS data © Crown copyright and database right 2026. Contains Royal Mail data © Royal Mail copyright and database right 2026. See the repository README for source links, methodology and reuse conditions.
