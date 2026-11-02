"""Download SBA 7(a) and 504 loan approvals and total them for the nation and the Southeast states.

SBA's public FOIA files list every approved loan since FY2010 (no key). Only totals leave this
script; the borrower-level rows stay in raw/ and are never published. Loans are placed by the
state of the project (where the business operates), by federal fiscal year of approval.
Canceled loans (approved but never made) are dropped.

Output: site/data/sba.json
  fys, recent: [first, last] fiscal years of the recent window, prior: the window before it,
  sectors: code -> name, names: four-digit code -> name,
  areas: key -> {
    fy: {n, amt, jobs, young, mfg_n, mfg_amt} arrays aligned to fys (amt in $M),
    sec: sector -> [loans, $M, jobs, young loans] over the recent window,
    secPrior: sector -> loans over the prior window,
    loss: sector -> [loans approved FY2010-FY2019, charged off],
    top: [[four-digit code, recent loans, prior loans, recent $M], ...] most-financed industries
  }
'young' = startups plus businesses two years old or less.
"""
import json
import re
import sys
from pathlib import Path

import pandas as pd
import requests

ROOT = Path(__file__).resolve().parent
RAW = ROOT / 'raw' / 'sba'
OUT = ROOT.parent / 'site' / 'data' / 'sba.json'
BASE = 'https://data.sba.gov/sites/default/files/uploaded_resources/'
PAGE = 'https://data.sba.gov/dataset/7a-504-foia'
WANT = ['FOIA_7a_FY2010_FY2019', 'FOIA_7a_FY2020_Present', 'FOIA_504_FY2010_Present']
STATES = {'AL': '01', 'GA': '13', 'TN': '47', 'SC': '45', 'MS': '28'}
COLS = ['ProjectState', 'ApprovalFY', 'NaicsCode', 'NaicsDescription', 'GrossApproval', 'JobsSupported',
        'BusinessAge', 'LoanStatus']
SECTORS = {'11': 'Farming, forestry & fishing', '21': 'Mining, oil & gas', '22': 'Utilities',
           '23': 'Construction', '31': 'Manufacturing', '42': 'Wholesale trade', '44': 'Retail',
           '48': 'Transportation & warehousing', '51': 'Information', '52': 'Finance & insurance',
           '53': 'Real estate & rentals', '54': 'Professional & technical services',
           '55': 'Company management', '56': 'Business support & cleaning', '61': 'Education',
           '62': 'Health care', '71': 'Arts & recreation', '72': 'Hotels & restaurants',
           '81': 'Repair & personal services', '92': 'Public administration'}
MERGE = {'32': '31', '33': '31', '45': '44', '49': '48'}
LOSS_FYS = (2010, 2019)


def files():
    """The file names carry an as-of date that changes each quarter, so read them off the dataset page."""
    page = requests.get(PAGE, headers={'User-Agent': 'Mozilla/5.0'}, timeout=60).text
    for stem in WANT:
        name = sorted(set(n for n in re.findall(rf'{stem}_asof_\d+\.csv', page)))[-1]
        path = RAW / name
        if not path.exists():
            for old in RAW.glob(f'{stem}_asof_*.csv'):
                old.unlink()
            print(f'Downloading {name}')
            with requests.get(BASE + name, headers={'User-Agent': 'Mozilla/5.0'}, stream=True, timeout=900) as r:
                r.raise_for_status()
                RAW.mkdir(parents=True, exist_ok=True)
                with open(path, 'wb') as f:
                    for chunk in r.iter_content(1 << 20):
                        f.write(chunk)
        yield path


def main():
    df = pd.concat([pd.read_csv(p, usecols=COLS, dtype=str) for p in files()], ignore_index=True)
    df = df[df.LoanStatus != 'CANCLD'].copy()
    df['fy'] = pd.to_numeric(df.ApprovalFY, errors='coerce')
    df['amt'] = pd.to_numeric(df.GrossApproval, errors='coerce').fillna(0) / 1e6
    df['jobs'] = pd.to_numeric(df.JobsSupported, errors='coerce').fillna(0)
    df['young'] = df.BusinessAge.fillna('').str.startswith(('Startup', 'New Business'))
    df['naics'] = df.NaicsCode.fillna('').str[:6]
    two = df.naics.str[:2]
    df['sec'] = two.map(lambda s: MERGE.get(s, s)).where(two.isin(list(SECTORS) + list(MERGE)), 'other')
    df['ind'] = df.naics.str[:4]
    df['area'] = df.ProjectState.str.strip().map(STATES)
    df = df[df.fy >= 2010]

    fys = list(range(2010, int(df.fy.max()) + 1))
    recent = [fys[-1] - 5, fys[-1]]
    prior = [recent[0] - 6, recent[0] - 1]
    names = (df[df.ind.str.len() == 4].groupby('ind').NaicsDescription.agg(lambda s: s.mode().iat[0]).to_dict())
    out = {'fys': fys, 'recent': recent, 'prior': prior, 'sectors': SECTORS, 'names': {}, 'areas': {}}

    for key in ['US'] + list(STATES.values()):
        d = df if key == 'US' else df[df.area == key]
        g = d.groupby('fy')
        m = d[d.sec == '31'].groupby('fy')
        fy = {'n': g.size(), 'amt': g.amt.sum(), 'jobs': g.jobs.sum(), 'young': g.young.sum(),
              'mfg_n': m.size(), 'mfg_amt': m.amt.sum()}
        fy = {k: [round(float(v.get(y, 0)), 1 if k.endswith('amt') else None) for y in fys] for k, v in fy.items()}
        fy = {k: [int(x) if not k.endswith('amt') else x for x in v] for k, v in fy.items()}

        win = d[d.fy.between(*recent)]
        sec = win.groupby('sec').agg(n=('amt', 'size'), amt=('amt', 'sum'), jobs=('jobs', 'sum'), young=('young', 'sum'))
        before = d[d.fy.between(*prior)].groupby('sec').size()
        old = d[d.fy.between(*LOSS_FYS)]
        loss = old.groupby('sec').agg(n=('amt', 'size'), bad=('LoanStatus', lambda s: (s == 'CHGOFF').sum()))

        ind_now = win[win.ind.str.len() == 4].groupby('ind').agg(n=('amt', 'size'), amt=('amt', 'sum'))
        ind_then = d[d.fy.between(*prior) & (d.ind.str.len() == 4)].groupby('ind').size()
        top = ind_now.sort_values('n', ascending=False).head(40)
        out['areas'][key] = {
            'fy': fy,
            'sec': {s: [int(r.n), round(r.amt, 1), int(r.jobs), int(r.young)] for s, r in sec.iterrows() if s in SECTORS},
            'secPrior': {s: int(v) for s, v in before.items() if s in SECTORS},
            'loss': {s: [int(r.n), int(r.bad)] for s, r in loss.iterrows() if s in SECTORS},
            'top': [[c, int(r.n), int(ind_then.get(c, 0)), round(r.amt, 1)] for c, r in top.iterrows()],
        }
        for c in top.index:
            out['names'][c] = names.get(c, c)
        a = out['areas'][key]['fy']
        print(f'{key}: FY{fys[-1]} {a["n"][-1]:,} loans, ${a["amt"][-1]:,.0f}M; young {a["young"][-1]:,}')
    OUT.write_text(json.dumps(out, separators=(',', ':')))
    print(f'Wrote {OUT} ({OUT.stat().st_size / 1e3:.0f} KB)')


if __name__ == '__main__':
    sys.exit(main())
