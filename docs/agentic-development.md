# Agentic development, with evidence

The useful unit of work was a decision artifact: a complete CSV of sectors above a defined local-price threshold. The method and acceptance criteria came first. The implementation stayed small enough to inspect and validate.

## Human direction and agent execution

The project brief specified sources, transaction filters, approximate geometry, shared-edge adjacency, cumulative graph depths and the final selection threshold. It set a scope constraint: a straightforward Python CLI, caching and tests, with no unnecessary service or database.

The agent decomposed the work into issues, implemented the stages, wrote and ran tests, executed the national pipeline and recorded coverage and provenance. The repository owner supplied the decision objective and constraints. Those activities demonstrate a delivery process; they do not establish that every line received independent human review.

## The original delivery trail

| Issue | Behaviour | Validation evidence |
| --- | --- | --- |
| [#1](https://github.com/pranman/postcode-signals/issues/1) | Cache and ingest eligible sales | Postcode formats, exclusions and interrupted downloads |
| [#2](https://github.com/pranman/postcode-signals/issues/2) | Aggregate prices and flag sparse sectors | Exact quartiles, percentile ties and sample counts |
| [#3](https://github.com/pranman/postcode-signals/issues/3) | Build approximate sector polygons | OA coverage, uniqueness, normalisation and dissolve |
| [#4](https://github.com/pranman/postcode-signals/issues/4) | Construct shared-edge adjacency | Reject corner contact, overlap and self-edges |
| [#5](https://github.com/pranman/postcode-signals/issues/5) | Traverse cumulative neighbourhoods | Cycles, distance, isolates and unpriced graph nodes |
| [#6](https://github.com/pranman/postcode-signals/issues/6) | Expose CLI and selection policy | Offline end-to-end tests and exact-threshold ties |
| [#7](https://github.com/pranman/postcode-signals/issues/7) | Deliver and audit national output | Independent set expansion, complete selection and source hashes |

Each issue has an implementation/documentation commit and a separate validation/delivery commit: 14 commits in the original delivery. Issue records were recreated for publication; their creation timestamps differ from the original implementation date. The [commit history](https://github.com/pranman/postcode-signals/commits/main/) retains that sequence. The delivery manifest records 34 passing tests, 188,880 matched Output Areas and all 24,723 sector/depth comparisons checked independently.

## What the verification catches

Production traversal uses NetworkX. The national-output test recomputes neighbourhoods using independent set expansion, reducing the chance that the same traversal mistake appears in implementation and assertion. Synthetic geometry tests distinguish a real shared edge from a corner and an overlap. Decimal comparisons protect the strict 20% boundary from binary rounding.

Coverage is part of the result: 154 observed-price sectors lack geometry; 22 geometric sectors lack prices; one priced island sector has no priced neighbours. The tool reports those limitations instead of inventing comparators.

## Release review as a second stage

The public-readiness pass used parallel, bounded tasks: code review and regression fixes, an independent release audit, and a runnable analytical example with figures. A coordinating agent integrated the results and ran release checks. This is distinct from the original delivery; the original session record does not establish a multi-agent build.

The review found concrete improvements: caches needed integrity checks, mixed sample thresholds could be accepted downstream, CI was absent, and Windows line-ending conversion made checked-in bytes differ from delivery hashes. Fixes and regression checks are tracked in [#9](https://github.com/pranman/postcode-signals/issues/9); the product example and narrative are in [#8](https://github.com/pranman/postcode-signals/issues/8).

The release approach is: define observable acceptance criteria, delegate with clear file ownership, challenge the output independently, inspect figures, run offline tests, then commit and verify CI. Parallel agent review adds checking; it does not substitute for scientific or customer validation.

## Model and resource record

The [sanitised metrics export](development-metrics.json) comes from the original build's local session metadata. Only model settings, timestamps and usage counters were exported.

| Original implementation turn | Recorded value |
| --- | ---: |
| Model | `gpt-6-astra` |
| Reasoning setting | `xhigh` |
| Input tokens | 1,806,093 |
| Cached input tokens (included in input) | 1,722,880 |
| Uncached input tokens (input minus cached) | 83,213 |
| Output tokens | 26,949 |
| Reasoning output tokens (included in output) | 4,486 |
| Total tokens (input + output) | 1,833,042 |
| Recorded turn interval, including tools and downloads | 19 minutes 41 seconds |

Scope: the implementation turn on 14 September 2026, from 10:45:20.766 to 11:05:01.323 UTC. It excludes the later coverage question and public-readiness work. Repeated context and cache hits count toward input usage. No monetary cost or time-saving claim is inferred. Raw logs remain private, so the counters are an exported record, not independently verifiable public telemetry.

## Product and system thinking

The decisions connect an explainable housing proxy, geographic context, visible quality flags, a portable output contract and a measurable next experiment. [Design tradeoffs](product-decisions.md) show where the method is useful and where further investment is warranted. The strongest next evidence would be sensitivity analysis and a controlled business pilot, rather than more application infrastructure.
