# Citation corpus

49 sources (19 crossref-verified, 6 primary-read, 2 unverified, 22 url-verified). Machine-readable companion: [`CITATIONS.csl.json`](./CITATIONS.csl.json) (CSL-JSON).

**This file is generated.** Edit `CITATIONS.csl.json` and run
`uv run python scripts/generate_citations.py`. CI fails if the two drift apart.

Verification pass completed 2026-08-23 against the Crossref REST API and direct fetches of
publisher, standards-body, grid-operator and government URLs.

## How to read this

### Verification status

This says how the *bibliographic record* was checked. It says nothing about whether the finding is true.

| Status | Meaning |
|---|---|
| `primary-read` | The document itself was retrieved and the passage this project relies on was read and quoted. The strongest status here. |
| `crossref-verified` | The DOI resolves in Crossref and the returned title, authors, year, container, volume and pages were compared against what this corpus claims. Any discrepancy is written into the caveat. |
| `url-verified` | No DOI, or no need of one. An authoritative URL (publisher, standards body, grid operator, government) was fetched on 2026-08-23 and the document identity confirmed from the response itself. |
| `unverified` | Neither a resolvable DOI nor a successfully fetched authoritative URL. Usually because the host blocks automated clients. The bibliographic details may be wrong, and the caveat says so. |

A `crossref-verified` record can still carry a loud caveat. **Verification confirms the *citation*, and
the *claim* remains a separate question.** Several entries here are Crossref-verified but were paywalled to full-text fetch, meaning
this project confirmed the paper exists and matches its record here, and never read its numbers. Where a
number was actually read out of a document, the status is `primary-read` and the caveat quotes it.

### Access level

`open-access` | `paywalled` | `public-domain` (government, national-lab or intergovernmental output) |
`standard-purchase` (must be bought from a standards body).

### Evidence tier

The tier describes what the source licenses this product to *do* with the number. How good the
source is in the abstract plays no part. A first-rate weather API is tier E for a carbon claim, because nothing in it
licenses a carbon claim.

| Tier | Definition | Product treatment |
|---|---|---|
| A | A grid operator's or standards body's own published methodology | May drive a headline number |
| B | Peer-reviewed method, independently replicated | May drive a headline number |
| C | Peer-reviewed but single-study, or a method published without validation | Renders as estimated, never as measured |
| D | Vendor white paper or self-reported figure with a stated method | Labelled, advisory only |
| E | Assumed, folk knowledge, or no source found | Must be visibly flagged in the API response |

The API surfaces this: every carbon-intensity response carries a `provenance` block naming the
citekeys behind the number and the lowest evidence tier among them, and `GET /api/v1/citations`
serves this corpus over the wire.

### Counts

| Verification | n |
|---|---|
| `crossref-verified` | 19 |
| `primary-read` | 6 |
| `unverified` | 2 |
| `url-verified` | 22 |
| **total** | **49** |

| Access level | n |
|---|---|
| `open-access` | 36 |
| `paywalled` | 8 |
| `public-domain` | 4 |
| `standard-purchase` | 1 |

| Evidence tier | n |
|---|---|
| `A` | 18 |
| `B` | 18 |
| `C` | 5 |
| `D` | 6 |
| `E` | 2 |

| Group | n |
|---|---|
| `compute-energy` | 3 |
| `emission-factors` | 6 |
| `grid-data` | 16 |
| `methodology` | 15 |
| `standards` | 9 |

---

## Emission factors

6 sources.

#### `electricity-maps-default-factors`

Electricity Maps. (2026). *Default emission factors*. electricitymaps-contrib wiki

- URL: <https://github.com/electricitymaps/electricitymaps-contrib/wiki/Default-emission-factors>
- Verification: URL-verified | Access: open-access | evidence tier **D**
- Backs:
  - an independent implementation of the same problem also takes IPCC AR5 Annex III as its default factor table
  - the oil factor of 650 gCO2eq/kWh is attributed to the UK Parliamentary Office of Science and Technology, a source outside IPCC AR5
  - battery discharge is assigned world-average intensity (301), not zero
  - the 'unknown' fuel bucket is assigned 700 on a stated assumption of thermal generation
- **Caveat:** Page fetched and its factor table extracted on 2026-08-23, together with EMISSION_FACTORS_SOURCES.md from the same repository at master. This is a vendor's published default table with a stated method, hence tier D: it's cited as evidence of what another implementation does and of where the 650 oil figure is attributed, never as independent evidence that a number is correct.

#### `ipcc-ar5-wg3-annex3`

Schlömer, Steffen; Bruckner, Thomas; Fulton, Lew; Hertwich, Edgar; McKinnon, Alan; Perczyk, Daniel; Roy, Joyashree; Schaeffer, Roberto; Sims, Ralph; Smith, Pete; Wiser, Ryan. (2014). *Annex III: Technology-specific cost and performance parameters*. Climate Change 2014: Mitigation of Climate Change. Contribution of Working Group III to the Fifth Assessment Report of the Intergovernmental Panel on Climate Change 1329-1356

- URL: <https://www.ipcc.ch/site/assets/uploads/2018/02/ipcc_wg3_ar5_annex-iii.pdf>
- Verification: PRIMARY TEXT READ | Access: public-domain | evidence tier **A**
- Backs:
  - Table A.III.2 lifecycle emission medians for coal, gas, biomass, geothermal, hydro, nuclear, CSP, solar PV, wind and ocean
  - Table A.III.2 has separate rows for onshore and offshore wind, and for rooftop and utility solar PV
  - Table A.III.2 contains no row for oil, lignite, waste or an unknown/mixed bucket
- **Caveat:** PDF downloaded in full and Table A.III.2 read directly on 2026-08-23, not taken from secondary citation. Page 1335 of the printed report. Author list and the 'This annex should be cited as' string are transcribed from the annex's own front matter. Values are lifecycle gCO2eq/kWh including the albedo effect.

#### `neso-carbon-intensity-methodology`

National Grid ESO. (2021). *Carbon Intensity Forecast Methodology*. National Grid ESO / carbon-intensity

- URL: <https://github.com/carbon-intensity/methodology>
- Verification: URL-verified | Access: open-access | evidence tier **A**
- Backs:
  - the emission factors actually behind every UK zone carbon-lens reports, which are NESO's and not this project's
  - that those factors are DIRECT gCO2/kWh, scoring hydro, nuclear, solar and wind at exactly 0
- **Caveat:** Central to a limitation this project had not previously stated: UK zones come from the NESO Carbon Intensity API and therefore carry NESO's direct-combustion factors, while every fuel-mix zone carries this project's IPCC lifecycle factors. The two measure different quantities. Re-fetched and the live factor table read on 2026-08-23 from https://api.carbonintensity.org.uk/intensity/factors.

#### `staffell-2017-british-electricity`

Staffell, Iain. (2017). *Measuring the progress and impacts of decarbonising British electricity*. Energy Policy 102: 463-475

- DOI: [10.1016/j.enpol.2016.12.037](https://doi.org/10.1016/j.enpol.2016.12.037)
- Verification: Crossref-verified | Access: paywalled | evidence tier **B**
- Backs:
  - GB-specific generation emission factors, against which NESO's published direct factors can be sanity-checked
- **Caveat:** DOI re-resolved against the Crossref REST API on 2026-08-23 from this project; title, year, container, volume and pages matched the record below.

#### `turconi-2013-lca-electricity`

Turconi, Roberto; Boldrin, Alessio; Astrup, Thomas. (2013). *Life cycle assessment (LCA) of electricity generation technologies: Overview, comparability and limitations*. Renewable and Sustainable Energy Reviews 28: 555-565

- DOI: [10.1016/j.rser.2013.08.013](https://doi.org/10.1016/j.rser.2013.08.013)
- Verification: Crossref-verified | Access: paywalled | evidence tier **B**
- Backs:
  - the spread of published lifecycle factors per technology, i.e. that the corpus's point estimates hide real ranges
- **Caveat:** DOI re-resolved against the Crossref REST API on 2026-08-23 from this project; title, year, container, volume and pages matched the record below.

#### `uk-post-268-2006`

Parliamentary Office of Science and Technology. (2006). *Carbon Footprint of Electricity Generation*. Houses of Parliament, United Kingdom POSTnote 268

- URL: <https://www.parliament.uk/globalassets/documents/post/postpn268.pdf>
- Verification: PRIMARY TEXT READ | Access: public-domain | evidence tier **C**
- Backs:
  - the emission factor of 650 gCO2eq/kWh used for oil-fired generation
- **Caveat:** Read in full on 2026-08-23. parliament.uk returns HTTP 403 to every automated client (direct, and with a browser User-Agent); the document was retrieved through the Wayback Machine at web.archive.org/web/2019id_/. Verbatim, page 2: 'The average carbon footprint of oil-fired electricity generation plants in the UK is ~650gCO2eq/kWh.' Note what this actually is, because it's much weaker than the use it's put to: a UK-fleet average published in October 2006, for a fuel the same page says supplied 1% of UK generation and ran mainly as peaking back-up. It carries no standing as a global median or an IPCC figure, and it's twenty years old.

## Methodology

15 sources.

#### `bialek-1996-tracing-electricity`

Bialek, Janusz. (1996). *Tracing the flow of electricity*. IEE Proceedings - Generation, Transmission and Distribution 143: 313-320

- DOI: [10.1049/ip-gtd:19960461](https://doi.org/10.1049/ip-gtd:19960461)
- Verification: Crossref-verified | Access: paywalled | evidence tier **B**
- Backs:
  - the proportional-sharing assumption underlying the flow-tracing system in flow_tracing.py
- **Caveat:** DOI re-resolved against the Crossref REST API on 2026-08-23 from this project; title, year, container, volume and pages matched the record below. Cited as the origin of proportional sharing, the assumption that makes the tracing system solvable. flow_tracing.py inherits this assumption without stating it: a zone's exports are assumed to carry its whole consumed mix, which is a modelling choice and has no physical basis.

#### `dodge-2022-carbon-intensity-ai`

Dodge, Jesse; Prewitt, Taylor; Tachet des Combes,Remi; Odmark, Erika; Schwartz, Roy; Strubell, Emma; Luccioni, Alexandra Sasha; Smith, Noah A.; DeCario, Nicole; Buchanan, Will. (2022). *Measuring the Carbon Intensity of AI in Cloud Instances*. Proceedings of the 2022 ACM Conference on Fairness, Accountability, and Transparency 1877-1894

- DOI: [10.1145/3531146.3533234](https://doi.org/10.1145/3531146.3533234)
- Verification: Crossref-verified | Access: open-access | evidence tier **B**
- Backs:
  - measured emissions variation across cloud regions and hours, the premise of carbon-aware routing
- **Caveat:** DOI re-resolved against the Crossref REST API on 2026-08-23 from this project; title, year, container, volume and pages matched the record below.

#### `gagnon-2022-short-run-omits`

Gagnon, Pieter J.; Bistline, John E. T.; Alexander, Maxwell H.; Cole, Wesley J.. (2022). *Short-run marginal emission rates omit important impacts of electric-sector interventions*. Proceedings of the National Academy of Sciences 119: e2211624119

- DOI: [10.1073/pnas.2211624119](https://doi.org/10.1073/pnas.2211624119)
- Verification: Crossref-verified | Access: open-access | evidence tier **C**
- Backs:
  - that short-run marginal rates omit induced capacity effects, a stated limitation of the /signal marginal number
- **Caveat:** DOI re-resolved against the Crossref REST API on 2026-08-23 from this project; title, year, container, volume and pages matched the record below.

#### `hawkes-2010-marginal-emissions`

Hawkes, A.D.. (2010). *Estimating marginal CO2 emissions rates for national electricity systems*. Energy Policy 38: 5977-5987

- DOI: [10.1016/j.enpol.2010.05.053](https://doi.org/10.1016/j.enpol.2010.05.053)
- Verification: Crossref-verified | Access: paywalled | evidence tier **B**
- Backs:
  - marginal emission factors as the correct signal for a load-shifting decision, which is what /signal reports
- **Caveat:** DOI re-resolved against the Crossref REST API on 2026-08-23 from this project; title, year, container, volume and pages matched the record below. Backs the *concept* the merit-order heuristic in emission_factors.calculate_marginal_intensity() approximates, and nothing more: the heuristic is a fuel-mix rule of thumb, while this paper describes a regression method.

#### `hawkes-2014-long-run-marginal`

Hawkes, A.D.. (2014). *Long-run marginal CO2 emissions factors in national electricity systems*. Applied Energy 125: 197-205

- DOI: [10.1016/j.apenergy.2014.03.060](https://doi.org/10.1016/j.apenergy.2014.03.060)
- Verification: Crossref-verified | Access: open-access | evidence tier **B**
- Backs:
  - the distinction between short-run and long-run marginal factors, which the API doesn't currently draw
- **Caveat:** DOI re-resolved against the Crossref REST API on 2026-08-23 from this project; title, year, container, volume and pages matched the record below. The marginal number carbon-lens reports is short-run at best. This paper is the reason the provenance block says 'heuristic' rather than 'marginal emission factor'.

#### `holland-2022-marginal-not-decreasing`

Holland, Stephen P.; Kotchen, Matthew J.; Mansur, Erin T.; Yates, Andrew J.. (2022). *Why marginal CO2 emissions are not decreasing for US electricity: Estimates and implications for climate policy*. Proceedings of the National Academy of Sciences 119: e2116632119

- DOI: [10.1073/pnas.2116632119](https://doi.org/10.1073/pnas.2116632119)
- Verification: Crossref-verified | Access: open-access | evidence tier **B**
- Backs:
  - that marginal and average intensity can diverge in both direction and magnitude
- **Caveat:** DOI re-resolved against the Crossref REST API on 2026-08-23 from this project; title, year, container, volume and pages matched the record below.

#### `kirschen-1997-contributions`

Kirschen, Daniel; Allan, Ron; Strbac, Goran. (1997). *Contributions of individual generators to loads and flows*. IEEE Transactions on Power Systems 12: 52-60

- DOI: [10.1109/59.574923](https://doi.org/10.1109/59.574923)
- Verification: Crossref-verified | Access: paywalled | evidence tier **B**
- Backs:
  - the alternative common-generator formulation of the same tracing problem
- **Caveat:** DOI re-resolved against the Crossref REST API on 2026-08-23 from this project; title, year, container, volume and pages matched the record below. Cited for completeness as the competing formulation. This project implements the Bialek/Tranberg proportional-sharing line instead, and that choice carries consequences.

#### `maji-2022-carboncast`

Maji, Diptyaroop; Shenoy, Prashant; Sitaraman, Ramesh K.. (2022). *CarbonCast: multi-day forecasting of grid carbon intensity*. Proceedings of the 9th ACM International Conference on Systems for Energy-Efficient Buildings, Cities, and Transportation 198-207

- DOI: [10.1145/3563357.3564079](https://doi.org/10.1145/3563357.3564079)
- Verification: Crossref-verified | Access: paywalled | evidence tier **B**
- Backs:
  - multi-day grid carbon-intensity forecasting, the class of method /forecast approximates
- **Caveat:** DOI re-resolved against the Crossref REST API on 2026-08-23 from this project; title, year, container, volume and pages matched the record below. carbon-lens's non-ENTSO-E forecast is a time-of-day heuristic that falls well short of a model of this kind. Cited only for what the feature approximates.

#### `miller-2022-hourly-accounting`

Miller, Gregory J.; Novan, Kevin; Jenn, Alan. (2022). *Hourly accounting of carbon emissions from electricity consumption*. Environmental Research Letters 17: 044073

- DOI: [10.1088/1748-9326/ac6147](https://doi.org/10.1088/1748-9326/ac6147)
- Verification: Crossref-verified | Access: open-access | evidence tier **B**
- Backs:
  - hourly rather than annual accounting as the basis for the README's REC-matching argument
  - the value of an hourly time resolution for consumption-based accounting
- **Caveat:** DOI re-resolved against the Crossref REST API on 2026-08-23 from this project; title, year, container, volume and pages matched the record below.

#### `radovanovic-2023-carbon-aware-datacenters`

Radovanovic, Ana; Koningstein, Ross; Schneider, Ian; Chen, Bokan; Duarte, Alexandre; Roy, Binz; Xiao, Diyue; Haridasan, Maya; Hung, Patrick; Care, Nick; Talukdar, Saurav; Mullen, Eric; Smith, Kendal; Cottman, MariEllen; Cirne, Walfredo. (2023). *Carbon-Aware Computing for Datacenters*. IEEE Transactions on Power Systems 38: 1270-1280

- DOI: [10.1109/tpwrs.2022.3173250](https://doi.org/10.1109/tpwrs.2022.3173250)
- Verification: Crossref-verified | Access: open-access | evidence tier **B**
- Backs:
  - carbon-aware temporal load shifting in datacenters, the mechanism /schedule and /route implement
- **Caveat:** DOI re-resolved against the Crossref REST API on 2026-08-23 from this project; title, year, container, volume and pages matched the record below.

#### `ryan-2016-comparative-grid-methods`

Ryan, Nicole A.; Johnson, Jeremiah X.; Keoleian, Gregory A.. (2016). *Comparative Assessment of Models and Methods To Calculate Grid Electricity Emissions*. Environmental Science & Technology 50: 8937-8953

- DOI: [10.1021/acs.est.5b05216](https://doi.org/10.1021/acs.est.5b05216)
- Verification: Crossref-verified | Access: paywalled | evidence tier **B**
- Backs:
  - that average and marginal accounting answer different questions, which is why the API reports both
  - that the choice of grid-emissions method materially changes the answer
- **Caveat:** DOI re-resolved against the Crossref REST API on 2026-08-23 from this project; title, year, container, volume and pages matched the record below.

#### `siler-evans-2012-marginal-factors`

Siler-Evans, Kyle; Azevedo, Ines Lima; Morgan, M. Granger. (2012). *Marginal Emissions Factors for the U.S. Electricity System*. Environmental Science & Technology 46: 4742-4748

- DOI: [10.1021/es300145v](https://doi.org/10.1021/es300145v)
- Verification: Crossref-verified | Access: paywalled | evidence tier **B**
- Backs:
  - regression against observed generation as the standard way to estimate marginal factors
- **Caveat:** DOI re-resolved against the Crossref REST API on 2026-08-23 from this project; title, year, container, volume and pages matched the record below. Named here to mark the boundary: carbon-lens estimates marginal intensity from the running merit order, while this paper regresses marginal factors from observed generation. Cited as the method the heuristic is a cheap substitute for.

#### `tranberg-2019-flow-tracing`

Tranberg, Bo; Corradi, Olivier; Lajoie, Bruno; Gibon, Thomas; Staffell, Iain; Andresen, Gorm Bruun. (2019). *Real-time carbon accounting method for the European electricity markets*. Energy Strategy Reviews 26: 100367

- DOI: [10.1016/j.esr.2019.100367](https://doi.org/10.1016/j.esr.2019.100367)
- Verification: Crossref-verified | Access: open-access | evidence tier **B**
- Backs:
  - the flow-tracing linear system implemented in carbon_sources/flow_tracing.py
  - consumption-based intensity as the accounting basis for an import-heavy zone
- **Caveat:** DOI re-resolved against the Crossref REST API on 2026-08-23 from this project; title, year, container, volume and pages matched the record below. The module docstring already named this paper; this record makes it resolvable and ties it to the specific linear system in trace_consumption_intensity().

#### `wiesner-2021-lets-wait-awhile`

Wiesner, Philipp; Behnke, Ilja; Scheinert, Dominik; Gontarska, Kordian; Thamsen, Lauritz. (2021). *Let's wait awhile: how temporal workload shifting can reduce carbon emissions in the cloud*. Proceedings of the 22nd International Middleware Conference 260-272

- DOI: [10.1145/3464298.3493399](https://doi.org/10.1145/3464298.3493399)
- Verification: Crossref-verified | Access: open-access | evidence tier **B**
- Backs:
  - that temporal workload shifting reduces emissions, and by how much, for the scheduler's premise
- **Caveat:** DOI re-resolved against the Crossref REST API on 2026-08-23 from this project; title, year, container, volume and pages matched the record below.

#### `wiesner-2025-marginal-poor-metric`

Wiesner, Philipp; Kao, Odej. (2025). *Moving Beyond Marginal Carbon Intensity: A Poor Metric for Both Carbon Accounting and Grid Flexibility*. ACM SIGMETRICS Performance Evaluation Review 53: 108-111

- DOI: [10.1145/3764944.3764969](https://doi.org/10.1145/3764944.3764969)
- Verification: Crossref-verified | Access: open-access | evidence tier **C**
- Backs:
  - the counter-position that marginal intensity is a poor metric for load shifting
- **Caveat:** DOI re-resolved against the Crossref REST API on 2026-08-23 from this project; title, year, container, volume and pages matched the record below. Deliberately included against interest: this project reports a marginal signal and this paper argues the metric is weak for exactly that use. The corpus carries both sides.

## Grid data sources

16 sources.

#### `aeso-current-supply-demand`

Alberta Electric System Operator. (2026). *AESO Current Supply Demand Report*.

- URL: <https://www.aeso.ca/>
- Verification: URL-verified | Access: open-access | evidence tier **A**
- Backs:
  - the Alberta generation mix parsed in carbon_sources/canada.py
- **Caveat:** Site root fetched and confirmed on 2026-08-23.

#### `eia-electric-power-operational-data`

U.S. Energy Information Administration. (2024). *Electric Power Operational Data (electricity/electric-power-operational-data)*. U.S. Energy Information Administration

- URL: <https://api.eia.gov/v2/electricity/electric-power-operational-data/data/>
- Verification: URL-verified | Access: public-domain | evidence tier **A**
- Backs:
  - US 2023 all-sector net generation by fuel, used to weight the US fossil mix
  - onshore wind is 421,007 GWh of US 2023 wind generation against 134 GWh offshore, which is why the corpus takes the IPCC onshore row for wind
  - utility-scale PV is 162,683 GWh against 73,406 GWh small-scale distributed PV, which is why the corpus takes the IPCC utility row for solar
- **Caveat:** Queried directly with the project's own EIA key on 2026-08-23 for period 2023, sectorid 99 (all sectors), location US. The response is archived in docs/VERIFICATION.md. Figures are 'thousand megawatthours' (= GWh).

#### `eia-hourly-grid-monitor`

U.S. Energy Information Administration. (2026). *Hourly Electric Grid Monitor*. U.S. Energy Information Administration

- URL: <https://www.eia.gov/electricity/gridmonitor/about>
- Verification: URL-verified | Access: public-domain | evidence tier **A**
- Backs:
  - the hourly fuel-mix feed behind every US balancing-authority zone in carbon_sources/eia.py
  - that the reported mix is utility-scale generation, which is why the corpus takes the IPCC utility PV row
- **Caveat:** About page fetched on 2026-08-23. This is the feed the code reads; the annual dataset cited separately as eia-electric-power-operational-data is what the fossil-mix and wind/solar row checks were run against.

#### `electricity-maps-api`

Electricity Maps. (2026). *Electricity Maps API documentation*.

- URL: <https://static.electricitymaps.com/api/docs/index.html>
- Verification: URL-verified | Access: open-access | evidence tier **D**
- Backs:
  - the commercial carbon-intensity and marginal endpoints in carbon_sources/electricity_maps.py and marginal.py
- **Caveat:** Fetched on 2026-08-23. Commercial product: the values aren't independently auditable, so tier D even though the vendor is a serious one.

#### `ember-yearly-electricity-data`

Ember. (2026). *Yearly Electricity Data (full release, long format)*. Ember

- URL: <https://storage.googleapis.com/emb-prod-bkt-publicdata/public-downloads/yearly_full_release_long_format.csv>
- Verification: URL-verified | Access: open-access | evidence tier **A**
- Backs:
  - world power-sector CO2 intensity by year: 483.19 gCO2/kWh (2023), 471.46 (2024), 458.49 (2025)
- **Caveat:** Downloaded in full (49 MB) and read on 2026-08-23. Ember's CO2 intensity is DIRECT combustion CO2 for the power sector, a different basis from the lifecycle basis of the emission-factor corpus, so the two figures aren't directly comparable. Never cite it as a lifecycle number.

#### `entsoe-transparency-platform`

European Network of Transmission System Operators for Electricity. (2026). *ENTSO-E Transparency Platform and RESTful API guide*.

- URL: <https://transparency.entsoe.eu/>
- Verification: URL-verified | Access: open-access | evidence tier **A**
- Backs:
  - the A75 generation and A11 physical-flow documents parsed in carbon_sources/entsoe.py and flow_tracing.py
  - the IEC 62325 document structure the XML parsers depend on
- **Caveat:** Platform root fetched on 2026-08-23 and confirmed. The API guide URL used in the code (content/static_content/.../Guide.html) returned an application-level error to an automated client on the same date, so the guide itself was not read here; the document types are evidenced by the live responses the parsers handle.

#### `eskom-data-portal`

Eskom. (2026). *Eskom Data Portal*.

- URL: <https://www.eskom.co.za/dataportal/>
- Verification: URL-verified | Access: open-access | evidence tier **E**
- Backs:
  - South African grid context for the time-of-day model in carbon_sources/eskom.py
- **Caveat:** Portal fetched and confirmed to exist on 2026-08-23. Tier E because the code never reads it: carbon_sources/eskom.py is a fixed time-of-day curve, and no published source states the shape of that curve. The portal is listed here as the data that would be needed to replace the heuristic.

#### `grid-india-reports`

Grid Controller of India. (2026). *Grid Controller of India real-time generation reports*.

- URL: <https://report.grid-india.in/>
- Verification: UNVERIFIED | Access: open-access | evidence tier **C**
- Backs:
  - the Indian regional generation mix parsed in carbon_sources/grid_india.py
- **Caveat:** NOT VERIFIED 2026-08-23: the host did not complete a TLS connection from here. Endpoint identity is taken from the code path only. As with Brazil, the heuristic fallback tagged grid_india_heuristic has no source of its own.

#### `gridstatus-io`

GridStatus. (2026). *GridStatus.io API*.

- URL: <https://www.gridstatus.io/>
- Verification: UNVERIFIED | Access: open-access | evidence tier **C**
- Backs:
  - the US ISO fuel-mix feed parsed in carbon_sources/gridstatus.py
- **Caveat:** NOT VERIFIED 2026-08-23: gridstatus.io returned an HTTP 403 Cloudflare interstitial to every automated request from here. The endpoint identity is taken from the code path only.

#### `ieso-data-directory`

Independent Electricity System Operator. (2026). *IESO Data Directory*.

- URL: <https://www.ieso.ca/en/Power-Data/Data-Directory>
- Verification: URL-verified | Access: open-access | evidence tier **A**
- Backs:
  - the Ontario hourly generator output by fuel type parsed in carbon_sources/canada.py
- **Caveat:** Fetched on 2026-08-23.

#### `neso-carbon-intensity-api`

National Energy System Operator. (2026). *Carbon Intensity API*.

- URL: <https://carbonintensity.org.uk/>
- Verification: URL-verified | Access: open-access | evidence tier **A**
- Backs:
  - the live source behind every UK zone in carbon_sources/uk.py
  - the published per-fuel factor table at /intensity/factors
- **Caveat:** Fetched on 2026-08-23; /intensity/factors returned the live table (Coal 937, Gas CCGT 394, Gas OCGT 651, Oil 935, Other 300, and 0 for hydro, nuclear, solar, wind and pumped storage). Those are direct-combustion values.

#### `ons-brazil-open-data`

Operador Nacional do Sistema Elétrico. (2026). *ONS Brazil operational data*.

- URL: <https://www.ons.org.br/>
- Verification: URL-verified | Access: open-access | evidence tier **A**
- Backs:
  - the Brazilian subsystem generation mix parsed in carbon_sources/ons_brazil.py
- **Caveat:** Site root fetched on 2026-08-23. Note that the module falls back to a fixed per-region estimate when the live fetch fails, and that fallback is tagged ons_brazil_heuristic and has no source.

#### `open-meteo-api`

Open-Meteo. (2026). *Open-Meteo Weather Forecast API*.

- URL: <https://open-meteo.com/en/docs>
- Verification: URL-verified | Access: open-access | evidence tier **E**
- Backs:
  - the irradiance and wind-speed inputs to the weather-based estimate in carbon_sources/open_meteo.py
- **Caveat:** Documentation fetched on 2026-08-23. Tier E deliberately, and the tier judges the CARBON claim alone: Open-Meteo is a good weather source, but nothing published anywhere licenses the mapping from irradiance and wind speed to a grid carbon intensity that this module performs. That mapping is this project's own invention and has no source. See docs/VERIFICATION.md.

#### `openelectricity-api`

OpenElectricity. (2026). *OpenElectricity API (AEMO NEM data)*.

- URL: <https://docs.openelectricity.org.au/introduction>
- Verification: URL-verified | Access: open-access | evidence tier **A**
- Backs:
  - the Australian NEM fuel mix behind the five AEMO zones in carbon_sources/aemo.py
- **Caveat:** Documentation fetched on 2026-08-23.

#### `taipower-generation-data`

Taiwan Power Company. (2026). *Taipower real-time per-unit generation data (genary.json)*.

- URL: <https://www.taipower.com.tw/d006/loadGraph/loadGraph/data/genary.json>
- Verification: URL-verified | Access: open-access | evidence tier **A**
- Backs:
  - the per-unit Taiwanese fuel mix parsed in carbon_sources/taiwan.py
- **Caveat:** Endpoint is the one the code calls; identity confirmed from the code path alone, with no independent re-fetch on 2026-08-23.

#### `watttime-api`

WattTime. (2026). *WattTime Data API documentation*.

- URL: <https://docs.watttime.org/>
- Verification: URL-verified | Access: open-access | evidence tier **B**
- Backs:
  - the measured marginal operating emissions rate (MOER) consumed in carbon_sources/marginal.py
  - that MOER is published in lbs CO2/MWh, which is the basis of the unit conversion there
- **Caveat:** Documentation fetched on 2026-08-23. The API itself returns HTTP 401 without credentials, and this project holds none, which is why the WattTime backtest in docs/VALIDATION.md is reported as NOT RUN rather than estimated.

## Compute energy

3 sources.

#### `aws-pue-2025`

Amazon Web Services. (2026). *AWS Cloud sustainability: power usage effectiveness*.

- URL: <https://sustainability.aboutamazon.com/products-services/aws-cloud>
- Verification: PRIMARY TEXT READ | Access: open-access | evidence tier **D**
- Backs:
  - the AWS PUE constant in models/compliance.py
- **Caveat:** Page read on 2026-08-23. Verbatim: 'In 2025, our data centers reported an average global PUE of 1.14 which is an improvement compared to 1.15 reported in 2024.' The value in this repo was 1.135 labelled 'AWS 2023 sustainability report', which matches no figure AWS currently publishes; corrected to 1.14. Tier D because it is self-reported by the vendor and not independently audited. AWS also publishes PER-REGION PUE, which this project does not yet use.

#### `google-pue-2025`

Google. (2026). *Google data centers: efficiency*.

- URL: <https://www.google.com/about/datacenters/efficiency/>
- Verification: PRIMARY TEXT READ | Access: open-access | evidence tier **D**
- Backs:
  - the GCP PUE constant in models/compliance.py
- **Caveat:** Page read on 2026-08-23. Verbatim: 'In 2025, the average annual power usage effectiveness for our global fleet of data centers was 1.09.' The value in this repo was 1.10 labelled 'Google 2023'; corrected to 1.09. Google reports a trailing-twelve-month fleet-wide figure. Tier D: self-reported.

#### `microsoft-pue-fy25`

Microsoft. (2026). *Measuring energy and water efficiency for Microsoft datacenters*.

- URL: <https://datacenters.microsoft.com/sustainability/efficiency/>
- Verification: PRIMARY TEXT READ | Access: open-access | evidence tier **D**
- Backs:
  - the Azure PUE constant in models/compliance.py
- **Caveat:** Page read on 2026-08-23. Published table: global PUE 1.16 (FY24) and 1.17 (FY25), covering 1 July 2024 to 30 June 2025 for fully owned and operated datacenters. Regional spread in the same table is material and unmodelled here: Americas 1.16, EMEA 1.16, Asia Pacific 1.28. The value in this repo was 1.18 labelled 'Microsoft 2023'; corrected to 1.17. Tier D: self-reported.

## Standards & policy

9 sources.

#### `energytag-gc-standard-v2`

EnergyTag Ltd. (2024). *Granular Certificate Scheme Standard, Version 2*. EnergyTag Ltd

- URL: <https://energytag.org/wp-content/uploads/2024/12/EnergyTag_Granular-Certificate-Scheme-Standard-V2.pdf>
- Verification: URL-verified | Access: open-access | evidence tier **A**
- Backs:
  - the granular-certificate machinery that makes hourly matching auditable
- **Caveat:** Important limit, carried over and re-checked: this standard defines the certificate machinery, and it stops short of arguing that annual matching is weaker than hourly. The README's argument must cite riepin-2024-247-cfe or google-2021-247-cfe for that.

#### `ghg-protocol-corporate-standard`

World Resources Institute; World Business Council for Sustainable Development. (2004). *The Greenhouse Gas Protocol: A Corporate Accounting and Reporting Standard (Revised Edition)*. World Resources Institute

- URL: <https://ghgprotocol.org/sites/default/files/standards/ghg-protocol-revised.pdf>
- Verification: URL-verified | Access: open-access | evidence tier **A**
- Backs:
  - the scope 1/2/3 framework the EmissionScope enum in models/compliance.py encodes
- **Caveat:** PDF fetched on 2026-08-23 and confirmed to be the revised corporate standard. Not read end to end; cited for the scope framework only.

#### `ghg-protocol-scope2-guidance`

World Resources Institute; World Business Council for Sustainable Development. (2015). *GHG Protocol Scope 2 Guidance: An amendment to the GHG Protocol Corporate Standard*. World Resources Institute

- URL: <https://ghgprotocol.org/sites/default/files/2023-03/Scope%202%20Guidance.pdf>
- Verification: PRIMARY TEXT READ | Access: open-access | evidence tier **A**
- Backs:
  - the location-based and market-based methods distinguished by AccountingMethod in compliance/calculator.py
  - the dual-reporting requirement that carbon-lens doesn't currently satisfy
- **Caveat:** PDF downloaded and read on 2026-08-23 (ghgprotocol.org's HTML pages return 403 to automated clients, but the PDF doesn't). Glossary, verbatim: 'Location-based method for scope 2 accounting: A method to quantify scope 2 GHG emissions based on average energy generation emission factors for defined locations, including local, subnational, or national boundaries.' and 'Market-based method for scope 2 accounting: A method to quantify scope 2 GHG emissions based on GHG emissions emitted by the generators from which the reporter contractually purchases electricity bundled with instruments, or unbundled instruments on their own.' Section 1.5.1, verbatim: 'Companies with any operations in markets providing product or supplier-specific data in the form of contractual instruments shall report scope 2 emissions in two ways and label each result according to the method... This is also termed “dual reporting.”'

#### `ghg-protocol-scope3-standard`

World Resources Institute; World Business Council for Sustainable Development. (2011). *Corporate Value Chain (Scope 3) Accounting and Reporting Standard*. World Resources Institute

- URL: <https://ghgprotocol.org/sites/default/files/standards/Corporate-Value-Chain-Accounting-Reporing-Standard_041613_2.pdf>
- Verification: URL-verified | Access: open-access | evidence tier **A**
- Backs:
  - Category 1 (purchased goods and services) as the classification applied to managed cloud services in compliance/calculator.py
- **Caveat:** PDF fetched on 2026-08-23. Not read end to end. Note that carbon-lens's split between Scope 2 and Scope 3 Category 1 rests on a hardcoded list of managed service names, which is this project's own judgement and isn't licensed by the standard.

#### `google-2021-247-cfe`

Google LLC. (2021). *24/7 Carbon-Free Energy: Methodologies and Metrics*. Google LLC

- URL: <https://www.gstatic.com/gumdrop/sustainability/24x7-carbon-free-energy-methodologies-metrics.pdf>
- Verification: URL-verified | Access: open-access | evidence tier **D**
- Backs:
  - the canonical corporate statement of the 24/7 carbon-free energy argument the README makes
- **Caveat:** A corporate white paper with an obvious interest in the conclusion, hence tier D. Cited for the argument's canonical statement, never as evidence for it.

#### `gsf-sci-specification`

Green Software Foundation. (2024). *Software Carbon Intensity (SCI) Specification, version 1.1.0*. Green Software Foundation

- URL: <https://github.com/Green-Software-Foundation/sci/blob/main/SPEC.md>
- Verification: URL-verified | Access: open-access | evidence tier **A**
- Backs:
  - the software carbon intensity framing (operational energy x intensity) the compliance calculator's arithmetic follows
- **Caveat:** The repository's CITATION.cff is stale, still declaring version 1.0.0 and a 2021 release date; SPEC.md front matter on main says 1.1.0. Cite the spec.

#### `iso-iec-21031-2024`

International Organization for Standardization. (2024). *ISO/IEC 21031:2024 Information technology - Software Carbon Intensity (SCI) specification*. ISO/IEC JTC 1 ISO/IEC 21031:2024

- URL: <https://www.iso.org/standard/86612.html>
- Verification: URL-verified | Access: standard-purchase | evidence tier **A**
- Backs:
  - the ISO-standardised form of the SCI specification
- **Caveat:** NOT VERIFIED BY THIS PROJECT 2026-08-23: iso.org returned HTTP 403 (Cloudflare interstitial) to every automated request from here, with and without a browser User-Agent. The catalogue metadata below is inherited from the companion corpus in carbon-aware-dispatcher and was not independently confirmed. The standard text itself is paywalled and has not been read by anyone on this project.

#### `ricks-2023-hourly-matching`

Ricks, Wilson; Xu, Qingyu; Jenkins, Jesse D.. (2023). *Minimizing emissions from grid-based hydrogen production in the United States*. Environmental Research Letters 18: 014025

- DOI: [10.1088/1748-9326/acacb5](https://doi.org/10.1088/1748-9326/acacb5)
- Verification: Crossref-verified | Access: open-access | evidence tier **B**
- Backs:
  - that hourly matching produces materially different emissions outcomes than annual matching
- **Caveat:** DOI re-resolved against the Crossref REST API on 2026-08-23 from this project; title, year, container, volume and pages matched the record below. Note the tension with the marginal-accounting sources in the methodology group: this paper finds hourly matching outperforms marginal accounting. Both positions are in the corpus deliberately.

#### `riepin-2024-247-cfe`

Riepin, Iegor; Brown, Tom. (2024). *On the means, costs, and system-level impacts of 24/7 carbon-free energy procurement*. Energy Strategy Reviews 54: 101488

- DOI: [10.1016/j.esr.2024.101488](https://doi.org/10.1016/j.esr.2024.101488)
- Verification: Crossref-verified | Access: open-access | evidence tier **B**
- Backs:
  - the system-level analysis behind the README's claim that hourly matching is a stronger claim than annual REC matching
- **Caveat:** DOI re-resolved against the Crossref REST API on 2026-08-23 from this project; title, year, container, volume and pages matched the record below.
