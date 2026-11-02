"""Download Census business formation data for the nation and the Southeast states (no key).

- Business Formation Statistics: new business applications (EIN filings) by state and month.
  'Likely employers' are the applications Census flags as high-propensity (likely to hire).
- Business Dynamics Statistics, by state x sector x firm age: startups (age-0 firms), the jobs
  they start with, and how a startup class fared five years on (age-5 firms in the later year).
  BDS tracks firms, not individual startups, so survival is the standard cohort approximation.

Output: site/data/formation.json
  bfs: {years, ytd: {year, months}, areas: key -> {apps[], likely[], ytd: [latest, year before]}}
  bds: {years, cohort: [start, end], sectors: code -> name,
        areas: key -> sector -> {s: startups[], j: startup jobs[], f: all firms[], c: [startups, survivors, jobs, survivor jobs]}}
  'all' is the sum over sectors. Arrays aligned to years; null = withheld by Census.
"""
import json
import sys
from pathlib import Path

import pandas as pd
import requests

ROOT = Path(__file__).resolve().parent
RAW = ROOT / 'raw' / 'formation'
OUT = ROOT.parent / 'site' / 'data' / 'formation.json'
BFS = 'https://www.census.gov/econ/bfs/csv/bfs_monthly.csv'
BDS = 'https://www2.census.gov/programs-surveys/bds/tables/time-series/{v}/bds{v}_{t}.csv'
BDS_VINTAGE = 2023
STATES = {'AL': '01', 'GA': '13', 'TN': '47', 'SC': '45', 'MS': '28'}
SECTORS = {'11': 'Farming, forestry & fishing', '21': 'Mining, oil & gas', '22': 'Utilities',
           '23': 'Construction', '31-33': 'Manufacturing', '42': 'Wholesale trade', '44-45': 'Retail',
           '48-49': 'Transportation & warehousing', '51': 'Information', '52': 'Finance & insurance',
           '53': 'Real estate & rentals', '54': 'Professional & technical services',
           '55': 'Company management', '56': 'Business support & cleaning', '61': 'Education',
           '62': 'Health care', '71': 'Arts & recreation', '72': 'Hotels & restaurants',
           '81': 'Repair & personal services'}
FIRST_YEAR = 2005
MONTHS = ['jan', 'feb', 'mar', 'apr', 'may', 'jun', 'jul', 'aug', 'sep', 'oct', 'nov', 'dec']


def fetch(url):
    path = RAW / url.rsplit('/', 1)[1]
    if not path.exists():
        RAW.mkdir(parents=True, exist_ok=True)
        with requests.get(url, stream=True, timeout=600) as r:
            r.raise_for_status()
            with open(path, 'wb') as f:
                for chunk in r.iter_content(1 << 20):
                    f.write(chunk)
    return path


def bfs():
    df = pd.read_csv(fetch(BFS), dtype=str)
    df = df[(df.sa == 'U') & (df.naics_sector == 'TOTAL') & df.series.isin(['BA_BA', 'BA_HBA'])]
    df[MONTHS] = df[MONTHS].apply(pd.to_numeric, errors='coerce')
    df['year'] = df.year.astype(int)
    last = df.year.max()
    months = int(df[df.year == last][MONTHS].notna().all().sum())
    years = list(range(FIRST_YEAR, last))
    out = {'years': years, 'ytd': {'year': int(last), 'months': months}, 'areas': {}}
    for key, geo in [('US', 'US')] + [(f, a) for a, f in STATES.items()]:
        d = df[df.geo == geo].set_index(['series', 'year'])
        total = d[MONTHS].sum(axis=1, min_count=12)
        ytd = d[MONTHS[:months]].sum(axis=1)
        out['areas'][key] = {
            'apps': [int(total.get(('BA_BA', y))) for y in years],
            'likely': [int(total.get(('BA_HBA', y))) for y in years],
            'ytd': [int(ytd[('BA_BA', last)]), int(ytd[('BA_BA', last - 1)])],
            'ytdLikely': [int(ytd[('BA_HBA', last)]), int(ytd[('BA_HBA', last - 1)])],
        }
    return out


def bds():
    cols = ['year', 'sector', 'fage', 'firms', 'emp']
    nat = pd.read_csv(fetch(BDS.format(v=BDS_VINTAGE, t='sec_fa')), usecols=cols, dtype=str).assign(st='US')
    st = pd.read_csv(fetch(BDS.format(v=BDS_VINTAGE, t='st_sec_fa')), usecols=cols + ['st'], dtype=str)
    df = pd.concat([nat, st[st.st.isin(STATES.values())]])
    df['year'] = df.year.astype(int)
    df = df[df.year >= FIRST_YEAR]
    for c in ['firms', 'emp']:
        df[c] = pd.to_numeric(df[c], errors='coerce')
    years = list(range(FIRST_YEAR, BDS_VINTAGE + 1))
    cohort = [BDS_VINTAGE - 5, BDS_VINTAGE]
    out = {'years': years, 'cohort': cohort, 'sectors': SECTORS, 'areas': {}}
    for key, d in df.groupby('st'):
        rec = {}
        young = d[d.fage == 'a) 0']
        aged = d[d.fage == 'f) 5']
        firms = d.groupby(['sector', 'year']).firms.sum(min_count=1)
        for sec in list(SECTORS) + ['all']:
            pick = (lambda x: x) if sec == 'all' else (lambda x, s=sec: x[x.sector == s])
            y0 = pick(young).groupby('year')[['firms', 'emp']].sum(min_count=1)
            y5 = pick(aged).groupby('year')[['firms', 'emp']].sum(min_count=1)
            f = firms.groupby('year').sum(min_count=1) if sec == 'all' else firms.get(sec, pd.Series(dtype=float))

            def arr(s):
                return [None if pd.isna(s.get(y)) else int(s.get(y)) for y in years]
            c = [y0.firms.get(cohort[0]), y5.firms.get(cohort[1]), y0.emp.get(cohort[0]), y5.emp.get(cohort[1])]
            rec[sec] = {'s': arr(y0.firms), 'j': arr(y0.emp), 'f': arr(f),
                        'c': [None if pd.isna(v) else int(v) for v in c]}
        out['areas'][key] = rec
    return out


def main():
    out = {'bfs': bfs(), 'bds': bds()}
    b, s = out['bfs'], out['bds']
    al = b['areas']['01']
    print(f'BFS {b["years"][-1]}: AL {al["apps"][-1]:,} applications, {al["likely"][-1]:,} likely employers; '
          f'{b["ytd"]["year"]} through month {b["ytd"]["months"]}: {al["ytd"][0]:,} vs {al["ytd"][1]:,}')
    c = s['areas']['01']['all']['c']
    print(f'BDS: AL startups {s["years"][-1]} {s["areas"]["01"]["all"]["s"][-1]:,}; '
          f'{s["cohort"][0]} class {c[0]:,} -> {c[1]:,} firms, {c[2]:,} -> {c[3]:,} jobs')
    OUT.write_text(json.dumps(out, separators=(',', ':')))
    print(f'Wrote {OUT} ({OUT.stat().st_size / 1e3:.0f} KB)')


if __name__ == '__main__':
    sys.exit(main())
