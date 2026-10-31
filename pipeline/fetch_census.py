"""Download Census private construction spending (C30) and keep manufacturing by type.

Monthly, seasonally adjusted annual rate, millions of dollars. Census shows seven manufacturing
types separately; the rest of manufacturing is not broken out.
"""
import sys
from pathlib import Path

import pandas as pd
import requests

ROOT = Path(__file__).resolve().parent
RAW = ROOT / 'raw' / 'census' / 'privsatime.xlsx'
OUT = ROOT / 'warehouse' / 'construction.parquet'
URL = 'https://www.census.gov/construction/c30/xls/privsatime.xlsx'
HEADERS = {'User-Agent': 'Mozilla/5.0 ManufacturingMap research (https://madeinamerica.gerardbarile.com)'}

TYPES = {
    'Manufacturing': 'total',
    'Food/beverage/ tobacco': 'food',
    'Chemical': 'chemical',
    'Plastic/rubber': 'plastics',
    'Nonmetallic mineral': 'minerals',
    'Fabricated metal': 'fabricated',
    'Computer/ electronic/ electrical': 'electronics',
    'Transportation equipment': 'transportation',
}


def main():
    r = requests.get(URL, headers=HEADERS, timeout=120)
    r.raise_for_status()
    RAW.parent.mkdir(parents=True, exist_ok=True)
    RAW.write_bytes(r.content)

    sheet = pd.read_excel(RAW, header=None)
    header = [str(h).replace('\n_x000D_', ' ').replace('\n', ' ').strip() for h in sheet.iloc[3]]
    body = sheet.iloc[4:].copy()
    body.columns = header
    body['date'] = pd.to_datetime(body['Date'].astype(str).str.rstrip('pr'), format='%b-%y', errors='coerce')
    body = body[body.date.notna()]
    missing = [t for t in TYPES if t not in body.columns]
    if missing:
        raise RuntimeError(f'Census table layout changed; missing columns: {missing}')
    long = body.melt(id_vars='date', value_vars=list(TYPES), var_name='type', value_name='value')
    long['type'] = long['type'].map(TYPES)
    long['value'] = pd.to_numeric(long['value'], errors='coerce')
    long = long.dropna().sort_values(['type', 'date'])
    OUT.parent.mkdir(parents=True, exist_ok=True)
    long.to_parquet(OUT, index=False)
    print(f'Wrote {len(long)} rows, {long.date.min():%Y-%m} to {long.date.max():%Y-%m}, to {OUT}')


if __name__ == '__main__':
    sys.exit(main())
