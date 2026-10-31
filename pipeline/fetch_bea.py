"""Download BEA GDP by state and county and keep manufacturing.

Manufacturing GDP is the value manufacturers add (sales minus what they buy from other businesses).
"Real" figures are in chained 2017 dollars, so growth over time is after inflation; "nominal" figures
are in each year's dollars and are used for shares of the economy. County figures that BEA withholds
("(D)") are left blank. No API key is needed for the bulk files.
"""
import io
import json
import sys
import zipfile
from pathlib import Path

import pandas as pd
import requests

ROOT = Path(__file__).resolve().parent
RAW = ROOT / 'raw' / 'bea'
OUT = ROOT.parent / 'site' / 'data' / 'gdp.json'
URL = 'https://apps.bea.gov/regional/zip/{name}.zip'
HEADERS = {'User-Agent': 'Mozilla/5.0 ManufacturingMap research (https://madeinamerica.gerardbarile.com)'}
STATES = ['00', '01', '13', '47', '45', '28']
COUNTY_STATES = ['01', '13', '47', '45', '28']


def download(name):
    path = RAW / f'{name}.zip'
    r = requests.get(URL.format(name=name), headers=HEADERS, timeout=300)
    r.raise_for_status()
    RAW.mkdir(parents=True, exist_ok=True)
    path.write_bytes(r.content)
    return path


def read(path, prefix):
    with zipfile.ZipFile(path) as z:
        name = next(n for n in z.namelist() if n.startswith(prefix) and 'ALL_AREAS' in n)
        with z.open(name) as f:
            d = pd.read_csv(io.TextIOWrapper(f, encoding='latin-1'), dtype=str)
    d.columns = [c.strip() for c in d.columns]
    d['GeoFIPS'] = d['GeoFIPS'].str.strip().str.strip('"').str.strip()
    d['LineCode'] = pd.to_numeric(d['LineCode'], errors='coerce')
    d['Description'] = d['Description'].str.strip()
    return d


def values(row, years, scale=1.0):
    out = []
    for y in years:
        v = pd.to_numeric(row[str(y)], errors='coerce')
        out.append(None if pd.isna(v) else round(float(v) * scale, 1))
    return out


def main():
    sagdp = download('SAGDP')
    real = read(sagdp, 'SAGDP9_')
    nominal = read(sagdp, 'SAGDP2_')
    years = [int(c) for c in real.columns if c.isdigit()]
    out = {'years': years, 'states': {}, 'counties': {}}
    for fips in STATES:
        r = real[real['GeoFIPS'] == fips + '000']
        n = nominal[nominal['GeoFIPS'] == fips + '000']
        line = lambda d, code: d[d['LineCode'] == code].iloc[0]
        sub = {}
        subsectors = lambda d: d[(d['LineCode'] >= 14) & (d['LineCode'] <= 33) & (d['LineCode'] != 25)]
        for _, row in subsectors(r).iterrows():
            sub[row['Description']] = {'code': row['IndustryClassification'].strip(), 'real': values(row, years)}
        for _, row in subsectors(n).iterrows():
            sub.setdefault(row['Description'], {})['nominal'] = values(row, years)
        out['states'][fips] = {
            'total': values(line(n, 1), years), 'mfg': values(line(n, 12), years),
            'mfgReal': values(line(r, 12), years), 'totalReal': values(line(r, 1), years), 'sub': sub,
        }

    county_real = read(download('CAGDP9'), 'CAGDP9_')
    county_nominal = read(download('CAGDP2'), 'CAGDP2_')
    cyears = [int(c) for c in county_real.columns if c.isdigit()]
    out['countyYears'] = cyears
    for d, key in ((county_real, 'mfgReal'), (county_nominal, 'mfg'), (county_nominal, 'total')):
        code = 1 if key == 'total' else 12
        rows = d[(d['LineCode'] == code) & d['GeoFIPS'].str[:2].isin(COUNTY_STATES) & ~d['GeoFIPS'].str.endswith('000')]
        for _, row in rows.iterrows():
            # County files are in thousands of dollars; state files in millions.
            out['counties'].setdefault(row['GeoFIPS'], {})[key] = values(row, cyears, 0.001)
    OUT.write_text(json.dumps(out, separators=(',', ':')))
    al = out['states']['01']
    print(f'Wrote GDP {years[0]}-{years[-1]} for {len(out["states"])} areas and {len(out["counties"])} counties to {OUT}. '
          f'Alabama manufacturing {years[-1]}: ${al["mfg"][-1] / 1e3:.1f}B, {al["mfg"][-1] / al["total"][-1] * 100:.1f}% of GDP')


if __name__ == '__main__':
    sys.exit(main())
