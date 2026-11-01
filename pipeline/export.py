"""Turn the warehouse tables into the compact JSON files the site loads.

The site filters by story (strategic, legacy, industrial base, local) and industry group.
Each group and story is built from "pieces": three- or four-digit NAICS industries that
each belong to exactly one group and one story. Every story x group selection is
pre-aggregated, using a published three-digit total wherever the selection covers all of
that subsector, which keeps BLS suppression to a minimum.

Outputs (site/data/):
  meta.json                      years, stories, groups, pieces, build date
  national.json                  sel: selection x {e, n, p}, pc: piece x {e, n, p}, FRED series
  states.json                    state x {sel, pc}
  counties/<story>--<group>.json county x {e, n, p} for one selection (loaded on demand)
  counties/by-state/<ss>.json    county x {sel: group-level job arrays, pc: piece job arrays}

e = average annual employment, n = establishments, p = average annual pay in latest-year
dollars (CPI-U). Arrays are aligned to meta.years; null = suppressed or not reported.
"""
import json
import shutil
import sys
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent
WAREHOUSE = ROOT / 'warehouse'
OUT = ROOT.parent / 'site' / 'data'

# Categories (called "stories" in the data files). Every industry group sits in exactly one category.
STORIES = {
    'strategic': {'name': 'Strategic tech & defense',
                  'blurb': 'What the CHIPS Act, clean-energy tax credits and defense spending aim to build here: '
                           'semiconductors and electronics, batteries and grid equipment, aerospace, ships and rail, '
                           'and drugs and medical devices.'},
    'autos': {'name': 'Vehicles',
              'blurb': 'Cars, trucks, EVs and the parts that go into them, plus trailers and RVs.'},
    'base': {'name': 'Metals & machinery',
             'blurb': 'Steel, metal parts and machinery: the industrial base that other factories buy from.'},
    'chemmat': {'name': 'Chemicals & materials',
                'blurb': 'Chemicals, plastics, fuels, paper, wood and building materials: the inputs other industries are made from.'},
    'foodbev': {'name': 'Food & beverage',
                'blurb': 'Food processing, beverages and tobacco, which grow with population and nearby farms.'},
    'consumergoods': {'name': 'Consumer goods',
                      'blurb': 'Clothing, textiles, furniture, appliances, toys and other household goods: '
                               'the industries where imports took over most of the U.S. market.'},
}

GROUPS = {
    'chips': 'Semiconductors & electronics',
    'electrical': 'Batteries & electrical',
    'vehicles': 'Vehicles & EVs',
    'aero': 'Aerospace, ships & rail',
    'pharma': 'Pharma & medical',
    'metals': 'Steel & base metals',
    'machinery': 'Machinery',
    'fab': 'Metal fabrication',
    'chem': 'Chemicals, plastics & fuels',
    'textiles': 'Textiles & apparel',
    'consumer': 'Furniture & consumer goods',
    'food': 'Food & beverage',
    'materials': 'Wood, paper & building materials',
}

# code: (name, group, story)
PIECES = {
    '3344': ('Semiconductors & components', 'chips', 'strategic'),
    '3345': ('Instruments & controls', 'chips', 'strategic'),
    '3341': ('Computers & peripherals', 'chips', 'strategic'),
    '3342': ('Communications equipment', 'chips', 'strategic'),
    '3343': ('Audio & video equipment', 'chips', 'strategic'),
    '3346': ('Magnetic & optical media', 'chips', 'strategic'),
    '3353': ('Grid & electrical equipment', 'electrical', 'strategic'),
    '3359': ('Batteries, wire & other electrical', 'electrical', 'strategic'),
    '3351': ('Lighting', 'electrical', 'strategic'),
    '3361': ('Motor vehicles', 'vehicles', 'autos'),
    '3362': ('Truck bodies, trailers & RVs', 'vehicles', 'autos'),
    '3363': ('Vehicle parts', 'vehicles', 'autos'),
    '3369': ('Other transportation equipment', 'vehicles', 'autos'),
    '3364': ('Aerospace', 'aero', 'strategic'),
    '3365': ('Railroad rolling stock', 'aero', 'strategic'),
    '3366': ('Ships & boats', 'aero', 'strategic'),
    '3254': ('Pharmaceuticals', 'pharma', 'strategic'),
    '3391': ('Medical equipment & supplies', 'pharma', 'strategic'),
    '331': ('Steel & base metals', 'metals', 'base'),
    '333': ('Machinery', 'machinery', 'base'),
    '332': ('Metal fabrication', 'fab', 'base'),
    '3251': ('Basic chemicals', 'chem', 'chemmat'),
    '3252': ('Resins & synthetic rubber', 'chem', 'chemmat'),
    '3253': ('Fertilizers & pesticides', 'chem', 'chemmat'),
    '3255': ('Paints & adhesives', 'chem', 'chemmat'),
    '3256': ('Soaps & cosmetics', 'chem', 'chemmat'),
    '3259': ('Other chemicals', 'chem', 'chemmat'),
    '326': ('Plastics & rubber', 'chem', 'chemmat'),
    '324': ('Petroleum & coal products', 'chem', 'chemmat'),
    '313': ('Textile mills', 'textiles', 'consumergoods'),
    '314': ('Textile products', 'textiles', 'consumergoods'),
    '315': ('Apparel', 'textiles', 'consumergoods'),
    '316': ('Leather & footwear', 'textiles', 'consumergoods'),
    '337': ('Furniture', 'consumer', 'consumergoods'),
    '3352': ('Household appliances', 'consumer', 'consumergoods'),
    '3399': ('Toys, sporting goods, jewelry & other', 'consumer', 'consumergoods'),
    '311': ('Food', 'food', 'foodbev'),
    '312': ('Beverages & tobacco', 'food', 'foodbev'),
    '321': ('Wood products', 'materials', 'chemmat'),
    '323': ('Printing', 'materials', 'chemmat'),
    '327': ('Cement, concrete & glass', 'materials', 'chemmat'),
    '322': ('Paper', 'materials', 'chemmat'),
}

LEVELS = {'nation': (14, 15, 16), 'state': (54, 55, 56), 'county': (74, 75, 76)}


def write(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, separators=(',', ':')))


def parent(code):
    return code[:3]


def selections():
    out = {'all|all': list(PIECES)}
    for g in GROUPS:
        out[f'all|{g}'] = [c for c, v in PIECES.items() if v[1] == g]
    for s in STORIES:
        out[f'{s}|all'] = [c for c, v in PIECES.items() if v[2] == s]
        for g in GROUPS:
            chosen = [c for c, v in PIECES.items() if v[1] == g and v[2] == s]
            if chosen:
                out[f'{s}|{g}'] = chosen
    return out


def matrices(df, years, value):
    """code -> area x year frame. Suppressed cells are NaN. A missing row means no employers (0)
    in years whose files flag suppression; before 2001 BLS dropped suppressed rows instead, so
    there a missing row is unknown (NaN). Areas that reported nothing that year are NaN."""
    areas = sorted(df.area_fips.unique())
    flagged = set(df.loc[df.suppressed, 'year'])
    exists = df.groupby(['area_fips', 'year']).size().unstack().reindex(index=areas, columns=years).notna()
    zero_ok = exists & pd.Series({y: y in flagged for y in years})
    out = {}
    for code, g in df.groupby('industry_code'):
        vals = g.pivot(index='area_fips', columns='year', values=value).reindex(index=areas, columns=years)
        present = g.assign(one=1).pivot(index='area_fips', columns='year', values='one')
        present = present.reindex(index=areas, columns=years).notna()
        out[code] = vals.where(present, 0).where(present | zero_ok)
    return out


def resolve(pieces):
    """Codes to sum for a set of pieces, using a three-digit total when all its pieces are selected."""
    if set(pieces) == set(PIECES):
        return ['31-33']
    codes = []
    for p3 in sorted({parent(c) for c in pieces}):
        children = [c for c in PIECES if parent(c) == p3]
        chosen = [c for c in pieces if parent(c) == p3]
        codes += [p3] if set(chosen) == set(children) else chosen
    return codes


def estimate(e, n, w):
    """Fill withheld jobs and wages top-down: the withheld amount is exact (parent total minus
    published children) and is split among withheld children by establishment count, which BLS
    publishes even when jobs are withheld. Before 2001 withheld rows are missing entirely, so
    their 2001 establishment counts are used as weights. Returns filled e, w and, per code, the
    estimated number of jobs included in it."""
    original = dict(e)
    e, w = dict(e), dict(w)
    three = sorted({parent(c) for c in PIECES})
    families = [('31-33', three)] + [(p3, [c for c in PIECES if parent(c) == p3 and len(c) == 4])
                                      for p3 in three]
    for top, children in families:
        if not children or top not in e:
            continue
        missing = {c: e[c].isna() for c in children}
        weights = {}
        for c in children:
            wt = n[c].copy()
            for y in [y for y in wt.columns if y < 2001 and 2001 in wt.columns]:
                wt[y] = wt[y].fillna(n[c][2001])
            weights[c] = wt.where(missing[c], 0)
        weight_sum = sum(weights.values())
        missing_count = sum(m.astype(int) for m in missing.values())
        rest_e = (e[top] - sum(e[c].fillna(0) for c in children)).clip(lower=0)
        rest_w = (w[top] - sum(w[c].fillna(0) for c in children)).clip(lower=0)
        for c in children:
            even = missing[c].astype(float) / missing_count.where(missing_count > 0)
            share = (weights[c].fillna(0) / weight_sum.where(weight_sum > 0)).fillna(even)
            e[c] = e[c].fillna(rest_e * share)
            w[c] = w[c].fillna(rest_w * share)
    est = {c: e[c].where(original[c].isna(), 0) for c in e}
    return e, w, est


def total_of(mats, codes):
    """Sum of codes; NaN wherever any of them is NaN."""
    out = None
    for c in codes:
        out = mats[c] if out is None else out.add(mats[c])
    return out


def pieces_value(mats, pieces):
    """Sum of pieces, subsector by subsector. Uses the published three-digit total when all of a
    subsector is selected; when some selected parts are withheld, recovers them as the subsector
    total minus the unselected parts."""
    out = None
    for p3 in sorted({parent(c) for c in pieces}):
        children = [c for c in PIECES if parent(c) == p3]
        chosen = [c for c in pieces if parent(c) == p3]
        if set(chosen) == set(children):
            part = mats[p3]
        else:
            others = [c for c in children if c not in chosen]
            part = total_of(mats, chosen).fillna((mats[p3] - total_of(mats, others)).clip(lower=0))
        out = part if out is None else out.add(part)
    return out


def selection_value(mats, pieces):
    """A selection's value, falling back to all manufacturing minus everything else."""
    if set(pieces) == set(PIECES):
        return mats['31-33']
    direct = pieces_value(mats, pieces)
    rest = pieces_value(mats, [c for c in PIECES if c not in pieces])
    return direct.fillna((mats['31-33'] - rest).clip(lower=0))


def pay(wages, jobs):
    return (wages / jobs.where(jobs > 0)).round()


def rows(frame):
    """area -> list, with None for NaN."""
    arr = frame.to_numpy()
    return {area: [None if np.isnan(v) else int(round(v)) for v in arr[i]] for i, area in enumerate(frame.index)}


def build(df, years, estimated=False, keys=None):
    """area -> {'sel': {key: {e, n, p[, x]}}, 'pc': {code: {e, n, p[, x]}}} for one geography level.
    With estimated=True, withheld figures are filled (see estimate) and x flags estimated years."""
    e = matrices(df, years, 'e_val')
    n = matrices(df, years, 'annual_avg_estabs')
    w = matrices(df, years, 'wages')
    est = None
    if estimated:
        e, w, est = estimate(e, n, w)
    out = {}

    def add(kind, key, es, ns, ws, xs=None):
        metrics = [('e', es), ('n', ns), ('p', pay(ws, es))]
        for metric, frame in metrics:
            for area, values in rows(frame).items():
                out.setdefault(area, {'sel': {}, 'pc': {}})[kind].setdefault(key, {})[metric] = values
        if xs is not None:
            # x = percent of the jobs figure that is estimated, kept only where it is 10% or more
            pct = (xs / es.where(es > 0) * 100).round()
            pct = pct.where(pct >= 10, 0)
            for area, values in rows(pct).items():
                if any(values):
                    out[area][kind][key]['x'] = [v or 0 for v in values]

    for key, pieces in selections().items():
        if keys is not None and key not in keys:
            continue
        if estimated:
            codes = resolve(pieces)
            add('sel', key, total_of(e, codes), total_of(n, codes), total_of(w, codes),
                sum(est[c].fillna(0) for c in codes))
        else:
            add('sel', key, selection_value(e, pieces), selection_value(n, pieces), selection_value(w, pieces))
    if keys is None:
        for code in PIECES:
            if code in e:
                add('pc', code, e[code], n[code], w[code], est[code].fillna(0) if estimated else None)
    return out


def annual(fred, series, first, last, scale=1.0):
    s = fred[fred.series == series].set_index('date').value
    full = s.groupby(s.index.year).count()
    s = s.groupby(s.index.year).mean()
    s = s[(s.index >= first) & (s.index <= last) & (full.reindex(s.index) == 12)]
    return {'years': [int(y) for y in s.index], 'values': [round(v * scale, 2) for v in s]}


def latest(fred, series, scale=1.0):
    s = fred[fred.series == series].sort_values('date').iloc[-1]
    return {'date': s.date.strftime('%Y-%m'), 'value': round(s.value * scale, 2)}


CONSTRUCTION_TYPES = {
    'electronics': 'Computers, electronics & electrical (incl. chips, batteries)',
    'chemical': 'Chemicals',
    'transportation': 'Transportation equipment (incl. EVs)',
    'food': 'Food, beverage & tobacco',
    'plastics': 'Plastics & rubber',
    'minerals': 'Cement, concrete & glass',
    'fabricated': 'Fabricated metal',
    'other': 'All other manufacturing',
}


def reindustrialization(fred, construction):
    """Factory construction spending in real dollars (deflated with the BLS producer price index
    for new industrial building construction), monthly and by type."""
    ppi = fred[fred.series == 'PCU236211236211'].set_index('date').value
    wide = construction.pivot(index='date', columns='type', values='value')
    wide['other'] = wide['total'] - wide[[t for t in CONSTRUCTION_TYPES if t != 'other']].sum(axis=1)
    wide = wide[wide.index >= ppi.index.min()]
    price = ppi.reindex(wide.index).ffill()
    base = price.iloc[-1]
    real = wide.mul(base / price, axis=0) / 1000
    nominal = wide / 1000
    last12 = real.iloc[-12:].mean()
    before = real.loc['2019-01-01':'2021-12-01'].mean()
    full_years = real.groupby(real.index.year).filter(lambda g: len(g) == 12)
    annual = full_years.groupby(full_years.index.year)['total'].mean()
    return {
        'latest': real.index[-1].strftime('%Y-%m'),
        'dollarsOf': real.index[-1].strftime('%B %Y'),
        'monthly': {
            'dates': [d.strftime('%Y-%m') for d in real.index],
            'real': [round(v, 1) for v in real['total']],
            'nominal': [round(v, 1) for v in nominal['total']],
        },
        'byType': [{'id': t, 'name': name, 'before': round(before[t], 1), 'recent': round(last12[t], 1)}
                   for t, name in CONSTRUCTION_TYPES.items()],
        'total': {'before': round(before['total'], 1), 'recent': round(last12['total'], 1)},
        'annualReal': {'years': [int(y) for y in annual.index], 'values': [round(v, 1) for v in annual]},
    }


def has_data(arr):
    return any(v not in (None, 0) for v in arr)


def main():
    qcew = pd.read_parquet(WAREHOUSE / 'qcew.parquet')
    fred = pd.read_parquet(WAREHOUSE / 'fred.parquet')
    years = list(range(int(qcew.year.min()), int(qcew.year.max()) + 1))

    cpi = fred[fred.series == 'CPIAUCSL'].set_index('date').value
    cpi = cpi.groupby(cpi.index.year).mean()
    qcew = qcew[~qcew.area_fips.str.endswith('999')].copy()
    qcew['e_val'] = qcew.annual_avg_emplvl.where(~qcew.suppressed)
    qcew['wages'] = qcew.e_val * qcew.avg_annual_pay * qcew.year.map(cpi[years[-1]] / cpi)
    codes_needed = set(PIECES) | {parent(c) for c in PIECES} | {'31-33'}
    qcew = qcew[qcew.industry_code.isin(codes_needed)]

    county_keys = {'all|all'} | {f'all|{g}' for g in GROUPS}
    built = {
        'nation': build(qcew[qcew.agglvl_code.isin(LEVELS['nation'])], years, estimated=True),
        'state': build(qcew[qcew.agglvl_code.isin(LEVELS['state'])], years, estimated=True),
        'county': build(qcew[qcew.agglvl_code.isin(LEVELS['county'])], years, keys=county_keys),
    }
    shutil.rmtree(OUT / 'counties', ignore_errors=True)

    nation = built['nation']['US000']
    write(OUT / 'national.json', {
        'sel': nation['sel'],
        'pc': nation['pc'],
        'jobs': annual(fred, 'MANEMP', 1979, years[-1], 0.001),
        'output': annual(fred, 'IPMAN', 1979, years[-1]),
        'outputExHiTech': annual(fred, 'IPX4HTMVS', 1979, years[-1]),
        'construction': annual(fred, 'TLMFGCONS', 2002, years[-1], 0.001),
        'latest': {'jobs': latest(fred, 'MANEMP', 0.001), 'output': latest(fred, 'IPMAN'),
                   'construction': latest(fred, 'TLMFGCONS', 0.001)},
    })

    write(OUT / 'states.json', {fips[:2]: v for fips, v in built['state'].items()})
    write(OUT / 'reindustrialization.json',
          reindustrialization(fred, pd.read_parquet(WAREHOUSE / 'construction.parquet')))

    # Counties: published figures only (no estimates), all manufacturing plus group-level jobs
    # for the hover breakdown. Finer county detail is mostly withheld by BLS.
    counties = built['county']
    write(OUT / 'counties' / 'all--all.json',
          {f: c['sel']['all|all'] for f, c in counties.items() if has_data(c['sel']['all|all']['e'] + c['sel']['all|all']['n'])})
    by_state = {}
    for fips, c in counties.items():
        groups = {k: v['e'] for k, v in c['sel'].items() if k != 'all|all' and has_data(v['e'])}
        by_state.setdefault(fips[:2], {})[fips] = {'sel': groups, 'pc': {}}
    for st, rows in by_state.items():
        write(OUT / 'counties' / 'by-state' / f'{st}.json', rows)

    write(OUT / 'meta.json', {
        'years': years,
        'built': date.today().isoformat(),
        'stories': STORIES,
        'groups': GROUPS,
        'pieces': {c: {'name': v[0], 'group': v[1], 'story': v[2]} for c, v in PIECES.items()},
        'selections': sorted(selections()),
        'payDollarsYear': years[-1],
    })
    print(f'Exported {years[0]}-{years[-1]}, {len(selections())} selections, to {OUT}')


if __name__ == '__main__':
    sys.exit(main())
