# Validation

What this project's numbers are worth, measured rather than asserted.

Every result below is reproducible. The scripts are in [`scripts/validation/`](../scripts/validation/),
the raw outputs are checked in under [`data/validation/`](../data/validation/), and the
inputs are either a free unauthenticated API or the rolling archive this project already
publishes at `raw.githubusercontent.com/peterklingelhofer/carbon-lens/data/history.json`.
A third party can rerun all of it without asking us for anything.

Two comparisons are **NOT RUN**, because they need paid or
registered credentials this project doesn't hold. They're reported as unrun rather than
estimated, and the scripts are complete so anyone with a key can run them. Publishing a
number we didn't measure would defeat the purpose of the document.

Dates: measurements taken 2026-08-23. Live-grid results sample a single instant and will
differ on rerun; archive results cover 2026-08-08 to 2026-08-23.

| # | Question | Status | Headline |
|---|---|---|---|
| 1 | Does the marginal heuristic track measured marginal data? | **NOT RUN** | No WattTime credentials |
| 2 | Do our intensities agree with Electricity Maps? | **NOT RUN** | No Electricity Maps key |
| 3 | Does flow tracing change the answer enough to justify itself? | **MEASURED** | Yes for importers: mean 41.5%, up to 289% |
| 4 | What does snapshot carry-forward cost in accuracy? | **MEASURED** | Median 8.5, p90 125 gCO2/kWh; 38.2% of archived points are carried |
| 5 | What did the factor-corpus change do to reported numbers? | **MEASURED** | Mean 3.9% absolute, max 12.3% |
| 6 | How much of the UK/EU difference comes from accounting basis rather than the grid? | **MEASURED** | 60.4% at the sampled instant |

Results 5 and 6 measure the effect of two changes made during the audit: the
emission-factor corpus (5) and the mixed accounting basis it uncovered (6). Both change
numbers the API already serves.

---

## 1. Marginal heuristic vs WattTime measured MOER

**Status: NOT RUN. No credentials.**

`api.watttime.org` returns HTTP 401 without a login, and this project holds none. Script:
[`scripts/validation/watttime_backtest.py`](../scripts/validation/watttime_backtest.py),
runnable with `WATTTIME_USERNAME` / `WATTTIME_PASSWORD`. It reports paired-hour count,
Pearson and Spearman correlation, mean absolute error, bias and RMSE.

One property of the estimator matters before any data does: **it emits no confidence
signal.** What CarbonLens calls marginal intensity is
`emission_factors.calculate_marginal_intensity`: a merit-order lookup that walks
`("petroleum", "oil", "natural_gas", "coal", "biomass")` and returns the emission factor
of the first fuel currently generating.

That has two consequences worth stating plainly:

1. **The output is a step function with about five possible values** (650, 490, 820, 230,
   or the grid average when no fossil runs), compared against a continuous measured
   signal. Pearson r will understate agreement; the script reports Spearman as well, and
   logs the distinct values actually produced.
2. **There's no confidence signal to gate the feature on.** If the backtest shows poor
   agreement, the remedy is to add one; there's no existing one to threshold.

Until this runs, `marginal_intensity_gco2_kwh` is labelled `heuristic` in the API
(`marginal_basis` on `/signal`) and its provenance cites the marginal literature as *the
method it approximates*, explicitly not as evidence that the approximation is good. The
corpus also carries `wiesner-2025-marginal-poor-metric`, which argues against the metric
this project reports.

## 2. Intensity vs Electricity Maps

**Status: NOT RUN. No API key.**

Electricity Maps' intensity endpoints are commercial. Script:
[`scripts/validation/electricity_maps_compare.py`](../scripts/validation/electricity_maps_compare.py),
runnable with `CARBON_LENS_ELECTRICITY_MAPS_API_KEY`. It compares both production-based and
consumption-based intensity per zone.

What is already known without running it, from their published default factor table
(which is free, and was read on 2026-08-23):

- They use **solar 45**, which isn't an IPCC AR5 row at all. AR5 splits PV into rooftop
  (41) and utility (48); 45 is between them. This project uses 48, with the reasoning in
  `data/emission-factors.json`.
- They assign **battery discharge world-average intensity (301)**. This project excludes
  storage from the average entirely (see §4 of `docs/VERIFICATION.md`). These are different
  answers to a real question, and both are defensible.
- They assign their **unknown bucket 700** on a stated assumption of thermal generation.
  This project assigns `other` 300, an assumption with no source. On an import-heavy zone
  that single difference can move the result more than every other factor combined.

So a nonzero gap is expected. The comparison is worth running to find out whether the gap
is the size those known differences predict, or larger.

## 3. Production-based vs consumption-based intensity

**Status: MEASURED.** Live ENTSO-E, sampled 2026-08-23T20:36Z.
Raw: [`data/validation/production-vs-consumption.json`](../data/validation/production-vs-consumption.json).
Script: [`production_vs_consumption.py`](../scripts/validation/production_vs_consumption.py).

Whether accounting for imports changes the number enough to justify the flow tracer:

**For zones that actually import, yes, and by a lot.** Nine of thirteen zones had
measurable imports. Across those: mean absolute difference **41.5%**, maximum **289%**.

| Zone | Production | Consumption | Δ | Δ% | Interpretation |
|---|---|---|---|---|---|
| AT | 40.9 | 159.1 | +118.2 | **+289.0%** | importer |
| IT-NO | 317.7 | 194.3 | -123.4 | -38.8% | importer |
| BE | 260.0 | 198.3 | -61.7 | -23.7% | importer |
| DE | 317.9 | 289.8 | -28.1 | -8.8% | importer |
| CZ | 341.2 | 362.7 | +21.5 | +6.3% | importer |
| PL | 548.6 | 531.4 | -17.2 | -3.1% | importer, small effect |
| CH | 23.9 | 24.4 | +0.5 | +2.1% | importer, small effect |
| ES | 158.5 | 157.1 | -1.4 | -0.9% | importer, small effect |
| NL | 529.4 | 525.4 | -4.0 | -0.8% | importer, small effect |
| DK-DK1 | 110.2 | 110.2 | 0.0 | 0.0% | net exporter, no imports |
| FR | 37.3 | 37.3 | 0.0 | 0.0% | net exporter, no imports |
| PT | 80.8 | 80.8 | 0.0 | 0.0% | net exporter, no imports |
| IE | 114.0 | 114.0 | 0.0 | 0.0% | **no evaluable border** |

**Austria is the result that matters.** On a production basis Austria looks like one of
the cleanest grids in Europe at 41 gCO2/kWh, because its own generation is overwhelmingly
hydro. It was importing 2,170 MW from the Czech Republic and 694 MW from Germany at the
sampled instant, and what Austrian consumers were actually using was **159 gCO2/kWh, four
times higher**. A caller routing a workload to Austria on the production number is making
a decision on a figure that's wrong by 4x for their purpose. This alone justifies the
flow-tracing feature.

### The zeros are three different things

A bare 0.0% delta is ambiguous: it can mean a zone imported nothing, or that its imports
couldn't be measured. The script classifies each zone rather than leaving that to the reader:

- **FR, PT, DK-DK1: correct zeros.** These were net exporters on every evaluable border at
  the sampled instant. A zone with no imports has consumption intensity identically equal
  to production intensity; that's the tracing equation behaving properly.
- **IE: a gap in the measurement.** Ireland's only borders in `TRACED_ZONES` are with GB, and GB
  never resolved (below). Ireland had **no evaluable border at all**, so the model gave it
  zero imports by default. Its 0.0% means "not measured"; it doesn't mean "no effect".

### Two data-quality problems found while doing this

**GB has no ENTSO-E production data.** `TRACED_ZONES` includes `GB`, and the ENTSO-E A75
document returned nothing for it. Three borders (`FR-GB`, `NL-GB`, `GB-IE`) are therefore
unevaluable, which is why Ireland is stranded. GB left the EU internal market and its
ENTSO-E coverage isn't what it was. The flow tracer silently models a smaller network
than `TRACED_ZONES` advertises.

**Ireland's reported load is implausible.** ENTSO-E returned **260 MW** of total generation
for IE. Irish demand runs in the low single-digit gigawatts, so this is roughly 5% of the
real system. The intensity computed from it (114 gCO2/kWh) is derived from a fragment of
the grid and shouldn't be trusted. This affects the ordinary `/carbon` path for Irish
zones as well as this analysis.

Both are recorded in [`VERIFICATION.md`](./VERIFICATION.md).

## 4. Snapshot carry-forward error

**Status: MEASURED.** From the published archive, 2026-08-08 to 2026-08-23.
Raw: [`data/validation/carry-forward-error.json`](../data/validation/carry-forward-error.json).
Script: [`carry_forward_error.py`](../scripts/validation/carry_forward_error.py).

The README says the snapshot builder carries a zone's last live reading forward across
brief upstream gaps rather than downgrading it to an estimate. This measures the cost.

**Method.** In the archive a carry-forward appears as consecutive samples with an identical
intensity *and* renewable percentage. For each run we compare the carried value against the
next different value. That difference is the error the carry had accumulated by
the time fresh data arrived: an upper bound on the error over the run, and the quantity a
consumer of a stale reading actually cares about.

**Sample.** 109 series (7 excluded as constant throughout, being fixed heuristics or mock
fixtures), 38,976 points, 2,152 carry runs.

**38.2% of all archived points are carried forward from an earlier reading.** That's the
single most important number here and it wasn't previously stated anywhere.

| Held for | n | Median abs error | Mean abs error | p90 | Max | Mean signed |
|---|---|---|---|---|---|---|
| 0-2 h | 419 | 3.2 | 19.3 | 71.5 | 230.2 | -7.5 |
| 2-4 h | 364 | **55.0** | 62.0 | 137.5 | 216.4 | -29.4 |
| 4-8 h | 450 | 15.6 | 50.1 | 137.5 | 275.5 | +31.5 |
| 8+ h | 919 | 5.6 | 13.7 | 33.9 | 460.8 | -4.6 |
| **all** | **2,152** | **8.5** | **30.6** | **125.0** | **460.8** | **-1.8** |

All figures gCO2/kWh.

**Reading the table:**

- A carry under two hours is usually cheap: median error 3.2 gCO2/kWh. The design decision
  is defensible for the case it was designed for.
- The **2-4 hour band is the worst**, median 55 gCO2/kWh. That's a real cost, and it's
  where a diurnal solar or wind swing happens while the reading sits frozen.
- The tail is heavy. The p90 across all runs is **125 gCO2/kWh**, which is larger than the
  entire intensity of several clean zones. Mean error (30.6) badly understates the risk;
  the median (8.5) understates it worse.
- **Bias is near zero overall (-1.8)** but not within bands, and the 2-4 h and 4-8 h bands
  have opposite signs (-29.4 and +31.5). A stale reading is about as likely to be too clean
  as too dirty, which is small comfort: for a routing decision, wrong in either direction
  sends the job to the wrong region.
- The 8+ hour band having the *lowest* median is an artefact. Long holds
  concentrate in stable, low-variance zones; they're the ones where nothing was changing
  anyway.

**Caveat, stated because it bounds the whole result:** a repeated value isn't proof of a
carry-forward. A stable grid can report the same rounded number twice. 423 of the
2,152 runs are single repeats and are the most likely to be coincidental. The measurement
excludes series that never vary at all, but it can't separate a true carry from a true
coincidence within a varying series.

### The false zero: the most serious defect this work found

The three worst runs in the table all look like this:

```
gcp/europe-west4    held 23.17 h    carried 0.0 -> fresh 460.8    error 460.8
azure/westeurope    held 23.17 h    carried 0.0 -> fresh 460.8    error 460.8
scaleway/nl-ams     held 23.17 h    carried 0.0 -> fresh 460.8    error 460.8
```

An intensity of exactly **0.0 gCO2/kWh** marks a hollow feed. It's what
`calculate_carbon_intensity` returns when the fuel mix sums to zero. Three Netherlands
cloud regions were published at 0.0 for **23 hours**, then jumped to 460.8. The Netherlands
is one of Europe's dirtier grids; we measured it at 529 gCO2/kWh on the day of writing.

This is worse than a zone going dark. **0.0 is the best score a carbon-aware router can
see**, so a zone whose feed has gone hollow loses its data and wins every
routing decision, every `/route` call, and every "greenest region" recommendation until
someone notices. For 23 hours, the correct answer to "where should I run this job" was
being outranked by a broken feed.

Scale: 72 points, 0.18% of the archive, 3 of 116 series, all Netherlands, none currently
occurring. Rare, and severe when it happens.

**Cause.** The ENTSO-E adapter already guarded `if not fuel_mix: raise`. But a mix that's
*present and entirely zero* (an upstream document reporting `<quantity>0</quantity>` for
every fuel) is a truthy dict, so it passed the guard and averaged to 0.0.

**Fixed 2026-08-23.** `intensity_from_fuel_mix` now raises when nothing is generating,
which makes the provider cascade fall through to the next source, exactly as it already
does for a failed fetch. The guard uses the same definition of "generating" the average
uses, so a mix of nothing but discharging storage is caught too. Five regression tests in
`tests/test_emission_factors.py` cover the empty, all-zero, negative-only and storage-only
cases.

## 5. What the factor-corpus change did to reported numbers

**Status: MEASURED.** Live ENTSO-E across 29 European zones, sampled 2026-08-23.
Raw: [`data/validation/factor-change-impact.json`](../data/validation/factor-change-impact.json).
Script: [`factor_change_impact.py`](../scripts/validation/factor_change_impact.py).

Consolidating the emission-factor corpus moved four things: coal 900 -> 820, gas 430 -> 490,
solar 41 -> 48, and storage from "factor 0, counted in the denominator" to "excluded". Each
is defended in `data/emission-factors.json`. This measures the combined effect on real
grids rather than asserting it's small.

**Mean absolute change 3.9%, mean signed change +2.0%, maximum 12.3%, 20 zones up and 9 down.**

| Zone | Before | After | Δ% | coal % | gas % |
|---|---|---|---|---|---|
| ES | 141.1 | 158.5 | +12.3% | 0.0 | 28.7 |
| IT-NO | 283.5 | 317.7 | +12.0% | 0.0 | 57.0 |
| BE | 239.0 | 260.0 | +8.8% | 0.0 | 35.0 |
| ME | 415.1 | 378.8 | -8.7% | 44.7 | 0.0 |
| PL | 589.4 | 550.8 | -6.6% | 56.8 | 11.4 |
| CZ | 364.7 | 341.2 | -6.4% | 34.1 | 6.2 |
| DE | 333.9 | 317.9 | -4.8% | 27.0 | 9.4 |
| FR | 36.0 | 37.3 | +3.7% | 0.0 | 2.2 |

The direction is exactly what the factor changes predict and is a useful check that the
change did what it was supposed to: **gas-heavy zones rose, coal-heavy zones fell**, and
the split tracks fuel share cleanly. Nothing moved by a surprising amount, and no zone
changed rank order in a way that would flip a routing decision at these magnitudes.

This is the number to quote if anyone asks whether "just using the published medians"
mattered. It moved every European zone by an average of 4%, in a consistent, explicable
direction, and it removed a disagreement with a sibling project that had persisted
silently.

## 6. How much of the UK/EU difference is accounting basis rather than grid

**Status: MEASURED.** NESO live API, settlement period 2026-08-23T20:00Z-20:30Z.
Raw: [`data/validation/accounting-basis-gap.json`](../data/validation/accounting-basis-gap.json).
Script: [`accounting_basis_gap.py`](../scripts/validation/accounting_basis_gap.py). Needs no
credentials.

UK zones don't use this project's emission factors at all. They carry NESO's published
intensity, computed on a **direct combustion** basis in which wind, solar, hydro, nuclear
and pumped storage all score exactly 0. Every fuel-mix zone carries an **IPCC lifecycle**
intensity in which those score 11, 48, 24 and 12. `/route` ranks them against each other.

Taking NESO's own generation mix for one settlement period and recomputing it under this
project's lifecycle factors:

| | gCO2/kWh |
|---|---|
| NESO published (direct basis) | **172** |
| Same mix, same instant, our lifecycle basis | **275.9** |
| Gap | **+103.9 (+60.4%)** |

Same grid, same instant, same mix. The entire difference is where the system boundary is
drawn.

**Sensitivity.** 27.7% of the UK mix that period was interconnector imports, which land in
this project's unsourced `other` bucket at 300. NESO prices each interconnector separately.
Substituting their figures bounds how much of the gap is that one assumption:

| Imports priced at | Lifecycle result |
|---|---|
| our `other` assumption, 300 | 275.9 |
| NESO French interconnector, 53 | 207.5 |
| NESO Irish interconnector, 458 | 319.6 |
| NESO Dutch interconnector, 474 | 324.1 |

Even at the most flattering assumption the gap is **+21%**. The mixed basis is real and it
isn't an artefact of the import factor.

**Consequence.** A UK zone is reported systematically cleaner than an equivalently dirty
fuel-mix zone, and the gap widens as UK renewable output rises, because that's exactly
when the direct basis is scoring the most generation at zero. Any cross-zone comparison
involving the UK is biased toward the UK.

**What was done about it.** Both numbers are correct on their own terms and NESO's is the
authoritative figure for the UK, so the gap is surfaced. Every reading
now carries `provenance.accounting_basis` (`production_direct` vs `production_lifecycle` vs
`consumption_lifecycle`) and UK readings carry an explicit caveat, so a caller comparing
two zones can see that they aren't the same quantity. A contract test asserts the two
bases stay distinguishable.

---

## Reproducing all of this

```bash
# No credentials needed
uv run python scripts/validation/accounting_basis_gap.py
uv run python scripts/validation/carry_forward_error.py

# Free ENTSO-E token (https://transparency.entsoe.eu/)
CARBON_LENS_ENTSOE_TOKEN=... uv run python scripts/validation/production_vs_consumption.py
CARBON_LENS_ENTSOE_TOKEN=... uv run python scripts/validation/factor_change_impact.py

# Credentials this project doesn't have
WATTTIME_USERNAME=... WATTTIME_PASSWORD=... uv run python scripts/validation/watttime_backtest.py
CARBON_LENS_ELECTRICITY_MAPS_API_KEY=... uv run python scripts/validation/electricity_maps_compare.py
```

The carry-forward analysis reads the published archive directly over HTTP, so it needs
nothing but a network connection, and it covers a longer window than ours as the
archive grows.

## What is still not validated

Stated so the gaps aren't mistaken for clean bills of health:

- **The marginal heuristic.** Unvalidated against anything. §1.
- **Every heuristic estimator.** Eskom, Grid India and ONS Brazil fallbacks, Québec's fixed
  30, and the Open-Meteo weather mapping have no ground truth here and, in the Open-Meteo
  case, no source for the method either. All are tier E and flagged in the API response.
- **Absolute accuracy anywhere.** Nothing above compares a CarbonLens number against a
  measured physical quantity. §3 compares two of our own methods, §5 compares us against
  our former selves, §6 compares two accounting boundaries. Only §1 and §2 would test
  absolute accuracy, and both are unrun.
- **The `other` bucket.** 300 gCO2/kWh, no source, and it carries 27.7% of the UK mix and
  every unclassified import elsewhere. Its plausible range spans 300 to 700. This is the
  largest single unquantified uncertainty in the system.
