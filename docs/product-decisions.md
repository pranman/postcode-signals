# From a geographic signal to a business decision

The starting question is specific: **which postcode sectors have higher sold-home prices than their surroundings?** Relative local price can help a team find variation within a market before deciding where to investigate or test.

The delivery contract was a CSV of sectors more than 20% above their cumulative two-step neighbourhood median, with missing coverage and small samples visible. Success meant producing that complete, independently checked output. Commercial impact has not been measured.

## Decisions this can support

| Use | What the output contributes | What a team must add | Measure of success |
| --- | --- | --- | --- |
| Geographic advertising experiments | Candidate areas for testing a product proposition | Permitted platform geographies, rights review, first-party response data and a comparison group | Incremental conversion or contribution margin |
| Market or service-area prioritisation | A shortlist of locally higher-price housing markets | Reachable demand, competition, delivery costs and operational capacity | Demand and unit economics validated in a pilot |
| Exploratory data analysis | A joinable sector table, graph and missing-data flags | Other appropriately licensed area-level indicators and stable joins | Reproducible findings robust to thresholds and data vintage |
| Geographic research | Contrasts between local premium and national percentile | Property-mix controls and updated geography | Findings that survive sensitivity and coverage checks |

An area can rank highly relative to nearby sectors without ranking highly across England and Wales. Use both `pct_above_neighbourhood` and `ew_percentile` when the decision needs local distinctiveness and a national price floor. Treat both as housing-market signals; neither measures a person's income, spending intent or net worth.

## A bounded experiment

1. Generate the [offline shortlist](examples/area-shortlist.md), retaining a minimum of 20 subject sales. Inspect low-count neighbours and missing coverage.
2. Restrict it to the serviceable market and translate sectors into supported campaign geographies after checking current platform rules and data rights.
3. Select comparable test and control areas. Predefine budget, measurement window, primary outcome and stop criteria; account for geographic spillover.
4. Join only the appropriately governed outcome data needed for evaluation. Compare incremental results, including acquisition cost and contribution margin.
5. Expand only if the experiment supports the decision. A high price premium alone is not evidence of demand or profitable acquisition.

Twenty sales is an illustrative screening threshold, not a confidence interval. It removes 55 of the 1,607 delivered candidates, leaving 1,552. Neighbourhood baselines still include low-sale neighbours, which the output flags separately.

## Engineering choices and their tradeoffs

| Choice | Reason | Consequence |
| --- | --- | --- |
| Small staged Python CLI | Make the data product inspectable and cheap to rerun | Operators manage stage order and data versions |
| Median of sold-home prices | Explainable, robust to some extreme transactions | Property mix, transaction selection and time affect the signal |
| Unweighted median of sector medians | Give each neighbouring area equal influence | Small and large transaction samples contribute equally |
| ONS OA best-fit dissolve | Reproducible open geographic construction | Approximate 2021 polygons; some later sectors do not match |
| Shared-edge adjacency | Define local geography without an arbitrary radius | Graph distance is not travel time; islands can lack comparators |
| Preserve unpriced graph nodes | Keep topology while exposing missing evidence | A graph neighbour may contribute no price |
| CSV plus source hashes | Easy inspection and downstream use | Batch files need explicit provenance and stale-output controls |
| No web service or database | Align scope with the decision artifact | Interactive exploration and scheduled refresh remain future work |

## Boundaries and next investment

The data covers qualifying sales in England and Wales, not the whole UK. Pooled 2023–2025 nominal prices are not adjusted for inflation, property type, floor area or tenure. The 2021 geography introduces a visible coverage gap. Missing data is not imputed. A sector-level average must not be used to assign wealth or sensitive traits to residents, or determine an individual's eligibility for opportunities.

The next useful investments are sensitivity analysis, current-geography coverage and automatic run lineage. A user interface should follow evidence of repeated exploration needs; commercial rollout should follow a measured pilot. See [automatic run lineage (#10)](https://github.com/pranman/postcode-signals/issues/10) and [sensitivity and geography validation (#11)](https://github.com/pranman/postcode-signals/issues/11).
