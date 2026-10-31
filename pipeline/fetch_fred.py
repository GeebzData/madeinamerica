"""Download national series from FRED (no API key needed for the graph CSV endpoint)."""
import io
import sys
from pathlib import Path

import pandas as pd
import requests

ROOT = Path(__file__).resolve().parent
OUT = ROOT / 'warehouse' / 'fred.parquet'
URL = 'https://fred.stlouisfed.org/graph/fredgraph.csv?id={series}'
HEADERS = {'User-Agent': 'ManufacturingMap research (https://madeinamerica.gerardbarile.com)'}

SERIES = {
    'MANEMP': 'Manufacturing employment, thousands (BLS CES)',
    'IPMAN': 'Industrial production: manufacturing, index 2017=100 (Federal Reserve G.17)',
    'TLMFGCONS': 'Construction spending: manufacturing, $ millions SAAR (Census)',
    'CPIAUCSL': 'Consumer price index, all urban consumers (BLS)',
    'PCU236211236211': 'Producer price index: new industrial building construction (BLS)',
}


def main():
    frames = []
    for series in SERIES:
        r = requests.get(URL.format(series=series), headers=HEADERS, timeout=60)
        r.raise_for_status()
        df = pd.read_csv(io.StringIO(r.text))
        df.columns = ['date', 'value']
        df['value'] = pd.to_numeric(df['value'], errors='coerce')
        df['series'] = series
        frames.append(df.dropna())
        print(f'  {series}: {len(df)} rows, {df.date.min()} to {df.date.max()}')
    out = pd.concat(frames, ignore_index=True)
    out['date'] = pd.to_datetime(out['date'])
    OUT.parent.mkdir(parents=True, exist_ok=True)
    out.to_parquet(OUT, index=False)
    print(f'Wrote {OUT}')


if __name__ == '__main__':
    sys.exit(main())
