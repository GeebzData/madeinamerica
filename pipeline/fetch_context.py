"""Small sourced series that the pages cite beside the main QCEW warehouse.

Labor-force participation is BLS LAUS via FRED (no API key; the public graph CSV).
Monthly factory jobs are BLS CES MANEMP, same endpoint, so the homepage can plot them
against the inflation-adjusted construction series already in reindustrialization.json.

EV manufacturing ranks are transcribed from Atlas Public Policy / Southern Alliance for
Clean Energy publications. They are announcements, not BLS jobs, and the page says so.
"""
import csv
import io
import json
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent
OUT = ROOT.parent / 'site' / 'data' / 'context.json'
URL = 'https://fred.stlouisfed.org/graph/fredgraph.csv?id={series}'
HEADERS = {'User-Agent': 'ManufacturingMap research (https://madeinamerica.gerardbarile.com)'}

LFPR = {
    'US': ('CIVPART', 'United States'),
    '01': ('LBSSA01', 'Alabama'),
    '13': ('LBSSA13', 'Georgia'),
    '47': ('LBSSA47', 'Tennessee'),
    '45': ('LBSSA45', 'South Carolina'),
    '37': ('LBSSA37', 'North Carolina'),
    '21': ('LBSSA21', 'Kentucky'),
    '28': ('LBSSA28', 'Mississippi'),
}


def fred(series):
    req = urllib.request.Request(URL.format(series=series), headers=HEADERS)
    with urllib.request.urlopen(req, timeout=60) as response:
        text = response.read().decode()
    rows = []
    for row in csv.DictReader(io.StringIO(text)):
        date, value = row['observation_date'] if 'observation_date' in row else row[next(iter(row))], None
        # fredgraph.csv uses DATE / series columns, not observation_date.
        keys = list(row)
        raw = row[keys[1]]
        if raw in ('', '.'):
            continue
        rows.append((row[keys[0]][:7], float(raw)))
    if not rows:
        raise SystemExit(f'no observations for {series}')
    return rows


def annual_average(rows, year):
    vals = [v for d, v in rows if d.startswith(str(year))]
    if len(vals) < 12:
        raise SystemExit(f'{year} has {len(vals)} months')
    return round(sum(vals) / len(vals), 1)


def main():
    lfpr = {}
    latest = None
    for fips, (series, name) in LFPR.items():
        rows = fred(series)
        as_of, value = rows[-1]
        latest = as_of if latest is None else min(latest, as_of)
        lfpr[fips] = {
            'name': name,
            'series': series,
            'latest': round(value, 1),
            'asOf': as_of,
            'avg2019': annual_average(rows, 2019),
        }
        print(f'  {series}: {as_of} {value}')

    jobs = fred('MANEMP')
    jobs = [(d, v) for d, v in jobs if d >= '2015-01']
    # MANEMP is thousands of jobs. Keep one decimal so the chart can show millions.
    out = {
        'lfpr': {
            'source': 'BLS labor force participation, seasonally adjusted, via FRED. States are LAUS series LBSSA plus the state FIPS code. The U.S. rate is CIVPART.',
            'asOf': latest,
            'states': lfpr,
        },
        'jobsMonthly': {
            'source': 'BLS Current Employment Statistics, manufacturing employment (MANEMP), seasonally adjusted, thousands of jobs, via FRED.',
            'dates': [d for d, _ in jobs],
            'thousands': [round(v, 1) for _, v in jobs],
        },
        'ev': {
            'june2025': {
                'source': 'Atlas Public Policy and the Southern Alliance for Clean Energy, Transportation Electrification in the Southeast (2025). Announced EV supply-chain jobs and investment through June 30, 2025, for Alabama, Florida, Georgia, North Carolina, South Carolina and Tennessee.',
                'url': 'https://atlaspolicy.com/transportation-electrification-in-the-southeast-2025/',
                'regionInvestBillion': 78.8,
                'regionJobs': 75400,
                'batteryShareOfInvestment': 0.61,
                'canceledInvestBillion': 3.5,
                'canceledJobs': 2000,
                'newInvestBillionPrior12Months': 4.8,
                'newInvestBillionYearBefore': 15.2,
                'jobsByState': {'01': 2830, '12': 184, '13': 26428, '37': 16253, '45': 13393, '47': 16262},
            },
            'alabamaEoy2025': {
                'source': 'Atlas Public Policy and the Southern Alliance for Clean Energy, Alabama end-of-2025 one-pager. Rank is among that six-state region. Growth is from December 31, 2024 to December 31, 2025.',
                'url': 'https://atlaspolicy.com/wp-content/uploads/2026/03/SACE-One-Pager-Alabama-EOY-2025.pdf',
                'rank': 5,
                'jobs': 2830,
                'investBillion': 3.0,
                'growth': 'none',
                'trainingCenter': 'A $30 million EV training center in Limestone County was expected to open in the first quarter of 2026.',
            },
        },
    }
    OUT.write_text(json.dumps(out, separators=(',', ':')))
    print(f'Wrote {OUT}')


if __name__ == '__main__':
    sys.exit(main())
