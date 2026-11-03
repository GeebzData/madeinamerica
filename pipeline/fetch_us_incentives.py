"""Build site/data/us_incentives.json: federal incentives committed to new U.S. factories, by month.

Three parts, each summed into a running total from the first commitment:
- CHIPS Act manufacturing incentives: final direct-funding awards from the NIST CHIPS Program Office
  awards list, dated by their final-award announcement (NIST releases, or Manufacturing Dive's
  CHIPS tracker for awards made before NIST's current news archive starts in 2025). Hand-compiled
  below, because the awards are not reported to USAspending. R&D awards are left out.
- DOE Office of Manufacturing and Energy Supply Chains grants (assistance listing 81.253, mostly
  battery and battery-materials plants): obligations by month from USAspending (no key).
- Section 48C advanced energy manufacturing tax credits: the two allocation rounds announced by
  Treasury and the IRS.
Left out because no dated public total exists: the 45X production tax credit, which manufacturers
claim on their tax returns, DOE loans, and state and local packages.
"""
import json
import sys
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent
OUT = ROOT.parent / 'site' / 'data' / 'us_incentives.json'
SPENDING = 'https://api.usaspending.gov/api/v2/search/spending_over_time/'
TRACKER = 'https://www.manufacturingdive.com/news/chips-and-science-act-tracker-semiconductor-manufacturing/734039/'
NIST = 'https://www.nist.gov/chips/chips-program-office-awards'
FIRST = '2022-08'

# Company, $ millions, month of the final award.
CHIPS = [
    ('Polar Semiconductor', 123, '2024-09'),
    ('TSMC Arizona', 6600, '2024-11'),
    ('GlobalFoundries', 1500, '2024-11'),
    ('BAE Systems', 35.5, '2024-11'),
    ('Rocket Lab', 23.9, '2024-11'),
    ('Intel', 7865, '2024-11'),
    ('Absolics', 75, '2024-12'),
    ('Entegris', 77, '2024-12'),
    ('Micron (Idaho and New York)', 6165, '2024-12'),
    ('GlobalWafers', 406, '2024-12'),
    ('SK hynix', 458, '2024-12'),
    ('Samsung', 4745, '2024-12'),
    ('Texas Instruments', 1600, '2024-12'),
    ('Amkor', 407, '2024-12'),
    ('Hemlock Semiconductor', 325, '2025-01'),
    ('HP', 53, '2025-01'),
    ('Corning', 32, '2025-01'),
    ('Edwards Vacuum', 18, '2025-01'),
    ('Infinera', 93, '2025-01'),
    ('Micron (Virginia)', 275, '2025-06'),
    ('Crucible Metals', 210, '2025-12'),
    ('USA Rare Earth', 277, '2026-06'),
    ('Powerex', 3, '2026-06'),
    ('Bosch', 225, '2026-07'),
]
C48 = [
    ('Round 1', 4000, '2024-03', 'https://www.irs.gov/newsroom/irs-and-treasury-provide-guidance-on-the-qualifying-advanced-energy-project-credit'),
    ('Round 2', 6000, '2025-01', 'https://fraser.stlouisfed.org/title/press-releases-united-states-department-treasury-6111/us-department-treasury-irs-announce-6-billion-tax-credit-allocations-second-round-48c-qualifying-advanced-energy-project-tax-credit-680427'),
]


def doe_by_month(last):
    body = {'group': 'month', 'filters': {'program_numbers': ['81.253'],
            'time_period': [{'start_date': '2022-10-01', 'end_date': f'{last}-28'}]}}
    r = requests.post(SPENDING, json=body, timeout=120)
    r.raise_for_status()
    out = {}
    for row in r.json()['results']:
        fy, m = int(row['time_period']['fiscal_year']), int(row['time_period']['month'])
        # USAspending months are fiscal: month 1 is October of the year before.
        year, month = (fy - 1, m + 9) if m <= 3 else (fy, m - 3)
        out[f'{year}-{month:02d}'] = out.get(f'{year}-{month:02d}', 0) + row['aggregated_amount'] / 1e6
    return out


def months(first, last):
    y, m = map(int, first.split('-'))
    out = []
    while f'{y}-{m:02d}' <= last:
        out.append(f'{y}-{m:02d}')
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)
    return out


def main():
    reind = json.loads((OUT.parent / 'reindustrialization.json').read_text())
    last = reind['latest']
    doe = doe_by_month(last)
    span = months(FIRST, last)
    series = {'chips': [], 'doe': [], 'c48': []}
    run = {'chips': 0, 'doe': 0, 'c48': 0}
    for month in span:
        run['chips'] += sum(a for _, a, m in CHIPS if m == month)
        run['doe'] += doe.get(month, 0)
        run['c48'] += sum(a for _, a, m, _ in C48 if m == month)
        for k in series:
            series[k].append(round(run[k] / 1e3, 2))
    out = {
        'months': span,
        **series,
        'total': [round(a + b + c, 2) for a, b, c in zip(series['chips'], series['doe'], series['c48'])],
        'chipsAwards': [{'company': c, 'million': a, 'month': m} for c, a, m in CHIPS],
        'c48Rounds': [{'round': r, 'million': a, 'month': m, 'url': u} for r, a, m, u in C48],
        'urls': {'chips': NIST, 'tracker': TRACKER, 'doe': 'https://www.usaspending.gov/search', 'c48': C48[0][3]},
    }
    OUT.write_text(json.dumps(out, separators=(',', ':')))
    print(f"Through {last}: CHIPS ${series['chips'][-1]}B, DOE ${series['doe'][-1]}B, 48C ${series['c48'][-1]}B, total ${out['total'][-1]}B")
    print(f'Wrote {OUT}')


if __name__ == '__main__':
    sys.exit(main())
