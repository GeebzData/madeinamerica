"""Build site/data/productivity.json: output per worker, output per hour, other countries, and robots.

Sources (all free; downloads cached in pipeline/raw/productivity/, which is gitignored):
- BLS labor productivity, manufacturing sector, output per hour (FRED OPHMFG, 2017 = 100), quarterly.
- Real output per factory worker: BEA real manufacturing GDP (site/data/gdp.json) divided by
  BLS CES manufacturing jobs (site/data/national.json), both annual.
- Other countries: World Bank manufacturing value added in current U.S. dollars (NV.IND.MANF.CD)
  divided by ILO manufacturing employment (ILOSTAT, ISIC Rev. 4 section C, household surveys).
  The World Bank stops publishing the U.S. after 2021, so the U.S. uses BEA's nominal figure.
- Labor force: BLS civilian labor force (FRED CLF16OV), annual averages, to size factory jobs against it.
- Why output per worker rose: BEA real value added by manufacturing industry (gdp.json) against
  BLS QCEW private jobs in the same industries (national.json), 1997 and the latest year.
- Robots: Census Annual Capital Expenditures Survey robotics tables (2020-2022), the 2022 Economic
  Census robotics tables (experimental), and U.S. imports of industrial robots (HS 847950) from
  UN Comtrade, because the Census trade API now needs a key.
"""
import csv
import io
import json
import sys
import time
from pathlib import Path

import openpyxl
import requests

ROOT = Path(__file__).resolve().parent
RAW = ROOT / 'raw' / 'productivity'
SITE = ROOT.parent / 'site' / 'data'
OUT = SITE / 'productivity.json'
HEADERS = {'User-Agent': 'ManufacturingMap research (https://madeinamerica.gerardbarile.com)'}

FRED = 'https://fred.stlouisfed.org/graph/fredgraph.csv?id=OPHMFG'
CLF = 'https://fred.stlouisfed.org/graph/fredgraph.csv?id=CLF16OV'
WB = 'https://api.worldbank.org/v2/country/{codes}/indicator/NV.IND.MANF.CD?format=json&date=2015:2025&per_page=500'
ILO = ('https://sdmx.ilo.org/rest/data/ILO,DF_EMP_TEMP_SEX_ECO_NB,1.0/{codes}.A..SEX_T.ECO_ISIC4_C'
       '?startPeriod=2015')
ACES = 'https://www2.census.gov/programs-surveys/aces/visualizations/{year}/robotics/table1a.xlsx'
ACES_PAGE = 'https://www.census.gov/library/publications/2023/econ/2022-robotic-equipment.html'
EC = 'https://www2.census.gov/programs-surveys/economic-census/data/2022/sector31/2022-ec-robotics-tables.xlsx'
EC_PAGE = 'https://www.census.gov/library/publications/2025/econ/2022-ec-robotic-equipment.html'
COMTRADE = ('https://comtradeapi.un.org/public/v1/preview/C/A/HS?reporterCode=842&cmdCode=847950'
            '&flowCode=M&partnerCode=0&period={year}')

COUNTRIES = {
    'USA': 'United States', 'DEU': 'Germany', 'GBR': 'United Kingdom', 'KOR': 'South Korea',
    'FRA': 'France', 'JPN': 'Japan', 'ITA': 'Italy', 'MEX': 'Mexico', 'VNM': 'Vietnam', 'IND': 'India',
}
SE = ['Alabama', 'Georgia', 'Tennessee', 'South Carolina', 'North Carolina', 'Kentucky', 'Mississippi']

# Hand-compiled from company releases and trade press, each with its link.
DEPLOYMENTS = [
    {'place': 'BMW, Spartanburg, South Carolina', 'when': 'August 2024',
     'what': "Figure 02 humanoids spent several weeks placing sheet-metal parts into fixtures in the body shop. "
             "BMW said the trial worked and set no date for bringing them back.",
     'url': 'https://newsroom.bmwgroup.com/americas/successful-test-of-humanoid-robots-at-bmw-group-plant-spartanburg',
     'source': 'BMW Group'},
    {'place': 'Hyundai Metaplant, near Savannah, Georgia', 'when': 'September 2026',
     'what': "Boston Dynamics opened a center inside the plant to train Atlas humanoids on parts logistics, "
             "sorting and sequencing. Hyundai and Kia plan to deploy Atlas robots across their plants.",
     'url': 'https://www.therobotreport.com/boston-dynamics-opens-metaplant-application-center-train-atlas-humanoid-robots/',
     'source': 'The Robot Report'},
]


def get(url, name, binary=False, accept=None):
    """Download once into RAW and reuse the copy after that."""
    path = RAW / name
    if not path.exists():
        r = requests.get(url, headers={**HEADERS, 'Accept': accept} if accept else HEADERS, timeout=120)
        r.raise_for_status()
        path.write_bytes(r.content)
    return path.read_bytes() if binary else path.read_text()


def output_per_hour():
    rows = list(csv.reader(io.StringIO(get(FRED, 'ophmfg.csv'))))[1:]
    by_year = {}
    for date, value in rows:
        if value not in ('', '.'):
            by_year.setdefault(int(date[:4]), []).append(float(value))
    full = {y: v for y, v in by_year.items() if len(v) == 4}
    years = sorted(full)
    latest = rows[-1]
    return {
        'years': years,
        'values': [round(sum(full[y]) / 4, 1) for y in years],
        'latest': {'quarter': f'{latest[0][:4]} Q{(int(latest[0][5:7]) - 1) // 3 + 1}', 'value': float(latest[1])},
        'series': 'OPHMFG',
    }


def output_per_worker():
    gdp = json.loads((SITE / 'gdp.json').read_text())
    national = json.loads((SITE / 'national.json').read_text())
    real = dict(zip(gdp['years'], gdp['states']['00']['mfgReal']))
    jobs = dict(zip(national['jobs']['years'], national['jobs']['values']))
    years = [y for y in gdp['years'] if real.get(y) and jobs.get(y)]
    # Real GDP is in millions of chained 2017 dollars; jobs are in millions.
    return {
        'years': years,
        'perWorker': [round(real[y] / jobs[y]) for y in years],
        'realGdp': [real[y] for y in years],
        'jobs': [jobs[y] for y in years],
    }


def labor_force():
    rows = list(csv.reader(io.StringIO(get(CLF, 'clf16ov.csv'))))[1:]
    by_year = {}
    for date, value in rows:
        if value not in ('', '.'):
            by_year.setdefault(int(date[:4]), []).append(float(value))
    # October 2025 was never collected (federal shutdown), so a year needs 11 of 12 months.
    years = sorted(y for y, v in by_year.items() if len(v) >= 11 and y < max(by_year))
    # FRED reports thousands of people; keep millions.
    return {'years': years, 'millions': [round(sum(by_year[y]) / len(by_year[y]) / 1e3, 2) for y in years], 'series': 'CLF16OV'}


SHORT = {
    '321': 'Wood products', '327': 'Glass, cement & stone', '331': 'Primary metals', '332': 'Fabricated metal',
    '333': 'Machinery', '334': 'Computers & electronics', '335': 'Electrical equipment',
    '3361-3363': 'Motor vehicles & parts', '3364-3466,3369': 'Aerospace, ships & rail', '337': 'Furniture',
    '339': 'Medical devices & other', '311-312': 'Food, beverage & tobacco', '313-314': 'Textiles',
    '315-316': 'Apparel & leather', '322': 'Paper', '323': 'Printing', '324': 'Petroleum & coal',
    '325': 'Chemicals & pharma', '326': 'Plastics & rubber',
}


def why_per_worker():
    """Split the rise in output per worker into better output within industries and a shift in mix.

    Chained dollars do not add up exactly across industries, so these splits are approximate.
    """
    gdp = json.loads((SITE / 'gdp.json').read_text())
    national = json.loads((SITE / 'national.json').read_text())
    years = json.loads((SITE / 'meta.json').read_text())['years']
    y0, y1 = gdp['years'][0], gdp['years'][-1]
    i0, i1 = years.index(y0), years.index(y1)

    def jobs(code, i):
        prefixes = []
        for part in code.replace('3466', '3366').split(','):
            lo, _, hi = part.partition('-')
            prefixes += [str(c) for c in range(int(lo), int(hi or lo) + 1)]
        return sum(v['e'][i] or 0 for k, v in national['pc'].items() if any(k.startswith(p) for p in prefixes))

    rows = []
    for sub in gdp['states']['00']['sub'].values():
        rows.append({'code': sub['code'], 'name': SHORT[sub['code']], 'real0': sub['real'][0], 'real1': sub['real'][-1],
                     'jobs0': jobs(sub['code'], i0), 'jobs1': jobs(sub['code'], i1)})
    for r in rows:
        r['ratio'] = round((r['real1'] / r['jobs1']) / (r['real0'] / r['jobs0']), 2)
    tot = {k: sum(r[k] for r in rows) for k in ('real0', 'real1', 'jobs0', 'jobs1')}
    base = tot['real0'] / tot['jobs0']
    within = sum(r['jobs0'] / tot['jobs0'] * r['real1'] / r['jobs1'] for r in rows) / base
    mix = sum(r['jobs1'] / tot['jobs1'] * r['real0'] / r['jobs0'] for r in rows) / base
    ex = [r for r in rows if r['code'] != '334']
    ex_ratio = (sum(r['real1'] for r in ex) / sum(r['jobs1'] for r in ex)) / (sum(r['real0'] for r in ex) / sum(r['jobs0'] for r in ex))
    return {
        'years': [y0, y1],
        'rows': sorted(rows, key=lambda r: -r['jobs1']),
        'within': round(within, 2), 'mix': round(mix, 2), 'exComputers': round(ex_ratio, 2),
        'total': round((tot['real1'] / tot['jobs1']) / base, 2),
    }


def countries(year):
    va = {}
    for r in json.loads(get(WB.format(codes=';'.join([*COUNTRIES, 'CHN'])), 'wb_mfg_va.json'))[1]:
        if r['value']:
            va.setdefault(r['countryiso3code'], {})[int(r['date'])] = r['value']
    gdp = json.loads((SITE / 'gdp.json').read_text())
    us = dict(zip(gdp['years'], gdp['states']['00']['mfg']))
    va['USA'] = {y: v * 1e6 for y, v in us.items() if v}
    emp = {}
    for r in csv.DictReader(io.StringIO(get(ILO.format(codes='+'.join(COUNTRIES)), 'ilo_mfg_emp.csv',
                                           accept='application/vnd.sdmx.data+csv'))):
        emp.setdefault(r['REF_AREA'], {})[int(r['TIME_PERIOD'])] = float(r['OBS_VALUE']) * 1e3
    rows = []
    for code, name in COUNTRIES.items():
        v, e = va.get(code, {}).get(year), emp.get(code, {}).get(year)
        if v and e:
            rows.append({'code': code, 'name': name, 'valueAdded': round(v / 1e9, 1),
                         'workers': round(e / 1e6, 2), 'perWorker': round(v / e)})
    china = va.get('CHN', {}).get(year)
    return {'year': year, 'rows': sorted(rows, key=lambda r: -r['perWorker']),
            'chinaValueAdded': round(china / 1e9) if china else None}


def aces():
    out = []
    for year in (2020, 2021, 2022):
        ws = openpyxl.load_workbook(io.BytesIO(get(ACES.format(year=year), f'aces_{year}.xlsx', True)),
                                    data_only=True).active
        row = {'year': year}
        for cells in ws.iter_rows(values_only=True):
            if cells[1] == 'Total':
                row['total'] = cells[2]
            elif cells[0] == '31-33':
                row['manufacturing'] = cells[2]
        out.append(row)
    return out


def economic_census():
    wb = openpyxl.load_workbook(io.BytesIO(get(EC, 'ec2022_robotics.xlsx', True)), data_only=True)
    def table(prefix, start):
        ws = next(s for s in wb.worksheets if s.title.startswith(prefix))
        return [r for r in ws.iter_rows(min_row=start, values_only=True) if r[0] is not None]
    geo = {r[0]: r for r in table('Percent of... Geo', 6) if isinstance(r[1], float)}
    capex = {r[0]: r[1] for r in table('CapEx... Geo', 6) if isinstance(r[1], (int, float))}
    states = [{'name': n, 'plants': geo[n][1], 'workers': geo[n][2], 'capex': capex.get(n)}
              for n in ['United States'] + SE if n in geo]
    industries = [{'naics': str(r[0]), 'name': r[1], 'plants': r[2], 'workers': r[3]}
                  for r in table('Percent of... NAICS', 6) if isinstance(r[2], float) and str(r[0]) != '31-33']
    sizes = [{'size': r[0], 'plants': r[1], 'workers': r[2]}
             for r in table('Robot adoption and plant size', 6) if isinstance(r[1], float)]
    return {'states': states, 'industries': industries, 'sizes': sizes}


def robot_imports():
    out = []
    for year in range(2013, 2026):
        name = f'comtrade_847950_{year}.json'
        if not (RAW / name).exists():
            time.sleep(4)  # The public preview endpoint drops requests that come too fast.
        data = json.loads(get(COMTRADE.format(year=year), name)).get('data') or []
        if data:
            out.append({'year': year, 'millions': round(data[0]['primaryValue'] / 1e6)})
        else:
            (RAW / name).unlink()
            print(f'  Comtrade returned nothing for {year}; rerun to try again')
    return out


def main():
    RAW.mkdir(parents=True, exist_ok=True)
    out = {
        'perHour': output_per_hour(),
        'perWorker': output_per_worker(),
        'countries': countries(2023),
        'laborForce': labor_force(),
        'why': why_per_worker(),
        'robots': {
            'aces': aces(),
            'acesUrl': ACES_PAGE,
            'census2022': economic_census(),
            'censusUrl': EC_PAGE,
            'imports': robot_imports(),
            'deployments': DEPLOYMENTS,
        },
    }
    OUT.write_text(json.dumps(out, separators=(',', ':')))
    pw = out['perWorker']
    print(f"Output per worker {pw['years'][0]}: ${pw['perWorker'][0]:,}; {pw['years'][-1]}: ${pw['perWorker'][-1]:,}")
    print(f"Countries {out['countries']['year']}: " + ', '.join(f"{r['code']} ${r['perWorker'] / 1e3:.0f}k" for r in out['countries']['rows']))
    w = out['why']
    print(f"Why per worker: total {w['total']}x, within industries {w['within']}x, mix {w['mix']}x, ex computers {w['exComputers']}x")
    print(f"Labor force {out['laborForce']['years'][-1]}: {out['laborForce']['millions'][-1]}M")
    print(f"Robot imports: {len(out['robots']['imports'])} years; ACES {[r['manufacturing'] for r in out['robots']['aces']]}")
    print(f'Wrote {OUT}')


if __name__ == '__main__':
    sys.exit(main())
