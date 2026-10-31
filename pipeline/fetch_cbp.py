"""Download Census County Business Patterns and count manufacturing plants by size.

Plants (establishments) are grouped by number of employees: 1-19, 20-99, 100-499 and 500+.
Census withholds some size counts ("N") to protect individual employers; those plants are kept
as "size not published" so every row still adds up to the total plant count.
"""
import io
import json
import sys
import zipfile
from pathlib import Path

import pandas as pd
import requests

from export import GROUPS, PIECES

ROOT = Path(__file__).resolve().parent
RAW = ROOT / 'raw' / 'cbp'
OUT = ROOT.parent / 'site' / 'data' / 'plants.json'
URL = 'https://www2.census.gov/programs-surveys/cbp/datasets/{year}/cbp{yy}{geo}.zip'
HEADERS = {'User-Agent': 'Mozilla/5.0 ManufacturingMap research (https://madeinamerica.gerardbarile.com)'}
BANDS = {
    '1-19': ['n<5', 'n5_9', 'n10_19'],
    '20-99': ['n20_49', 'n50_99'],
    '100-499': ['n100_249', 'n250_499'],
    '500+': ['n500_999', 'n1000'],
}


def download(year, geo):
    """Path to the year's county ('co') or state ('st') file, downloading it if needed. None if not out yet."""
    yy = str(year)[2:]
    path = RAW / f'cbp{yy}{geo}.zip'
    if not path.exists():
        r = requests.get(URL.format(year=year, yy=yy, geo=geo), headers=HEADERS, timeout=300)
        if r.status_code == 404:
            return None
        r.raise_for_status()
        RAW.mkdir(parents=True, exist_ok=True)
        path.write_bytes(r.content)
    return path


def read(path):
    with zipfile.ZipFile(path) as z:
        with z.open(z.namelist()[0]) as f:
            return pd.read_csv(io.TextIOWrapper(f, encoding='latin-1'), dtype=str)


def cbp_code(code):
    """PIECES code to the CBP NAICS spelling: 3361 -> 3361//, 331 -> 331///."""
    return code + '/' * (6 - len(code))


def bands(rows):
    """[1-19, 20-99, 100-499, 500+, size not published] summed over the rows."""
    out = []
    for cols in BANDS.values():
        out.append(int(sum(pd.to_numeric(rows[c], errors='coerce').fillna(0).sum() for c in cols)))
    total = int(pd.to_numeric(rows['est'], errors='coerce').fillna(0).sum())
    out.append(total - sum(out))
    return out


def main():
    year = next(y for y in range(2030, 2016, -1) if download(y, 'co'))
    county = read(download(year, 'co'))
    state = read(download(year, 'st'))
    state = state[state['lfo'] == '-']

    out = {'year': year, 'bands': list(BANDS), 'states': {}, 'counties': {}}
    mfg = county[county['naics'] == '31----']
    for _, row in mfg.iterrows():
        out['counties'][row['fipstate'] + row['fipscty']] = bands(row.to_frame().T)

    codes = {g: [cbp_code(c) for c, p in PIECES.items() if p[1] == g] for g in GROUPS}
    for fips, rows in state.groupby('fipstate'):
        entry = {'all': bands(rows[rows['naics'] == '31----']), 'groups': {}}
        for g, cs in codes.items():
            entry['groups'][g] = bands(rows[rows['naics'].isin(cs)])
        out['states'][fips] = entry

    OUT.write_text(json.dumps(out, separators=(',', ':')))
    print(f'Wrote {year} plant sizes for {len(out["states"])} states and {len(out["counties"])} counties to {OUT}')


if __name__ == '__main__':
    sys.exit(main())
