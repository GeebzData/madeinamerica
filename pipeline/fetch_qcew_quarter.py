"""Download the latest BLS QCEW quarter for all manufacturing and the same quarter a year earlier.

Annual averages lag about nine months behind the latest quarter, so this gives an early read on
the current year. Factory employment is seasonal, so a quarter is only compared with the same
quarter of the year before. Private sector only, like the annual data.
"""
import io
import json
import sys
from datetime import date
from pathlib import Path

import pandas as pd
import requests

ROOT = Path(__file__).resolve().parent
OUT = ROOT.parent / 'site' / 'data' / 'quarter.json'
URL = 'https://data.bls.gov/cew/data/api/{year}/{qtr}/industry/31_33.csv'
HEADERS = {'User-Agent': 'Mozilla/5.0 ManufacturingMap research (https://madeinamerica.gerardbarile.com)'}
LEVELS = {'14', '54', '74'}


def fetch(year, qtr):
    r = requests.get(URL.format(year=year, qtr=qtr), headers=HEADERS, timeout=120)
    if r.status_code == 404:
        return None
    r.raise_for_status()
    d = pd.read_csv(io.StringIO(r.text), dtype={'area_fips': str, 'own_code': str, 'agglvl_code': str, 'disclosure_code': str})
    d = d[(d['own_code'] == '5') & d['agglvl_code'].isin(LEVELS)]
    rows = {}
    for _, row in d.iterrows():
        fips = row['area_fips']
        key = 'US' if fips == 'US000' else fips[:2] if fips.endswith('000') else fips
        if row['disclosure_code'] == 'N':
            rows[key] = None
            continue
        rows[key] = [round((row['month1_emplvl'] + row['month2_emplvl'] + row['month3_emplvl']) / 3),
                     int(row['qtrly_estabs']), int(row['avg_wkly_wage'])]
    return rows


def main():
    today = date.today()
    latest = None
    for year in (today.year, today.year - 1):
        for qtr in (4, 3, 2, 1):
            latest = fetch(year, qtr)
            if latest:
                break
        if latest:
            break
    prior = fetch(year - 1, qtr)
    areas = {}
    for key, now in latest.items():
        before = prior.get(key)
        if now and before:
            areas[key] = now + before
    out = {'year': year, 'qtr': qtr, 'fields': ['e', 'n', 'w', 'e0', 'n0', 'w0'], 'areas': areas}
    OUT.write_text(json.dumps(out, separators=(',', ':')))
    print(f'Wrote {year} Q{qtr} vs {year - 1} Q{qtr} for {len(areas)} areas to {OUT}')


if __name__ == '__main__':
    sys.exit(main())
