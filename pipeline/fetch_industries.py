"""Download BLS QCEW industry detail for the nation and the five Southeast states.

One open-data API file per area and year (no key). Keeps private-sector rows for every
two-digit sector, and for manufacturing every three-, four- and six-digit industry. Pay is
converted to latest-year dollars with CPI-U from the FRED warehouse table. BLS's own location
quotient (the area's share of jobs in an industry divided by the nation's) is kept for the
latest year.

Output: site/data/industries.json
  years, names: code -> title,
  areas: fips -> code -> {e: jobs[], p: pay[], n: establishments[], lq}
Arrays are aligned to years; null = suppressed by BLS.
"""
import io
import json
import sys
from pathlib import Path

import pandas as pd
import requests

ROOT = Path(__file__).resolve().parent
RAW = ROOT / 'raw' / 'area'
OUT = ROOT.parent / 'site' / 'data' / 'industries.json'
HEADERS = {'User-Agent': 'ManufacturingMap research (https://madeinamerica.gerardbarile.com)'}
API = 'https://data.bls.gov/cew/data/api/{year}/a/area/{area}.csv'
TITLES = 'https://data.bls.gov/cew/doc/titles/industry/industry_titles.csv'
AREAS = {'US000': 'US', '01000': '01', '13000': '13', '47000': '47', '45000': '45', '28000': '28'}
FIRST_YEAR = 2015
LAST_YEAR = 2025
# National 14/15/16/18 and state 54/55/56/58 = sector / 3-digit / 4-digit / 6-digit
LEVELS = {'14': 2, '15': 3, '16': 4, '18': 6, '54': 2, '55': 3, '56': 4, '58': 6}


def area_file(year, area):
    path = RAW / str(year) / f'{area}.csv'
    if not path.exists():
        r = requests.get(API.format(year=year, area=area), headers=HEADERS, timeout=120)
        r.raise_for_status()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(r.content)
    df = pd.read_csv(path, dtype=str)
    df = df[(df.own_code == '5') & df.agglvl_code.isin(LEVELS)]
    digits = df.agglvl_code.map(LEVELS)
    mfg = df.industry_code.str[:2].isin(['31', '32', '33']) | (df.industry_code == '31-33')
    return df[(digits == 2) | mfg]


def num(v, scale=1.0):
    return None if pd.isna(v) else int(round(float(v) * scale))


def main():
    years = list(range(FIRST_YEAR, LAST_YEAR + 1))
    fred = pd.read_parquet(ROOT / 'warehouse' / 'fred.parquet')
    cpi = fred[fred.series == 'CPIAUCSL'].set_index('date').value
    cpi = cpi.groupby(cpi.index.year).mean()
    titles = pd.read_csv(io.StringIO(requests.get(TITLES, headers=HEADERS, timeout=60).text), dtype=str)
    titles = dict(zip(titles.industry_code, titles.industry_title.str.replace(r'^NAICS\d* ?', '', regex=True)
                      .str.replace(r'^[\d-]+ ', '', regex=True)))
    out = {'years': years, 'names': {}, 'areas': {a: {} for a in AREAS.values()}}
    for i, year in enumerate(years):
        real = cpi[years[-1]] / cpi[year]
        for area, key in AREAS.items():
            df = area_file(year, area)
            for r in df.itertuples():
                rec = out['areas'][key].setdefault(r.industry_code, {'e': [None] * len(years), 'p': [None] * len(years),
                                                                     'n': [None] * len(years)})
                if r.disclosure_code != 'N':
                    rec['e'][i] = num(r.annual_avg_emplvl)
                    rec['p'][i] = num(r.avg_annual_pay, real)
                    rec['n'][i] = num(r.annual_avg_estabs)
                    if year == years[-1] and key != 'US' and r.lq_disclosure_code != 'N':
                        rec['lq'] = round(float(r.lq_annual_avg_emplvl), 2)
                out['names'].setdefault(r.industry_code, titles.get(r.industry_code, r.industry_code))
        print(f'{year}: {sum(len(v) for v in out["areas"].values())} area-industries')
    for key, recs in out['areas'].items():
        for code in [c for c, rec in recs.items() if not any(rec['e'])]:
            del recs[code]
    OUT.write_text(json.dumps(out, separators=(',', ':')))
    print(f'Wrote {OUT} ({OUT.stat().st_size / 1e3:.0f} KB)')


if __name__ == '__main__':
    sys.exit(main())
