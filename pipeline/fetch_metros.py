"""Download the Census metro area definitions and write which counties make up each metro area.

Uses the current OMB delineation (July 2023). Metropolitan areas only; micropolitan areas are left
out. Metro areas that cross state lines are listed whole; the site sums only the counties it shows.
"""
import json
import sys
from pathlib import Path

import pandas as pd
import requests

ROOT = Path(__file__).resolve().parent
RAW = ROOT / 'raw' / 'census' / 'list1_2023.xlsx'
OUT = ROOT.parent / 'site' / 'data' / 'metros.json'
URL = 'https://www2.census.gov/programs-surveys/metro-micro/geographies/reference-files/2023/delineation-files/list1_2023.xlsx'
HEADERS = {'User-Agent': 'Mozilla/5.0 ManufacturingMap research (https://madeinamerica.gerardbarile.com)'}


def main():
    r = requests.get(URL, headers=HEADERS, timeout=120)
    r.raise_for_status()
    RAW.parent.mkdir(parents=True, exist_ok=True)
    RAW.write_bytes(r.content)

    d = pd.read_excel(RAW, header=2, dtype=str)
    d = d[d['Metropolitan/Micropolitan Statistical Area'] == 'Metropolitan Statistical Area']
    d = d[d['FIPS County Code'].notna()]
    metros = {}
    for code, rows in d.groupby('CBSA Code'):
        metros[code] = {
            'name': rows['CBSA Title'].iloc[0],
            'counties': sorted(rows['FIPS State Code'] + rows['FIPS County Code']),
        }
    OUT.write_text(json.dumps(metros, separators=(',', ':')))
    print(f'Wrote {len(metros)} metro areas, {sum(len(m["counties"]) for m in metros.values())} counties, to {OUT}')


if __name__ == '__main__':
    sys.exit(main())
