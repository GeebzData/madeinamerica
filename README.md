# Made in America: U.S. Manufacturing Map

An interactive map of where American manufacturing went since 1990, and where it's coming back.
Static site (HTML/CSS/vanilla JS + D3) fed by a small Python pipeline that pulls free public data.

## Layout

```
pipeline/
  fetch_qcew.py   BLS QCEW manufacturing jobs, factories, pay (national/state/county, 1990–latest)
  fetch_fred.py   National series from FRED: jobs, output, factory construction, CPI, building-cost PPI
  fetch_census.py Census private construction spending, manufacturing by type
  fetch_qcew_quarter.py  Latest BLS QCEW quarter vs the same quarter a year earlier ("2026 so far")
  fetch_cbp.py    Census County Business Patterns: plants by number of workers (writes site/data/plants.json)
  fetch_metros.py Census metro area definitions (writes site/data/metros.json)
  fetch_bea.py    BEA GDP by state and county, manufacturing (writes site/data/gdp.json)
  fetch_usaspending.py   Federal contracts with manufacturers, by state and Alabama county (writes site/data/contracts.json)
  fetch_alcommerce.py    Alabama Commerce New & Expanding Industry reports, parsed from PDF (writes site/data/announcements.json)
  fetch_industries.py    BLS QCEW by area: every sector and detailed manufacturing industry, U.S. + 7 Southeast states, with location quotients (writes site/data/industries.json)
  fetch_conditions.py    EIA industrial power prices, Census population, BLS union membership, all states (writes site/data/conditions.json)
  fetch_federal.py       USAspending economic-development grants for a fixed program list, 7 Southeast states (writes site/data/federal.json)
  fetch_sba.py           SBA 7(a)/504 loans, totals only by state, year, sector and industry (writes site/data/sba.json)
  fetch_formation.py     Census business applications and Business Dynamics startups/survival (writes site/data/formation.json)
  commerce/              State commerce-agency county data for the Commerce Dept page (writes site/data/commerce_counties.json)
  export.py       Warehouse tables -> compact JSON in site/data/
site/
  index.html                 Explore page
  story.html                 Story page (chapters, 1979 to now)
  reindustrialization.html   Reindustrialization page
  alabama.html               Alabama counties and metro areas, 5- and 10-year trends, incentives
  southeast.html             Alabama, Georgia, Tennessee, South Carolina and Mississippi compared, state → metro → county
  money.html                 Alabama in dollars: GDP, payroll, announced investment, federal contracts
  commerce.html              Commerce Dept: each Southeast commerce agency's own projects, jobs and investment, 2021-2025
  styles.css                 Shared styles
  data/                      Generated JSON
```

## Data source rule

Only official or complete sources go on the site (BLS, Census, Federal Reserve, BEA). Partial or
methodology-shifting trackers (subsidy trackers, announcement trackers) are left out. The one
exception planned is the Clean Investment Monitor (Rhodium/MIT, CC BY 4.0) for clean-tech plants:
its download needs a click-through, so save the quarterly CSV to `pipeline/raw/cim/` by hand.

`pipeline/raw/` and `pipeline/warehouse/` are local caches and are not committed.

## Refresh the data

```bash
python3.12 -m venv .venv
.venv/bin/pip install -r pipeline/requirements.txt
.venv/bin/python pipeline/fetch_fred.py
.venv/bin/python pipeline/fetch_census.py
.venv/bin/python pipeline/fetch_qcew.py   # first run downloads ~2 GB of BLS bulk files for 1990–2013
.venv/bin/python pipeline/export.py
.venv/bin/python pipeline/fetch_qcew_quarter.py
.venv/bin/python pipeline/fetch_cbp.py
.venv/bin/python pipeline/fetch_metros.py
.venv/bin/python pipeline/fetch_bea.py
.venv/bin/python pipeline/fetch_usaspending.py
.venv/bin/python pipeline/fetch_alcommerce.py   # prints how well each year's parsed projects match the report totals
.venv/bin/python pipeline/fetch_industries.py
.venv/bin/python pipeline/fetch_conditions.py
.venv/bin/python pipeline/fetch_federal.py
.venv/bin/python pipeline/fetch_sba.py         # first run downloads ~500 MB of SBA loan files; borrower rows never leave pipeline/raw/
.venv/bin/python pipeline/fetch_formation.py
```

No API keys are needed.

## Publishing

The site is published with GitHub Pages at https://madeinamerica.gerardbarile.com. Every push to `main`
that changes `site/` runs `.github/workflows/pages.yml`, which publishes the `site/` folder. `site/CNAME`
holds the custom domain; DNS is a CNAME record for `madeinamerica` pointing to `geebzdata.github.io`
(Route 53, `gerardbarile.com` zone).

## Run locally

```bash
cd site && python3 -m http.server 8000
```

Then open http://localhost:8000.

## Categories and industry groups

The site sorts manufacturing two ways, both defined in `pipeline/export.py` (`STORIES`, `GROUPS`, `PIECES`;
categories are still called "stories" in the code and data files):

- **Category** (6): Strategic tech & defense, Vehicles, Metals & machinery, Chemicals & materials,
  Food & beverage, Consumer goods.
- **Industry group** (13), each inside exactly one category: e.g. Semiconductors & electronics, Vehicles & EVs, Food & beverage.

Each piece (a 3- or 4-digit NAICS industry) belongs to exactly one group and one category, so every
combination adds up cleanly. Selections use a published 3-digit total wherever they cover a whole
subsector, which keeps suppressed cells to a minimum. `site/categories.js` builds the "What each
category includes" section on each page from `meta.json`, so it always matches these definitions.

## Data notes

- Jobs, establishments (plants and shops with employees) and pay are private-sector annual averages
  from the BLS Quarterly Census of Employment and Wages, coded by NAICS from 1990 on.
- BLS withholds some county and subsector figures to protect individual employers. The site shows them
  as hatched, never as zero.
- Pay is converted to the latest year's dollars with CPI-U.
- Connecticut replaced its 8 counties with 9 planning regions in recent data. The map outlines are the
  older counties, so some Connecticut county figures stop early.

## How changes are measured

- Change = latest year minus start year; percent change divides by the start year. Every change also
  shows growth per year (compound annual growth) and "vs U.S." (percent change minus the nation's, in
  percentage points).
- Counties and metros compare 3-year averages at each end once the span is 6+ years; states use single years.
- Percent maps dot (don't shade) counties with fewer than 500 factory jobs at the start.
- Map color bands come from the data on screen (quantiles of the absolute changes, rounded), so every
  view uses the full range. The legend shows the current bands.
- Shift-share for states: job change = U.S. trend (start jobs x U.S. growth) + industry mix (each
  group's start jobs x its U.S. growth minus total U.S. growth) + local edge (the rest).
- Pay with the industry mix held fixed weights each group's pay by its start-year share of jobs; skipped
  when withheld figures leave out more than 15% of jobs.
- Story chapter 1 adds Fed output excluding high-tech and motor vehicles (IPX4HTMVS), since much of total
  output growth is computers and chips.
- Caveats shown on the site: temp workers are counted in services, establishments are not new plants,
  CPI-U may slightly overstate inflation, announced investment is not money spent, and federal contract
  obligations are commitments for prime contracts only.

## Who's growing (Alabama and Southeast pages)

`site/momentum.js` draws four sections on both pages (the Southeast page adds a state picker):

- **Best-positioned industries**: 10-year job change, BLS location quotient, and local edge (job change beyond the same industry's national rate). Leader = 1.5× concentration or more, adding jobs, and 5+ points faster than the nation; Rising = under 1.5×, up 20%+, and 10+ points faster.
- **Why plants are coming**: power price, factory pay, union rate, population growth and manufacturing concentration, with ranks among the states; Alabama's announced projects by industry.
- **Public vs private money**: federal development grants (program list in `fetch_federal.py`), federal contracts with manufacturers, major incentive packages, announced private investment (Alabama only) and SBA-backed loans, five years against the five before.
- **Small business**: business applications, startups, five-year survival and jobs kept by sector, and SBA lending.

`site/data/incentives.json` is hand-compiled: one entry per major state/local package with a source link. Update it by hand when big deals are announced or change.

## Commerce Dept (commerce.html)

Seven states' recruiting results, each as its own economic development agency published them: projects, committed jobs and promised investment, 2021–2025, scaled by Census population. Alabama is built from `announcements.json`; the other six are hand-compiled in `site/data/commerce.json` with a source link for every state-year.

- Georgia and Mississippi report fiscal years ending June 30; the others are calendar years.
- South Carolina's figures come from S.C. Commerce's Power BI recruitment dashboard (read year by year with the Year filter), which matches its published totals for 2022–2025.
- North Carolina uses Commerce's annual report to the General Assembly on EDPNC.
- Kentucky uses the Cabinet's Location and Expansion Search database (exact, with county), which differs slightly from its rounded year-end releases.
- Rebuild the county file with `python pipeline/commerce/build_commerce_counties.py`. It reads cached inputs in `pipeline/raw/commerce/`: North Carolina's report PDFs (downloaded automatically), and page reads from `pipeline/commerce/sc_dashboard.py` (South Carolina) and `pipeline/commerce/ky_search.py` (Kentucky). Those two drive Google Chrome headlessly through each agency's public page, so they need Chrome and `websocket-client`.
- Maps: a seven-state map (jobs or investment per resident, by year) and a county bubble map of 2021–2025 totals in `site/data/commerce_counties.json` (South Carolina read county by county from the dashboard's County filter, North Carolina from the county tables in Commerce's legislative reports, Kentucky from its search database; Alabama from `announcements.json`). Georgia, Tennessee and Mississippi publish no county totals.
- Rounded figures from releases are flagged `"approx": true` and shown with a ~.
- Each year, add the new year's row per state when the agencies publish (Georgia in August/September, Tennessee in spring, the others in December/January) and move `years` forward.

Waiting on a Census API key: exports by state and industry, and Annual Survey of Manufactures capital spending.

