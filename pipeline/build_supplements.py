"""Build the small sourced JSON files added after the first audit.

Inputs are public files. Raw downloads stay in pipeline/raw and are not committed.
"""
import csv
import io
import json
import re
import urllib.request
import zipfile
from html import unescape
from pathlib import Path

import openpyxl

ROOT = Path(__file__).resolve().parent
RAW = ROOT / 'raw' / 'supplements'
SITE = ROOT.parent / 'site' / 'data'
HEADERS = {'User-Agent': 'ManufacturingMap research (https://madeinamerica.gerardbarile.com)'}

FIPS = {
    'AL': '01', 'AK': '02', 'AZ': '04', 'AR': '05', 'CA': '06', 'CO': '08', 'CT': '09', 'DE': '10',
    'DC': '11', 'FL': '12', 'GA': '13', 'HI': '15', 'ID': '16', 'IL': '17', 'IN': '18', 'IA': '19',
    'KS': '20', 'KY': '21', 'LA': '22', 'ME': '23', 'MD': '24', 'MA': '25', 'MI': '26', 'MN': '27',
    'MS': '28', 'MO': '29', 'MT': '30', 'NE': '31', 'NV': '32', 'NH': '33', 'NJ': '34', 'NM': '35',
    'NY': '36', 'NC': '37', 'ND': '38', 'OH': '39', 'OK': '40', 'OR': '41', 'PA': '42', 'RI': '44',
    'SC': '45', 'SD': '46', 'TN': '47', 'TX': '48', 'UT': '49', 'VT': '50', 'VA': '51', 'WA': '53',
    'WV': '54', 'WI': '55', 'WY': '56',
}
NAME = {
    'Alabama': '01', 'Alaska': '02', 'Arizona': '04', 'Arkansas': '05', 'California': '06', 'Colorado': '08',
    'Connecticut': '09', 'Delaware': '10', 'District of Columbia': '11', 'Florida': '12', 'Georgia': '13',
    'Hawaii': '15', 'Idaho': '16', 'Illinois': '17', 'Indiana': '18', 'Iowa': '19', 'Kansas': '20',
    'Kentucky': '21', 'Louisiana': '22', 'Maine': '23', 'Maryland': '24', 'Massachusetts': '25',
    'Michigan': '26', 'Minnesota': '27', 'Mississippi': '28', 'Missouri': '29', 'Montana': '30',
    'Nebraska': '31', 'Nevada': '32', 'New Hampshire': '33', 'New Jersey': '34', 'New Mexico': '35',
    'New York': '36', 'North Carolina': '37', 'North Dakota': '38', 'Ohio': '39', 'Oklahoma': '40',
    'Oregon': '41', 'Pennsylvania': '42', 'Rhode Island': '44', 'South Carolina': '45', 'South Dakota': '46',
    'Tennessee': '47', 'Texas': '48', 'Utah': '49', 'Vermont': '50', 'Virginia': '51', 'Washington': '53',
    'West Virginia': '54', 'Wisconsin': '55', 'Wyoming': '56',
}


def fetch(url, dest):
    dest = Path(dest)
    if dest.exists() and dest.stat().st_size > 0:
        return dest
    dest.parent.mkdir(parents=True, exist_ok=True)
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=180) as response:
        dest.write_bytes(response.read())
    return dest


def millions(text):
    match = re.search(r'\$([0-9]+(?:\.[0-9]+)?)\s*(billion|million)', text or '', re.I)
    if not match:
        return None
    value = float(match.group(1))
    return value * 1000 if match.group(2).lower() == 'billion' else value


def chips():
    projects = []
    for page in range(4):
        url = 'https://www.nist.gov/chips/chips-program-office-awards' + (f'?page={page}' if page else '')
        html = fetch(url, RAW / f'nist-{page}.html').read_text(encoding='utf-8', errors='replace')
        for chunk in html.split('<div class="margin-top-3">')[1:]:
            piece = chunk.split('</div></div></div>')[0]
            text = unescape(re.sub(r'<[^>]+>', ' ', piece))
            text = re.sub(r'\s+', ' ', text).strip()
            place = re.search(r'–\s+([^,]+),\s+([A-Z]{2})', text)
            amount = re.search(r'(Proposed Award Amount:|Award Amount:)\s*(.*?)(?:CHIPS Organization|$)', text)
            href = re.search(r'href="(/chips/[^"]+)"', chunk)
            title = re.match(r'(.+?)\s+–', text)
            amount_text = amount.group(2).strip() if amount else ''
            proposed = (amount and amount.group(1).startswith('Proposed')) or 'proposed' in amount_text.lower()
            projects.append({
                'company': title.group(1).strip() if title else text[:80],
                'place': place.group(1).strip() if place else '',
                'state': place.group(2) if place else '',
                'amountText': amount_text,
                'million': millions(amount_text),
                'status': 'proposed' if proposed else 'direct',
                'split': 'split across' in amount_text.lower(),
                'url': 'https://www.nist.gov' + href.group(1) if href else '',
            })
    # One Samsung total is printed on both the Austin and Taylor rows.
    seen = set()
    for project in projects:
        key = (project['company'], project['state'], project['million'], project['status'])
        project['countInStateTotal'] = (
            project['status'] == 'direct' and not project['split'] and project['million'] is not None and key not in seen
        )
        if project['countInStateTotal']:
            seen.add(key)
    states = {}
    for project in projects:
        row = states.setdefault(project['state'], {'directMillion': 0, 'projects': 0})
        row['projects'] += 1
        if project['countInStateTotal']:
            row['directMillion'] = round(row['directMillion'] + project['million'], 1)
    states.setdefault('AL', {'directMillion': 0, 'projects': 0})
    return {
        'source': 'NIST CHIPS Program Office awards list, four pages, updated August 6, 2026.',
        'url': 'https://www.nist.gov/chips/chips-program-office-awards',
        'asOf': '2026-08-06',
        'projects': projects,
        'states': states,
    }


def electricity():
    path = fetch(
        'https://www.eia.gov/electricity/monthly/xls/table_5_06_a.xlsx',
        RAW / 'table_5_06_a.xlsx',
    )
    sheet = openpyxl.load_workbook(path, data_only=True).active
    rows = {}
    for row in sheet.iter_rows(values_only=True):
        name = str(row[0]).replace('\n', ' ').strip() if row[0] else ''
        if name in ('U.S. Total',):
            key = 'US'
        elif name in NAME:
            key = NAME[name]
        else:
            continue
        industrial = row[5]
        year_ago = row[6]
        if not isinstance(industrial, (int, float)):
            continue
        rows[key] = {'cents': industrial, 'centsYearAgo': year_ago if isinstance(year_ago, (int, float)) else None}
    return {
        'source': 'EIA Electric Power Monthly, Table 5.6.A. Average price of electricity to ultimate customers by end-use sector. Industrial column, cents per kilowatthour. Not seasonally adjusted.',
        'url': 'https://www.eia.gov/electricity/monthly/epm_table_grapher.php?t=table_5_06_a',
        'month': '2026-08',
        'compareMonth': '2025-08',
        'states': rows,
    }


def exports():
    path = fetch(
        'https://www.census.gov/trade/downloads/2025/state_exp/naics_om_m/STNAICS2512.ZIP',
        RAW / 'STNAICS2512.ZIP',
    )
    with zipfile.ZipFile(path) as archive:
        raw = archive.read('STNAICSR2512.txt').decode('latin-1')
    totals = {}
    for line in raw.splitlines():
        if len(line) < 136 or not line[0:2] in ('31', '32', '33') or not line[0:4].isdigit():
            continue
        state = line[8:10]
        fips = FIPS.get(state)
        if not fips:
            continue
        totals[fips] = totals.get(fips, 0) + int(line[121:136])
    return {
        'source': 'Census Bureau, State Exports by NAICS, origin of movement, December 2025 year-to-date. Sum of 4-digit NAICS codes beginning with 31, 32, or 33. Origin of movement is the state where the goods started the export journey, which is not always the state that made them.',
        'url': 'https://www.census.gov/foreign-trade/data/STNAICS.html',
        'year': 2025,
        'dollars': totals,
    }


def robotics():
    out = {'year': 2025, 'codes': {}}
    for code, label in (
        ('3332', 'Industrial machinery (NAICS 3332), including semiconductor machinery'),
        ('3339', 'Other general-purpose machinery (NAICS 3339). Census places industrial robot manufacturing in 333999, inside this industry. BLS did not publish a separate 333999 file for 2025.'),
    ):
        path = fetch(f'https://data.bls.gov/cew/data/api/2025/a/industry/{code}.csv', RAW / f'{code}.csv')
        states = {}
        for row in csv.DictReader(path.open()):
            if row['own_code'] != '5':
                continue
            area = row['area_fips']
            if area == 'US000':
                key = 'US'
            elif len(area) == 5 and area.endswith('000'):
                key = area[:2]
            else:
                continue
            withheld = row['disclosure_code'] == 'N'
            states[key] = None if withheld else int(row['annual_avg_emplvl'])
        out['codes'][code] = {'label': label, 'employment': states}
    out['source'] = 'BLS QCEW, 2025 annual average, private ownership, not seasonally adjusted. Statewide rows only.'
    out['url'] = 'https://www.bls.gov/cew/'
    return out


def fred_point(series):
    text = urllib.request.urlopen(urllib.request.Request(
        f'https://fred.stlouisfed.org/graph/fredgraph.csv?id={series}', headers=HEADERS,
    ), timeout=60).read().decode()
    rows = []
    for row in csv.DictReader(io.StringIO(text)):
        keys = list(row)
        raw = row[keys[1]]
        if raw in ('', '.'):
            continue
        rows.append((row[keys[0]][:7], float(raw)))
    return rows


def jobs_baseline():
    sa = fred_point('SMS01000003000000001')
    nsa = fred_point('ALMFGN')
    def pack(rows, series, adjustment):
        latest = rows[-1]
        dec = dict(rows)['2019-12']
        return {
            'series': series,
            'adjustment': adjustment,
            'unit': 'thousands of jobs',
            'dec2019': dec,
            'latest': latest[1],
            'latestMonth': latest[0],
            'pctVsDec2019': (latest[1] - dec) / dec * 100,
        }
    return {
        'qcew': {
            'series': 'BLS QCEW private manufacturing, annual average employment',
            'adjustment': 'not seasonally adjusted',
            'startYear': 2019,
            'endYear': 2025,
            'note': 'The site map uses this series. The percent change is the 2025 annual average divided by the 2019 annual average, not December 2019 and not a seasonally adjusted month.',
        },
        'cesSa': pack(sa, 'SMS01000003000000001', 'seasonally adjusted'),
        'cesNsa': pack(nsa, 'ALMFGN', 'not seasonally adjusted'),
    }


def lfpr_extra(context):
    for fips, series, name in (('12', 'LBSSA12', 'Florida'), ('48', 'LBSSA48', 'Texas')):
        rows = fred_point(series)
        latest = rows[-1]
        avg = [v for d, v in rows if d.startswith('2019')]
        context['lfpr']['states'][fips] = {
            'name': name, 'series': series, 'latest': round(latest[1], 1),
            'asOf': latest[0], 'avg2019': round(sum(avg) / len(avg), 1),
        }


def main():
    SITE.mkdir(parents=True, exist_ok=True)
    context_path = SITE / 'context.json'
    context = json.loads(context_path.read_text())
    lfpr_extra(context)
    context['alMfgJobs'] = jobs_baseline()
    context_path.write_text(json.dumps(context, separators=(',', ':')))
    payload = {
        'electricity': electricity(),
        'exports': exports(),
        'robotics': robotics(),
        'chips': chips(),
    }
    (SITE / 'supplements.json').write_text(json.dumps(payload, separators=(',', ':')))
    print('Wrote supplements and updated context')
    base = context['alMfgJobs']
    print('CES SA pct', round(base['cesSa']['pctVsDec2019'], 2), 'NSA', round(base['cesNsa']['pctVsDec2019'], 2))
    print('chips projects', len(payload['chips']['projects']), 'AL direct', payload['chips']['states'].get('AL'))
    print('AL power', payload['electricity']['states']['01'], 'AL exports', payload['exports']['dollars']['01'])


if __name__ == '__main__':
    main()
