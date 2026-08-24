# Verification record

An audit of the highest-risk claims in this project's README, code comments and API
responses, chased to primary sources, with the verdicts published including the failures.
Date: 2026-08-23.

Verdict vocabulary. **RESOLVED**: primary text obtained and quoted. **FIXED**: resolved and
the code changed. **PARTIALLY RESOLVED**: some sub-claims proven, others not.
**UNRESOLVABLE**: searched properly, no source located, and the product now says so rather than
implying a source exists.

Fourteen claims audited against primary sources. Eight produced fixes, three of which
changed numbers the API served; the rest are confirmed, or declared as assumptions where no
source exists.

| # | Item | Verdict |
|---|---|---|
| 1 | IPCC AR5 factor table: which rows, and which values | **FIXED**: solar 41 -> 48, coal 900 -> 820, gas 430 -> 490 |
| 2 | The `650` oil factor's provenance | RESOLVED: a 2006 UK POSTnote; AR5 has no oil row; tiered C |
| 3 | `lignite`, `waste`, `thermal_mix`, `other` | UNRESOLVABLE, now declared as assumptions |
| 4 | `battery: 0` and storage in the denominator | **FIXED**: storage excluded from the average |
| 5 | UK renewable-percentage estimator | **FIXED**: now reads NESO's published mix (was +46.9 pp) |
| 6 | "UK (18 zones)" | **FIXED**: provider bug; zones were unreachable via the API |
| 7 | Publishing `0.0 gCO2/kWh` for a hollow feed | **FIXED**: hollow feeds now fall through |
| 8 | Mixed accounting basis between UK and fuel-mix zones | RESOLVED, surfaced in every reading |
| 9 | GHG Protocol data-quality grades | **FIXED**: derived from the provenance registry |
| 10 | Provider PUE constants | **FIXED**: all three updated to current vendor figures |
| 11 | Scope 2 dual-reporting conformance | PARTIALLY RESOLVED, limitation documented |
| 12 | The Open-Meteo weather-to-carbon mapping | UNRESOLVABLE, tier E, flagged in the API |
| 13 | Heuristic time-of-day curves (Eskom, India, Brazil, Québec) | UNRESOLVABLE, tier E, flagged |
| 14 | The REC-matching argument in "Why This Exists" | RESOLVED, now cited |

---

## 1. The IPCC AR5 factor table

**Verdict: FIXED from primary text. Two values corrected; a third confirmed and its row
documented.**

`emission_factors.py` cited "IPCC AR5 WG3 (2014), Annex III, Table A.III.2" for its whole
factor table. That citation is correct and the table is real. It was never checked against.

The PDF was downloaded in full from `ipcc.ch` and Table A.III.2 read directly (page 1335 of
the printed report). Lifecycle emissions, gCO2eq/kWh, min / **median** / max:

| Row | Published |
|---|---|
| Coal (PC) | 740 / **820** / 910 |
| Gas (Combined Cycle) | 410 / **490** / 650 |
| Biomass (cofiring) | 620 / **740** / 890 |
| Biomass (dedicated) | 130 / **230** / 420 |
| Geothermal | 6.0 / **38** / 79 |
| Hydropower | 1.0 / **24** / 2200 |
| Nuclear | 3.7 / **12** / 110 |
| Concentrated Solar Power | 8.8 / **27** / 63 |
| Solar PV (rooftop) | 26 / **41** / 60 |
| Solar PV (utility) | 18 / **48** / 180 |
| Wind onshore | 7.0 / **11** / 56 |
| Wind offshore | 8.0 / **12** / 35 |
| Ocean | 5.6 / **17** / 28 |

### 1.1 `solar: 41` was the wrong row

The code said:

```python
"solar": 41,  # utility PV median
```

**41 is the ROOFTOP median. The utility median is 48.** The comment recorded the right
intent and the value didn't match it, so the value was corrected rather than the comment.

Utility is the correct row because balancing-authority fuel-mix feeds report utility-scale
generation; behind-the-meter rooftop doesn't appear in them at all. EIA's 2023 data,
queried directly, splits 162,683 GWh of utility-scale PV from 73,406 GWh of small-scale
distributed PV, and only the former is in the hourly mix this project reads.

### 1.2 `coal: 900` and `natural_gas: 430` were undeclared deviations with weak reasons

Both were annotated inline, which is better than nothing, and neither reason survives
contact with the source.

- `coal: 900  # conservative; IPCC median is 820, but subcritical/lignite runs higher`.
  The AR5 median is already a global median across a fleet that's largely subcritical, and
  the argument runs the other way for supercritical units. A 10% upward fudge applied to
  every coal-heavy zone is an unstated thumb on the scale. Now 820,
  with lignite available as a separate key for feeds that report it.
- `natural_gas: 430  # efficient CCGT end; IPCC median is 490`. Real gas fleets mix CCGT
  with open-cycle peakers, which are *worse* than the median, and the AR5 median already
  includes 91 gCO2eq/kWh of upstream methane. Picking the efficient end understated every
  gas-heavy zone. Now 490.

### 1.3 `wind: 11` was right, and the row is now documented

11 is the **onshore** median; 12 is offshore. The companion project used 12. Neither table
said which row it meant. The values differed because of an undocumented
disagreement about which row to read. Resolved to onshore, because onshore dominates the
generation these feeds report: EIA's 2023 US figures are 421,007 GWh onshore against 134
GWh offshore.

### 1.4 What this cost

Measured on 29 live European zones: **mean absolute change 3.9%, maximum 12.3%**, with
gas-heavy zones rising and coal-heavy zones falling exactly as the changes predict. Full
table in [`VALIDATION.md`](./VALIDATION.md) §5.

Every factor now lives in `data/emission-factors.json` with its citekey, the exact row, that
row's published range, and a reason for any deviation. A test asserts every value claiming
an IPCC row falls inside that row's published min/max. The loader refuses to start if any
factor has neither a resolvable citekey nor a declared assumption.

## 2. Where `650` for oil actually comes from

**Verdict: RESOLVED. The 650 is a 2006 UK POSTnote figure, and both this project and its
companion implied it was an IPCC value.**

**Table A.III.2 has no oil row at all.** It has no lignite row and no waste row either. The
code's honest inline note (`no IPCC median row; mid-range diesel/HFO lifecycle estimate`)
was right that there's no row, and wrong to describe the value as an estimate: 650 was
inherited from another table.

Traced through the Electricity Maps published default table, which attributes its 650 to
"UK Parliamentary Office of Science and Technology". The primary was then obtained and read.

`parliament.uk`, `post.parliament.uk` and `researchbriefings.files.parliament.uk` all return
HTTP 403 to automated clients, with and without a browser User-Agent. The document was
retrieved through the Wayback Machine. **POSTnote 268, October 2006**, page 2, verbatim:

> The average carbon footprint of oil-fired electricity generation plants in the UK is
> ~650gCO2eq/kWh.

Note what that actually is, because it's much weaker than the use it's put to. The same
page states oil supplied **1% of UK generation** and ran mainly as peaking back-up. So the
figure is a **UK-fleet average, from 2006, for a marginal fuel**, twenty years old, with
no AR5 row behind it. It's tiered **C** accordingly, the
lowest tier of any cited factor.

**Also resolved: where Electricity Maps' `45` for solar comes from.** It appears nowhere in
AR5 despite being labelled "IPCC 2014". It's the midpoint of the rooftop (41) and utility
(48) rows: a vendor's editorial choice presented as an IPCC value. The companion project
carried 45, which means its table was copied from there rather than read out of AR5.

## 3. The buckets with no source at all

**Verdict: UNRESOLVABLE. Now declared as assumptions rather than passing as cited values.**

| Key | Value | Status |
|---|---|---|
| `lignite` | 1050 | No AR5 row. Above the Coal (PC) published maximum of 910. Two unconfirmed leads recorded in the corpus (a German UBA figure of 1054, and the midpoint of a published lignite range); neither was read here. |
| `waste` | 580 | No AR5 row. Table A.III.11 in the same annex covers waste *treatment* only, which doesn't support a waste-to-energy electricity factor. |
| `thermal_mix` | 750 | A blended coal+gas bucket for feeds reporting undifferentiated "thermal". Implies roughly a 79/21 coal/gas split. Never derived from published generation shares. |
| `other` | 300 | The catch-all, and **the largest single unquantified uncertainty in the system**. |

`other` deserves its own paragraph. The old comment called 300 a "conservative placeholder".
The direction of that conservatism is backwards: if the unknown bucket is in fact thermal,
300 *understates* it badly. Electricity Maps assigns 700 to the comparable bucket on a
stated assumption of thermal generation, so the plausible range spans **300 to 700**. It was
left at 300 because there's no evidence to prefer either end and moving it would be an
unforced behavioural change, but the uncertainty is now visible rather than implied.

One lead worth recording: NESO's published UK factor table assigns its own "Other" bucket
exactly **300**. This value may have been taken from there rather than assumed
independently. Unconfirmed, and NESO's table is direct-combustion rather than lifecycle, so
it wouldn't license the number on this corpus's basis even if true.

This matters more than its 300-gram face value suggests: `other` carries **27.7% of the UK
generation mix** (interconnector imports) and every unclassified import elsewhere.

**Every one of these is now surfaced to API consumers.** A reading whose fuel mix contains
an assumed bucket carries it in `provenance.assumed_factors`, so a caller can see that part
of the number is a guess.

## 4. `battery: 0` and storage in the denominator

**Verdict: FIXED 2026-08-23.**

The code carried:

```python
"battery": 0,  # storage: discharge emissions belong to the charging source; zero is wrong
```

The comment correctly identified that 0 is wrong and then shipped 0 anyway. Worse, storage
stayed in the **denominator** of the weighted average. The effect is large: a mix of
500 MW coal and 500 MW discharging battery averaged to **410 gCO2/kWh** when the correct
answer is 820. Every megawatt of battery discharge diluted a zone's intensity toward zero.

The right treatment is exclusion: **storage isn't generation**.
Discharge re-delivers energy whose emissions were already attributed when it was generated,
so counting it again double-counts the energy. It's now excluded from both the numerator
and the denominator, and from the renewable-percentage calculation.

Two notes on the fix:

- The companion project already got this right (`EIA_STORAGE_FUELS = {"BAT", "PS"}`) and
  this project didn't. The shared corpus now enforces one answer for both.
- **Electricity Maps takes a different, also-defensible line**: they assign battery
  discharge the world-average intensity (301). That attributes rather than excludes, and it
  is better than exclusion *if* you have charge-source attribution. Without it, exclusion is
  the more honest of the two. Recorded in the corpus so the choice is visible.

`pumped_storage` was added as a second storage key; EIA reports it as `PS` and this project
previously had no mapping for it at all, so it fell to the `other` bucket at 300.

## 5. The UK renewable-percentage estimator

**Verdict: FIXED 2026-08-23.**

This is the largest single numerical error found.

```python
def _estimate_renewable_pct(intensity: float) -> float:
    """UK grid: ~0 gCO2/kWh = 100% renewable, ~450+ = 0% renewable."""
    pct = max(0.0, (1 - intensity / 450) * 100)
```

No source, and it's inferring one physical quantity from another with a straight line and a
guessed anchor. NESO publishes the actual generation mix, free, **in a response this module
was already fetching**, so the estimate was never necessary.

Measured against NESO's own published mix over **97 half-hour settlement periods**
(2026-08-21 to 2026-08-23):

| | Result |
|---|---|
| Mean error vs wind+solar+hydro | **+46.9 percentage points** |
| Mean absolute error | **46.9 pp** (identical, so it *never once* understated) |
| Mean error counting biomass as renewable | +36.6 pp |
| Estimator output range | 60.7% to 87.8% |
| True renewable range | 10.3% to 51.2% |

**The two ranges don't overlap.** There's no half-hour in the sample where the estimator
produced a value that reality also produced.

The cause is a system-boundary error. NESO's intensity is **direct combustion**, so wind,
solar, hydro *and nuclear* all score 0 and UK intensity sits structurally far below 450. A
450 anchor therefore reads almost any UK half-hour as predominantly renewable, and reads
nuclear-heavy periods as renewable for the same reason. The formula looks like it was
designed against a lifecycle-style scale and applied to a direct one.

**Fixed** by reading NESO's published mix (`renewable_pct_from_mix`). Biomass and imports
are excluded, matching the corpus's treatment of biomass as combustion. The broken function
is retained, deprecated, with the measurement in its docstring, and a test pins its wrong
output so it can't be quietly reused. Raw data:
[`data/validation/uk-renewable-estimator.json`](../data/validation/uk-renewable-estimator.json).

## 6. "UK (18 zones)"

**Verdict: FIXED 2026-08-23. The provider code for 17 of the 18 zones raised on every
call; those zones are also unreachable through the public API, so the user-facing defect was
the README's coverage claim.**

Found while fixing §5. The README's data-source table advertises "UK (18 zones)" as a **Live
API**. In fact only `GB` worked.

```python
intensity = region["intensity"]["actual"] or region["intensity"]["forecast"]
```

NESO's `/regional` endpoint publishes only `forecast` and `index`. **It carries no `actual`
key at all**, unlike `/intensity`, which does. So this raised `KeyError: 'actual'` for
every regional zone. The single-zone path propagated it; the batch path caught
`(httpx.HTTPError, ValueError, KeyError)` and dropped the zones on the floor.

**Impact.** `GB-1` through `GB-17` are NESO distribution regions. **No cloud region maps to any of
them** (`data/region_grid_map.yaml` contains zero `GB-N` entries), and the zone endpoint
gates on a zone having a cloud-region representative (`_require_zone`), so
`GET /api/v1/carbon/zone/GB-1` returns 404 and always did. Verified against production after
deploying the fix.

Precisely:

- The **code path was broken**. The `KeyError` was real, and any caller reaching
  the provider directly, or any future mapping of a cloud region onto a `GB-N` zone, would
  have hit it.
- **No API consumer was served a degraded UK regional number**, because no API consumer
  could request one.
- What was actually wrong for users was the **README's coverage claim**. "UK (18 zones)"
  described a provider capability that didn't work and that the API didn't expose.

Had those zones been reachable, the failure would still have been well-handled rather than
loud: they would have fallen through the cascade to an Open-Meteo estimate or mock data with
the `source` field reporting `open_meteo` or `mock`. The provenance labelling was
working correctly throughout. Only the README's claim was wrong.

Fixed with a `_region_intensity` helper that prefers `actual`, falls back to `forecast`, and
raises rather than inventing a value when neither is present. It deliberately does **not**
use an `or` chain: `0` is a legitimate NESO value for a wind-dominated region on their
direct basis (North Scotland reported exactly 0 during testing, with a 99.8% wind mix), and
an `or` chain would silently discard it. All 18 zones now return live NESO data at the
provider level (verified directly: `GB-1` 0 gCO2/kWh at 99.8% wind, `GB-13` 171, `GB-17`
331); five tests cover the payload shapes. Exposing them through the API would additionally
require mapping cloud regions onto them, which this change doesn't do.

## 7. Publishing `0.0 gCO2/kWh` for a hollow feed

**Verdict: FIXED 2026-08-23.** Found by the carry-forward analysis in
[`VALIDATION.md`](./VALIDATION.md) §4, where it's documented in full.

Three Netherlands cloud regions were published at **0.0 gCO2/kWh for 23 hours**, then jumped
to 460.8. An exact 0.0 marks a hollow feed; it's what a weighted average over a
zero-summing fuel mix returns.

This is worse than a zone going dark, because **0.0 is the best score a carbon-aware router
can see**. A zone whose feed goes hollow is handed the routing decision, and wins every
one of them. For 23 hours the correct answer to "where should I run this job" was being
outranked by a broken feed.

The adapters guarded `if not fuel_mix: raise` but a mix that's *present and entirely zero*
is a truthy dict. `intensity_from_fuel_mix` now raises when nothing is generating, using the
same definition of "generating" the average uses, so a mix of nothing but discharging
storage is caught too. The provider cascade then falls through to the next source, exactly
as it already does for a failed fetch.

Scale: 72 points, 0.18% of the published archive, 3 of 116 series. Rare and severe.

## 8. The mixed accounting basis

**Verdict: RESOLVED. Surfaced rather than silently corrected.** Measured in
[`VALIDATION.md`](./VALIDATION.md) §6.

CarbonLens doesn't report every zone on the same basis, and had never said so.

- Fuel-mix zones: **IPCC lifecycle**. Wind 11, solar 48, nuclear 12.
- UK zones: **NESO direct combustion**. Wind, solar, hydro, nuclear and pumped storage all
  exactly 0.

`/route` ranks them against each other as though they were the same quantity. Taking NESO's
own mix for one settlement period and recomputing it on this project's lifecycle factors:
NESO published **172**, the same mix on a lifecycle basis is **275.9**, a **+60.4%** gap
from methodology alone. Even pricing the 27.7% interconnector share at NESO's most flattering
own figure, the gap is +21%.

**Both numbers are right on their own terms**, and NESO's is the
authoritative figure for the UK, so the difference is surfaced. Every reading now carries
`provenance.accounting_basis` (`production_direct` / `production_lifecycle` /
`consumption_lifecycle`), UK readings carry an explicit caveat naming the problem, and a
contract test asserts the two bases stay distinguishable.

This is the finding most likely to matter to someone actually using the API to choose a
region, and it was invisible before this audit.

## 9. GHG Protocol data-quality grades

**Verdict: FIXED 2026-08-23.**

The compliance calculator graded each emissions record's data quality from a local list:

```python
measured = {"uk", "eia", "aemo", "entsoe", "grid_india", "ons_brazil", "eskom", "gridstatus"}
```

Four of those eight strings match nothing any provider emits. Providers stamp
`uk_carbon_intensity`, `openelectricity`, `eskom_heuristic`, `taipower`, `ieso`, `aeso`. So:

- every **UK, Australian, Canadian and Taiwanese** reading was graded `estimated` on a
  compliance report despite coming from a live grid-operator feed;
- the **Eskom time-of-day model**, which is a fixed curve with no source, would have graded
  `measured` had its string matched.

The existing test passed because it asserted on `_data_quality("uk")`, a string that never
occurs in production. It encoded the bug.

Fixed by deriving the grade from the provenance registry, so there's one source of truth
for source classification instead of two lists that could drift. The test now asserts on the
strings providers actually emit, and a contract test asserts the calculator and the registry
agree for every classified source.

## 10. Provider PUE constants

**Verdict: RESOLVED. All three were stale; all three corrected.**

```python
"aws": 1.135,   # AWS 2023 sustainability report
"gcp": 1.10,    # Google 2023 (best-in-class)
"azure": 1.18,  # Microsoft 2023 sustainability report
```

All three vendor pages were read on 2026-08-23.

| Provider | Was | Now | Published, verbatim |
|---|---|---|---|
| AWS | 1.135 | **1.14** | "In 2025, our data centers reported an average global PUE of 1.14 which is an improvement compared to 1.15 reported in 2024." |
| Google | 1.10 | **1.09** | "In 2025, the average annual power usage effectiveness for our global fleet of data centers was 1.09." |
| Microsoft | 1.18 | **1.17** | Published table: global 1.16 (FY24), 1.17 (FY25) |

The AWS figure is the notable one: **1.135 matches no figure AWS has ever published**. It
looks like an average of two numbers or a transcription artefact.

Two limitations remain, now written into the code rather than left implicit:

- These are **global fleet averages**, but AWS and Microsoft both publish **per-region** PUE,
  and the spread is material: Microsoft's FY25 Asia Pacific figure is **1.28** against 1.16
  in the Americas. This project maps cloud regions and could use per-region values.
- The reporting periods differ. AWS and Google report calendar 2025; Microsoft reports FY25
  ending 30 June 2025.

All three are **tier D**: self-reported by the vendor with no independent audit. The
`default: 1.20` for providers that publish nothing has no citation and is now labelled as
a guess.

## 11. GHG Protocol Scope 2 conformance

**Verdict: PARTIALLY RESOLVED. The methods are implemented correctly; a reporting
requirement goes unmet, and that's now documented.**

The Scope 2 Guidance PDF was downloaded and read (`ghgprotocol.org` HTML pages return 403 to
automated clients, but the PDF doesn't). The glossary definitions match what
`AccountingMethod` implements, verbatim:

> **Location-based method for scope 2 accounting**: A method to quantify scope 2 GHG
> emissions based on average energy generation emission factors for defined locations,
> including local, subnational, or national boundaries.

> **Market-based method for scope 2 accounting**: A method to quantify scope 2 GHG emissions
> based on GHG emissions emitted by the generators from which the reporter contractually
> purchases electricity bundled with instruments, or unbundled instruments on their own.

**The gap is §1.5.1**, verbatim:

> Companies with any operations in markets providing product or supplier-specific data in
> the form of contractual instruments **shall report scope 2 emissions in two ways** and
> label each result according to the method: one based on the location-based method, and one
> based on the market-based method. This is also termed "dual reporting."

`EmissionsCalculator.calculate()` takes a single `method` and returns a single figure, so a
caller can produce a one-method report that doesn't conform. Documented in the calculator's
docstring; callers wanting conformance must run it twice and report both.

A second limitation, unprompted by the standard: the Scope 2 / Scope 3 Category 1 split keys
off a **hardcoded list of managed service names**. That boundary is this project's own
judgement. The standard doesn't enumerate cloud services.

## 12. The Open-Meteo weather-to-carbon mapping

**Verdict: UNRESOLVABLE. No source exists, because the method is this project's own
invention. Tier E and flagged in every response.**

The README already says this is "not a carbon measurement", which was honest. The audit's
job was to establish whether anything backs the mapping. Nothing does:

```python
solar_pct = min(40.0, (radiation / 1000) * 40)
wind_pct = min(30.0, ((wind_speed - 12) / 33) * 30) if wind_speed > 12 else 0.0
```

The 40% solar cap, the 30% wind cap, the 12 km/h cut-in, the 33 km/h span, and the baseline
intensity divisor are all invented. Open-Meteo is a good weather source and the irradiance
and wind data are real; **nothing published anywhere licenses the step from those to a grid
carbon intensity**, which depends on installed capacity, curtailment, demand and dispatch,
none of which this sees.

The citekey `open-meteo-api` is therefore tier **E**, and the tier is about the *carbon*
claim alone. Every `open_meteo` reading now carries
`source_class: "estimated"`, `accounting_basis: "none"`, `evidence_tier: "E"` and a caveat
saying in plain words that the mapping has no source.

## 13. The heuristic time-of-day curves

**Verdict: UNRESOLVABLE. All assumed, all now tier E and flagged.**

| Source | The claim | Status |
|---|---|---|
| `eskom_heuristic` | ~780 gCO2/kWh base, ×0.92 at midday, ×1.02 at night | No source for the base or the curve shape. South Africa's grid being coal-dominated is well established; **this specific curve has no such backing**. |
| `grid_india_heuristic` | Per-region fallback with a time-of-day adjustment | Baseline read from the mock table. No source for either. |
| `ons_brazil_heuristic` | Per-region fallback | Same. |
| `hydro_quebec_heuristic` | Fixed 30 gCO2/kWh, 95% renewable | A fixed guess that **never changes hour to hour**. Hydro-Québec publishes no free real-time feed. |

None of these is indefensible as demo coverage. All four were presented with the same
`source` labelling as live feeds, distinguished only by a `_heuristic` suffix a caller had to
notice. All four now carry `source_class: "modeled"`, `evidence_tier: "E"`, and a caveat
beginning "ASSUMED".

Québec is the weakest: a fixed number that never varies can only be a constant wearing
an estimate's clothes, because the quantity it claims to estimate varies with time.

## 14. The REC-matching argument

**Verdict: RESOLVED. The argument is sound and is now cited. One source doesn't say what it
would be convenient for it to say.**

The README's opening argument, that annual REC matching is a weaker claim than hourly
matching, was asserted with no source. It's a real position in the literature and is now
backed by `riepin-2024-247-cfe`, `ricks-2023-hourly-matching`, `miller-2022-hourly-accounting`
and `google-2021-247-cfe` (tier D, a corporate white paper with an obvious interest in the
conclusion, cited for the argument's canonical statement and not as evidence for it).

**One caveat carried over and re-checked.** `energytag-gc-standard-v2` is in the corpus and
does **not** support the argument. It defines the granular-certificate machinery that makes
hourly matching auditable; it doesn't itself claim annual matching is weaker. Citing it for
the argument would be a misattribution, and its record says so.

The corpus also deliberately carries sources **against** this project's own positions:
`wiesner-2025-marginal-poor-metric` argues marginal intensity is a poor metric for load
shifting, which is a metric this API reports.

---

## What was checked and found correct

Recorded so the document works as an audit as well as a defect list.

- The IPCC AR5 Annex III citation itself: correct, and the table matches what the code claims.
- `nuclear: 12`, `hydro: 24`, `geothermal: 38`, `biomass: 230`, `marine: 17`: all match the
  published medians exactly.
- `biomass` excluded from renewable and carbon-free percentages despite AR5 grouping it with
  renewables: a deliberate and defensible choice, now documented.
- The flow-tracing implementation: the linear system in `flow_tracing.py` matches Tranberg et
  al. (2019), the paper was already named in the docstring, and the Gauss-Seidel convergence
  argument from diagonal dominance is correct. The proportional-sharing assumption it
  inherits from Bialek (1996) was undocumented and is now stated.
- The `source` field: already honest everywhere it was checked. When the UK regional zones
  were silently failing (§6), the fallback readings correctly reported themselves as
  `open_meteo` or `mock`. The labelling was right; the README's claim above it was wrong.
- XML parsing via `defusedxml`: as described.
- The marginal merit-order comment's reasoning (gas rather than coal usually sets the margin,
  because it's the flexible peaker and the ordering is by cost rather than carbon): correct as
  economics, and unvalidated as a predictor. See §1 of [`VALIDATION.md`](./VALIDATION.md).
