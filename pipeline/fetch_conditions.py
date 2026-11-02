"""Download the state conditions a plant site search weighs, for every state and the U.S.

- Industrial electricity price, cents per kWh (EIA Electric Power Annual, table 2.10)
- Population, 2020 and latest (Census population estimates)
- Union membership, percent of wage and salary workers (BLS union membership release, table 5)
No API keys are needed.

Output: site/data/conditions.json
  {power: {year, prev, states: fips -> [latest, prev]}, pop: {years, states: fips -> [first, last]},
   union: {years, states: fips -> [prev, latest]}}  ('US' is the national figure)
"""
import html
import json
import re
import sys
from pathlib import Path

import pandas as pd
import requests

ROOT = Path(__file__).resolve().parent
RAW = ROOT / 'raw' / 'conditions'
OUT = ROOT.parent / 'site' / 'data' / 'conditions.json'
HEADERS = {'User-Agent': 'ManufacturingMap research (https://madeinamerica.gerardbarile.com)'}
POWER = 'https://www.eia.gov/electricity/annual/xls/epa_02_10.xlsx'
POP = 'https://www2.census.gov/programs-surveys/popest/datasets/2020-2025/state/totals/NST-EST2025-ALLDATA.csv'
UNION = 'https://www.bls.gov/news.release/union2.t05.htm'


def fetch(url):
    path = RAW / url.rsplit('/', 1)[1]
    if not path.exists():
        r = requests.get(url, headers=HEADERS, timeout=120)
        r.raise_for_status()
        RAW.mkdir(parents=True, exist_ok=True)
        path.write_bytes(r.content)
    return path


def main():
    pop = pd.read_csv(fetch(POP), dtype={'STATE': str})
    states = pop[pop.SUMLEV == 40]
    names = dict(zip(states.NAME, states.STATE.str.zfill(2)))
    names['U.S. Total'] = names['United States'] = 'US'

    raw = pd.read_excel(fetch(POWER), header=None)
    head = raw.iloc[3].tolist()
    ind = head.index(next(h for h in head if str(h).startswith('Year')), 5)
    year = int(str(raw.iloc[3, ind]).split()[-1])
    power = {}
    for row in raw.itertuples(index=False):
        fips = names.get(str(row[0]).strip())
        if fips and pd.notna(row[ind]):
            power[fips] = [float(row[ind]), float(row[ind + 1])]

    cols = [c for c in pop.columns if c.startswith('POPESTIMATE')]
    first, last = cols[0], cols[-1]
    people = {'US' if r.SUMLEV == 10 else r.STATE.zfill(2): [int(getattr(r, first)), int(getattr(r, last))]
              for r in pop.itertuples() if r.SUMLEV in (10, 40)}

    page = fetch(UNION).read_text()
    years = [int(y) for y in re.findall(r'(\d{4})-(\d{4}) annual averages', page)[0]]
    union, totals = {}, [[0, 0], [0, 0]]
    for tr in re.findall(r'<tr[^>]*>(.*?)</tr>', page, re.S):
        cells = [html.unescape(re.sub('<[^>]+>', '', c)).strip() for c in re.findall(r'<t[hd][^>]*>(.*?)</t[hd]>', tr, re.S)]
        fips = names.get(re.sub(r'\s*\(.*', '', cells[0])) if cells else None
        if fips and len(cells) >= 11:
            union[fips] = [float(cells[3]), float(cells[8])]
            for t, (emp, mem) in zip(totals, [(cells[1], cells[2]), (cells[6], cells[7])]):
                t[0] += float(emp.replace(',', ''))
                t[1] += float(mem.replace(',', ''))
    # Table 5 has no national row; members over employed across the states and D.C. matches it to rounding.
    union['US'] = [round(100 * mem / emp, 1) for emp, mem in totals]

    out = {'power': {'year': year, 'prev': year - 1, 'states': power},
           'pop': {'years': [int(first[-4:]), int(last[-4:])], 'states': people},
           'union': {'years': years, 'states': union}}
    OUT.write_text(json.dumps(out, separators=(',', ':')))
    print(f'Power {year}: AL {power["01"][0]}c vs US {power["US"][0]}c; '
          f'union {years[1]}: AL {union["01"][1]}% vs US {union.get("US", [0, 0])[1]}%; '
          f'{len(power)} / {len(people)} / {len(union)} areas')


if __name__ == '__main__':
    sys.exit(main())
