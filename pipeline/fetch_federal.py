"""Download federal grants for economic development in the Southeast from USAspending.gov (no key).

Only programs aimed at businesses, factories, workers or regional development are counted,
from a fixed list of assistance listing numbers (below) in five groups. Broadband, research,
safety-net and highway money is left out. Amounts are grant obligations (award types 02-05)
by where the work is done, per federal fiscal year, in each year's dollars.

Output: site/data/federal.json
  fys, groups: id -> {name, programs: {number: title}},
  states: fips -> id -> $M per fy,
  top: fips -> [[number, title, $M], ...] largest programs over the last five fiscal years
"""
import json
import sys
from datetime import date
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent
OUT = ROOT.parent / 'site' / 'data' / 'federal.json'
GEO = 'https://api.usaspending.gov/api/v2/search/spending_by_geography/'
CFDA = 'https://api.usaspending.gov/api/v2/search/spending_by_category/cfda/'
FIRST_FY = 2015
STATES = {'AL': '01', 'GA': '13', 'TN': '47', 'SC': '45', 'MS': '28'}
GROUPS = {
    'mfg': ('Manufacturing & supply chain', {
        '81.253': 'DOE manufacturing and energy supply chain (battery and materials plants)',
        '81.255': 'DOE clean energy demonstrations',
        '11.611': 'Manufacturing Extension Partnership',
        '11.039': 'Regional Technology and Innovation Hubs',
        '47.084': 'NSF Technology, Innovation and Partnerships (Regional Innovation Engines)'}),
    'devel': ('Economic development', {
        '11.300': 'EDA public works and development facilities',
        '11.307': 'EDA economic adjustment assistance',
        '11.302': 'EDA planning organizations',
        '11.040': 'EDA distressed area Recompete',
        '23.002': 'Appalachian Regional Commission development',
        '90.200': 'Delta Regional Authority',
        '90.201': 'Delta Regional Authority economic development',
        '12.610': 'Defense community economic adjustment',
        '12.617': 'Defense economic adjustment assistance',
        '10.351': 'USDA rural business development',
        '10.352': 'USDA value-added producer grants',
        '10.868': 'USDA Rural Energy for America (REAP)'}),
    'work': ('Workforce training', {
        '17.258': 'WIOA adult training',
        '17.259': 'WIOA youth',
        '17.278': 'WIOA dislocated workers',
        '17.277': 'National dislocated worker grants',
        '17.280': 'Dislocated worker demonstration grants',
        '17.285': 'Registered apprenticeship',
        '17.268': 'H-1B skills training grants',
        '17.245': 'Trade adjustment assistance'}),
    'small': ('Small business support', {
        '59.037': 'Small Business Development Centers',
        '59.046': 'SBA microloan program grants'}),
    'energy': ('Energy & grid', {
        '81.254': 'Grid infrastructure deployment and resilience',
        '81.041': 'State Energy Program'}),
}


def post(url, body):
    r = requests.post(url, json=body, timeout=180)
    r.raise_for_status()
    return r.json()


def main():
    # Grant reporting trails by months, so a fiscal year counts once the January after it ends.
    last = date.today().year - 1
    fys = list(range(FIRST_FY, last + 1))
    out = {'fys': fys, 'groups': {k: {'name': n, 'programs': p} for k, (n, p) in GROUPS.items()},
           'states': {f: {k: [] for k in GROUPS} for f in STATES.values()}, 'top': {}}
    for fy in fys:
        period = [{'start_date': f'{fy - 1}-10-01', 'end_date': f'{fy}-09-30'}]
        for key, (_, programs) in GROUPS.items():
            rows = post(GEO, {'scope': 'place_of_performance', 'geo_layer': 'state', 'geo_layer_filters': list(STATES),
                              'filters': {'time_period': period, 'award_type_codes': ['02', '03', '04', '05'],
                                          'program_numbers': list(programs)}})['results']
            amounts = {r['shape_code']: r['aggregated_amount'] for r in rows}
            for abbr, fips in STATES.items():
                out['states'][fips][key].append(round(amounts.get(abbr, 0) / 1e6, 1))
        print(f'FY{fy}: Alabama ${sum(v[-1] for v in out["states"]["01"].values()):,.0f}M')
    titles = {n: t for _, p in GROUPS.values() for n, t in p.items()}
    period = [{'start_date': f'{fys[-5] - 1}-10-01', 'end_date': f'{fys[-1]}-09-30'}]
    for abbr, fips in STATES.items():
        rows = post(CFDA, {'limit': 15, 'filters': {
            'time_period': period, 'award_type_codes': ['02', '03', '04', '05'],
            'program_numbers': list(titles), 'place_of_performance_locations': [{'country': 'USA', 'state': abbr}]}})
        out['top'][fips] = [[r['code'], titles.get(r['code'], r['name']), round(r['amount'] / 1e6, 1)]
                            for r in rows['results'] if r['amount'] and r['amount'] > 0]
    OUT.write_text(json.dumps(out, separators=(',', ':')))
    print(f'Wrote FY{fys[0]}-FY{fys[-1]} to {OUT}')


if __name__ == '__main__':
    sys.exit(main())
