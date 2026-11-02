"""Download federal contract spending with manufacturers from USAspending.gov.

Contracts (award types A-D) whose NAICS code is manufacturing (31-33), by where the work is done,
for each federal fiscal year (October to September). Amounts are obligations in each year's dollars.
Only complete fiscal years are kept. No API key is needed.
"""
import json
import sys
from datetime import date
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent
OUT = ROOT.parent / 'site' / 'data' / 'contracts.json'
URL = 'https://api.usaspending.gov/api/v2/search/spending_by_geography/'
FIRST_FY = 2008
STATES = {'AL': '01', 'GA': '13', 'TN': '47', 'SC': '45', 'MS': '28', 'NC': '37', 'KY': '21'}


def query(fy, geo_layer, extra):
    body = {
        'scope': 'place_of_performance', 'geo_layer': geo_layer,
        'filters': {
            'time_period': [{'start_date': f'{fy - 1}-10-01', 'end_date': f'{fy}-09-30'}],
            'award_type_codes': ['A', 'B', 'C', 'D'],
            'naics_codes': {'require': ['31', '32', '33']},
            **extra.get('filters', {}),
        },
        **{k: v for k, v in extra.items() if k != 'filters'},
    }
    r = requests.post(URL, json=body, timeout=120)
    r.raise_for_status()
    return r.json()['results']


def main():
    today = date.today()
    # A fiscal year is complete once September is over; allow a month for reporting.
    last = today.year if today.month >= 11 else today.year - 1
    fys = list(range(FIRST_FY, last + 1))
    out = {'fys': fys, 'states': {f: [] for f in STATES.values()}, 'counties': {}}
    for i, fy in enumerate(fys):
        rows = {r['shape_code']: r['aggregated_amount'] for r in query(fy, 'state', {'geo_layer_filters': list(STATES)})}
        for abbr, fips in STATES.items():
            out['states'][fips].append(round(rows.get(abbr, 0) / 1e6, 1))
        for r in query(fy, 'county', {'filters': {'place_of_performance_locations': [{'country': 'USA', 'state': 'AL'}]}}):
            if r['shape_code'] and r['shape_code'].startswith('01'):
                out['counties'].setdefault(r['shape_code'], [0] * len(fys))[i] = round(r['aggregated_amount'] / 1e6, 2)
        print(f'FY{fy}: Alabama ${out["states"]["01"][-1] / 1e3:.2f}B')
    OUT.write_text(json.dumps(out, separators=(',', ':')))
    print(f'Wrote FY{fys[0]}-FY{fys[-1]} to {OUT}')


if __name__ == '__main__':
    sys.exit(main())
