"""Download the Alabama Department of Commerce New & Expanding Industry reports and pull out projects.

Each yearly report lists every announced project by county: new or expanding, company, NAICS code,
jobs and capital investment. These are announcements (commitments), not finished projects. The
county totals printed in each report are kept as published, and the project lines are used to split
out manufacturing (NAICS 31-33). Years whose parsed projects don't match the printed totals within
5% are reported so the parser can be checked.
"""
import json
import re
import sys
from pathlib import Path

import pdfplumber
import requests

ROOT = Path(__file__).resolve().parent
RAW = ROOT / 'raw' / 'alcommerce'
OUT = ROOT.parent / 'site' / 'data' / 'announcements.json'
URL = 'https://www.madeinalabama.com/resources/documents/new-expanding-industry-report-{year}/'
HEADERS = {'User-Agent': 'Mozilla/5.0 ManufacturingMap research (https://madeinamerica.gerardbarile.com)'}
FIRST_YEAR = 2016

COUNTIES = {
    'AUTAUGA': '01001', 'BALDWIN': '01003', 'BARBOUR': '01005', 'BIBB': '01007', 'BLOUNT': '01009', 'BULLOCK': '01011',
    'BUTLER': '01013', 'CALHOUN': '01015', 'CHAMBERS': '01017', 'CHEROKEE': '01019', 'CHILTON': '01021', 'CHOCTAW': '01023',
    'CLARKE': '01025', 'CLAY': '01027', 'CLEBURNE': '01029', 'COFFEE': '01031', 'COLBERT': '01033', 'CONECUH': '01035',
    'COOSA': '01037', 'COVINGTON': '01039', 'CRENSHAW': '01041', 'CULLMAN': '01043', 'DALE': '01045', 'DALLAS': '01047',
    'DEKALB': '01049', 'ELMORE': '01051', 'ESCAMBIA': '01053', 'ETOWAH': '01055', 'FAYETTE': '01057', 'FRANKLIN': '01059',
    'GENEVA': '01061', 'GREENE': '01063', 'HALE': '01065', 'HENRY': '01067', 'HOUSTON': '01069', 'JACKSON': '01071',
    'JEFFERSON': '01073', 'LAMAR': '01075', 'LAUDERDALE': '01077', 'LAWRENCE': '01079', 'LEE': '01081', 'LIMESTONE': '01083',
    'LOWNDES': '01085', 'MACON': '01087', 'MADISON': '01089', 'MARENGO': '01091', 'MARION': '01093', 'MARSHALL': '01095',
    'MOBILE': '01097', 'MONROE': '01099', 'MONTGOMERY': '01101', 'MORGAN': '01103', 'PERRY': '01105', 'PICKENS': '01107',
    'PIKE': '01109', 'RANDOLPH': '01111', 'RUSSELL': '01113', 'ST. CLAIR': '01115', 'SHELBY': '01117', 'SUMTER': '01119',
    'TALLADEGA': '01121', 'TALLAPOOSA': '01123', 'TUSCALOOSA': '01125', 'WALKER': '01127', 'WASHINGTON': '01129',
    'WILCOX': '01131', 'WINSTON': '01133',
}
ALIASES = {'AUTUAGA': 'AUTAUGA', 'ST CLAIR': 'ST. CLAIR', 'SAINT CLAIR': 'ST. CLAIR', 'DE KALB': 'DEKALB'}

TYPE = r'(New|Expansion|Expanding|N|E)'
PROJECT = re.compile(TYPE + r'\s+(.*?)\s(\d{3,6}),?\s+(.*?)\s*(—|-|[\d,]+)?\s*(—|-|\$[\d,]+)?\s*$')
# A project whose NAICS code wrapped onto the line above.
BARE = re.compile(TYPE + r'\s+(.*?)\s+(—|-|[\d,]+)\s+(—|-|\$[\d,]+)\s*$')
LEADING_NAICS = re.compile(r'^(\d{3,6}),?\s')
TOTALS = re.compile(r'^TOTALS? FOR (.+?)\s*\((\d+) PROJECTS?\)\s*(—|[\d,]+)?\s*(—|\$[\d,]+)?\s*$')


def number(text):
    return int(re.sub(r'[^\d]', '', text)) if text and re.search(r'\d', text) else 0


def county_of(name):
    name = name.replace('*', '').replace(' COUNTY', '').strip().upper()
    name = ALIASES.get(name, name)
    return COUNTIES.get(name)


def download(year):
    path = RAW / f'{year}.pdf'
    if not path.exists():
        r = requests.get(URL.format(year=year), headers=HEADERS, timeout=300)
        if r.status_code == 404 or not r.headers.get('content-type', '').startswith('application/pdf'):
            return None
        r.raise_for_status()
        RAW.mkdir(parents=True, exist_ok=True)
        path.write_bytes(r.content)
    return path


def parse(path):
    """Projects and printed county totals from the report's county-by-county section."""
    projects, totals = [], {}
    county = None
    in_counties = False
    with pdfplumber.open(path) as pdf:
        for page in pdf.pages:
            text = page.extract_text() or ''
            # Pages without a section header continue the section before them.
            if any(h in text for h in ('INDUSTRIES IN DEPTH', 'COUNTRIES IN DEPTH', 'COUNTRY SUMMARY', 'INDUSTRY SUMMARY', 'RURAL')):
                in_counties = False
            elif 'COUNTIES IN DEPTH' in text or 'COUNTY SUMMARY' in text:
                in_counties = True
            if not in_counties:
                continue
            pending_naics = None
            for line in text.splitlines():
                line = line.strip()
                header = county_of(line)
                if header and len(line) < 24:
                    county = header
                    continue
                t = TOTALS.match(line)
                if t:
                    # Use the county being read: one report labels a county's totals with the wrong name.
                    fips = county or county_of(t.group(1))
                    if fips:
                        totals[fips] = [int(t.group(2)), number(t.group(3)), number(t.group(4))]
                    continue
                m = PROJECT.match(line)
                if m and county:
                    kind, rest, naics, activity, jobs, invest = m.groups()
                else:
                    b = BARE.match(line)
                    if not (b and county and pending_naics):
                        lead = LEADING_NAICS.match(line)
                        if lead:
                            pending_naics = lead.group(1)
                        continue
                    kind, rest, jobs, invest = b.groups()
                    naics, activity = pending_naics, ''
                    words = rest.split(' ')
                    rest = ' '.join(words[:-1]) if len(words) > 1 else rest
                pending_naics = None
                # The 2016-2019 layout repeats the county name before the company.
                words = rest.split(' ')
                for n in (2, 1):
                    if len(words) > n and county_of(' '.join(words[:n])) == county:
                        rest = ' '.join(words[n:])
                        break
                projects.append({
                    'county': county, 'type': 'new' if kind[0] == 'N' else 'expansion', 'company': rest.strip(),
                    'naics': naics, 'activity': activity.strip(), 'jobs': number(jobs), 'invest': number(invest),
                })
    return projects, totals


def main():
    out = {'years': [], 'counties': {}, 'state': {}, 'projects': []}
    for year in range(FIRST_YEAR, 2100):
        path = download(year)
        if not path:
            if year > FIRST_YEAR + 5:
                break
            continue
        projects, totals = parse(path)
        if not projects:
            print(f'{year}: no projects parsed; layout may have changed')
            continue
        out['years'].append(year)
        # Printed county totals are authoritative; parsed projects fill in counties without a totals line.
        by_county = {}
        for p in projects:
            row = by_county.setdefault(p['county'], [0, 0, 0, 0, 0, 0])
            mfg = p['naics'][:2] in ('31', '32', '33')
            row[0] += 1
            row[1] += p['jobs']
            row[2] += p['invest']
            if mfg:
                row[3] += 1
                row[4] += p['jobs']
                row[5] += p['invest']
            out['projects'].append({'year': year, **p})
        parsed_total = sum(r[2] for r in by_county.values())
        printed_total = sum(t[2] for t in totals.values())
        for fips, row in by_county.items():
            if fips in totals:
                row[:3] = totals[fips]
            out['counties'].setdefault(fips, {})[year] = row
        state = [sum(r[i] for r in by_county.values()) for i in range(6)]
        out['state'][year] = state
        gap = abs(parsed_total - printed_total) / printed_total * 100 if printed_total else 0
        flag = '' if gap < 5 else '  <-- check parser'
        print(f'{year}: {len(projects)} projects, ${state[2] / 1e9:.1f}B announced, ${state[5] / 1e9:.1f}B manufacturing; '
              f'parsed vs printed totals differ {gap:.1f}%{flag}')
    OUT.write_text(json.dumps(out, separators=(',', ':')))
    print(f'Wrote {len(out["years"])} years to {OUT}')


if __name__ == '__main__':
    sys.exit(main())
