"""Download BLS QCEW annual manufacturing data, 1990 to the latest year.

Keeps private-sector rows for NAICS 31-33, its 21 three-digit subsectors and the
four-digit industries the site's industry groups split out, at the national, state
and county levels. Recent years come from the QCEW open-data API; older years come
from the bulk annual zip files, where only the manufacturing members are extracted.
"""
import re
import sys
import zipfile
from datetime import date
from pathlib import Path

import pandas as pd
import requests

ROOT = Path(__file__).resolve().parent
RAW = ROOT / 'raw' / 'qcew'
OUT = ROOT / 'warehouse' / 'qcew.parquet'
HEADERS = {'User-Agent': 'ManufacturingMap research (https://madeinamerica.gerardbarile.com)'}
API = 'https://data.bls.gov/cew/data/api/{year}/a/industry/{code}.csv'
ZIP = 'https://data.bls.gov/cew/data/files/{year}/csv/{year}_annual_by_industry.zip'

FIRST_YEAR = 1990
INDUSTRIES = ['31-33', '311', '312', '313', '314', '315', '316', '321', '322', '323', '324', '325',
              '326', '327', '331', '332', '333', '334', '335', '336', '337', '339',
              '3251', '3252', '3253', '3254', '3255', '3256', '3259',
              '3341', '3342', '3343', '3344', '3345', '3346',
              '3351', '3352', '3353', '3359',
              '3361', '3362', '3363', '3364', '3365', '3366', '3369',
              '3391', '3399']
# 14/15/16 = national, 54/55/56 = state, 74/75/76 = county (sector / 3-digit / 4-digit)
AGG_LEVELS = {14, 15, 16, 54, 55, 56, 74, 75, 76}
COLUMNS = ['area_fips', 'own_code', 'industry_code', 'agglvl_code', 'year', 'disclosure_code',
           'annual_avg_estabs', 'annual_avg_emplvl', 'avg_annual_pay']


def year_dir(year):
    return RAW / str(year)


def missing_codes(year):
    """Codes with neither a cached file nor a marker saying BLS has no file for that year."""
    d = year_dir(year)
    return [c for c in INDUSTRIES if not (d / f'{c}.csv').exists() and not (d / f'{c}.missing').exists()]


def api_has(year):
    r = requests.head(API.format(year=year, code='31_33'), headers=HEADERS, timeout=60)
    return r.status_code == 200


def fetch_api(year, codes):
    d = year_dir(year)
    d.mkdir(parents=True, exist_ok=True)
    for code in codes:
        r = requests.get(API.format(year=year, code=code.replace('-', '_')), headers=HEADERS, timeout=120)
        if r.status_code == 404:
            (d / f'{code}.missing').touch()
            print(f'  {year}: no file for {code}')
            continue
        r.raise_for_status()
        (d / f'{code}.csv').write_bytes(r.content)


def fetch_zip(year):
    d = year_dir(year)
    d.mkdir(parents=True, exist_ok=True)
    zpath = RAW / f'{year}.zip'
    with requests.get(ZIP.format(year=year), headers=HEADERS, stream=True, timeout=600) as r:
        r.raise_for_status()
        with open(zpath, 'wb') as f:
            for chunk in r.iter_content(1 << 20):
                f.write(chunk)
    pattern = re.compile(r'annual (31-33|3\d{2,3}) ')
    with zipfile.ZipFile(zpath) as z:
        for name in z.namelist():
            m = pattern.search(Path(name).name)
            if m and m.group(1) in INDUSTRIES:
                (d / f'{m.group(1)}.csv').write_bytes(z.read(name))
    zpath.unlink()
    for code in missing_codes(year):
        (d / f'{code}.missing').touch()
        print(f'  {year}: no file for {code}')


def latest_year():
    year = date.today().year
    while year > FIRST_YEAR:
        r = requests.head(API.format(year=year, code='31_33'), headers=HEADERS, timeout=60)
        if r.status_code == 200:
            return year
        year -= 1
    raise RuntimeError('Could not find any QCEW annual data')


def load_year(year):
    frames = []
    for path in sorted(year_dir(year).glob('*.csv')):
        df = pd.read_csv(path, usecols=lambda c: c in COLUMNS or c == 'annual_avg_estabs_count',
                         dtype={'area_fips': str, 'own_code': str, 'industry_code': str, 'disclosure_code': str})
        df = df.rename(columns={'annual_avg_estabs_count': 'annual_avg_estabs'})[COLUMNS]
        df = df[(df.own_code == '5') & df.agglvl_code.isin(AGG_LEVELS)]
        frames.append(df)
    return pd.concat(frames, ignore_index=True)


def main():
    last = latest_year()
    print(f'QCEW annual data available {FIRST_YEAR}-{last}')
    for year in range(FIRST_YEAR, last + 1):
        codes = missing_codes(year)
        if not codes:
            continue
        print(f'  fetching {year}...', flush=True)
        if api_has(year):
            fetch_api(year, codes)
        else:
            fetch_zip(year)
    df = pd.concat([load_year(y) for y in range(FIRST_YEAR, last + 1)], ignore_index=True)
    df['suppressed'] = df.disclosure_code.fillna('').eq('N')
    df = df.drop(columns=['own_code', 'disclosure_code'])
    OUT.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(OUT, index=False)
    print(f'Wrote {len(df):,} rows to {OUT}')


if __name__ == '__main__':
    sys.exit(main())
