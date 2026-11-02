"""Build site/data/commerce_counties.json: 2021-2025 recruiting totals by county from state agencies.

Inputs, cached in pipeline/raw/commerce/ (gitignored):
- nc/nc_{id}.pdf   N.C. Commerce's yearly reports to the General Assembly on EDPNC (downloaded here).
                   Each has a 100-county table of projects, jobs and investment for its calendar year.
- sc_cty.json      Page text of S.C. Commerce's recruitment dashboard filtered to each county,
                   2021-2025 (written by sc_dashboard.py counties).
- ky_{year}.json   Kentucky Location and Expansion Search results for each year (ky_search.py).
Alabama's counties come from announcements.json in the browser, so they aren't repeated here.

Output: {note, period, states: fips -> {src, counties: county fips -> [projects, jobs, investment $M]}}
"""
import json
import re
import sys
from pathlib import Path

import pdfplumber
import requests

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / 'raw' / 'commerce'
OUT = ROOT.parent / 'site' / 'data' / 'commerce_counties.json'
ATLAS = 'https://cdn.jsdelivr.net/npm/us-atlas@3.0.1/counties-10m.json'
NC_DOCS = {2021: 28411, 2022: 75889, 2023: 84725, 2024: 94639, 2025: 105354}
NC_URL = 'https://webservices.ncleg.gov/ViewDocSiteFile/{}'
YEARS = range(2021, 2026)


def county_names():
    path = RAW / 'counties-10m.json'
    if not path.exists():
        path.write_bytes(requests.get(ATLAS, timeout=120).content)
    names = {}
    for g in json.loads(path.read_text())['objects']['counties']['geometries']:
        names.setdefault(g['id'][:2], {})[g['properties']['name'].lower()] = g['id']
    return names


def add(totals, fips, p, j, inv):
    t = totals.setdefault(fips, [0, 0, 0.0])
    t[0] += p
    t[1] += j
    t[2] += inv


def north_carolina(names):
    num = lambda s: 0 if s.strip() in ('-', '$ -', '') else float(re.sub(r'[^\d.]', '', s))
    lookup = dict(names['37'])
    lookup['hanover'] = lookup['new hanover']  # the 2021 table wraps "New" onto its own line
    pattern = re.compile(r'^(' + '|'.join(re.escape(n.title()) for n in sorted(lookup, key=len, reverse=True))
                         + r') (-|\d+) (-|[\d,]+) \$ ?(-|[\d,]+(?:\.\d+)?)', re.M | re.I)
    totals, sums = {}, {}
    for year, doc in NC_DOCS.items():
        pdf = RAW / 'nc' / f'nc_{doc}.pdf'
        if not pdf.exists():
            pdf.parent.mkdir(parents=True, exist_ok=True)
            pdf.write_bytes(requests.get(NC_URL.format(doc), timeout=120).content)
        with pdfplumber.open(pdf) as f:
            text = '\n'.join(p.extract_text() or '' for p in f.pages)
        # Only the county table: the block of county rows just before the table by tier.
        end = text.find('Announced Jobs and Capital Investment by Tier')
        text = text[text.rfind('\nAlamance', 0, end):end]
        seen = set()
        for m in pattern.finditer(text):
            name = m.group(1).lower()
            if name in seen:
                continue
            seen.add(name)
            p, j, inv = int(num(m.group(2))), int(num(m.group(3))), num(m.group(4)) / 1e6
            if p:
                add(totals, lookup[name], p, j, inv)
            s = sums.setdefault(year, [0, 0])
            s[0] += p
            s[1] += j
    for year, (p, j) in sums.items():
        print(f'NC {year}: {p} projects, {j:,} jobs in the county table')
    return totals


def south_carolina(names):
    num = lambda s: int(re.sub(r'[^\d]', '', s))
    totals, bad = {}, []
    for name, text in json.loads((RAW / 'sc_cty.json').read_text()).items():
        if f'South Carolina • {name} • All Countries' not in text:
            bad.append(name)
            continue
        head = re.search(r'Announcements\n\n(\d+)\n(\d+)\n\nNew\n\n(\d+)\n\nExpansion', text)
        tiers = re.findall(r'(Tier IV|Tier III|Tier II|Tier I)\n([\d,]+)\n\d+%\n\$([\d,]+)', text)
        p = int(head.group(1)) if head else 0
        if p:
            add(totals, names['45'][name.lower()], p, sum(num(t[1]) for t in tiers), sum(num(t[2]) for t in tiers) / 1e6)
    if bad:
        print('SC counties to re-read (filter did not apply):', bad)
    return totals


def kentucky(names):
    totals = {}
    for year in YEARS:
        rows = json.loads((RAW / f'ky_{year}.json').read_text())['rows']
        for r in rows:
            if len(r) < 8 or not r[0] or r[0] == 'All':
                continue
            inv = float(re.sub(r'[^\d.]', '', r[6]) or 0) / 1e6
            add(totals, names['21'][r[0].lower()], 1, int(re.sub(r'[^\d]', '', r[7]) or 0), inv)
    return totals


def main():
    names = county_names()
    states = {
        '45': ('https://www.sccommerce.com/state-economy/project-recruitment-data', south_carolina(names)),
        '37': (NC_URL.format(NC_DOCS[2025]), north_carolina(names)),
        '21': ('https://locationexpansionsearch.ced.ky.gov/', kentucky(names)),
    }
    out = {
        'note': ("County figures are 2021 to 2025 totals as each agency publishes them: Alabama from the Department of "
                 "Commerce New & Expanding Industry reports; South Carolina from S.C. Commerce's recruitment dashboard, "
                 "filtered county by county; North Carolina from the county tables in Commerce's yearly reports to the "
                 "General Assembly; Kentucky from the Cabinet's Location and Expansion Search database. North Carolina's "
                 "2025 county table adds to 2,405 fewer jobs than its statewide total, and South Carolina's dashboard "
                 "leaves 14 of its 485 projects (693 jobs) without a county, so county bubbles add up to slightly less "
                 "than the state figures. Georgia, Tennessee and Mississippi publish statewide totals and individual "
                 "announcements but no county totals."),
        'period': [YEARS[0], YEARS[-1]],
        'states': {f: {'src': src, 'counties': {c: [t[0], t[1], round(t[2], 2)] for c, t in sorted(rows.items())}}
                   for f, (src, rows) in states.items()},
    }
    for f, (_, rows) in states.items():
        print(f'{f}: {len(rows)} counties, {sum(t[0] for t in rows.values())} projects, '
              f'{sum(t[1] for t in rows.values()):,} jobs, ${sum(t[2] for t in rows.values()) / 1000:.1f}B')
    OUT.write_text(json.dumps(out, separators=(',', ':')))
    print(f'Wrote {OUT}')


if __name__ == '__main__':
    sys.exit(main())
