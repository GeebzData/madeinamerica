"""Checks that announcement job counts cannot be investment dollars.

Run from the repo root: python3 pipeline/test_announcements.py
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from fetch_alcommerce import JOB_CAP, recompute_manufacturing, sanitize_project, validate_projects

OUT = Path(__file__).resolve().parent.parent / 'site' / 'data' / 'announcements.json'


def check(name, cond):
    if not cond:
        raise SystemExit(f'FAIL {name}')
    print(f'ok {name}')


def test_known_swaps():
    foley = sanitize_project({
        'company': 'BC Foley, LLC Baldwin', 'naics': '713110',
        'jobs': 361_000_000, 'invest': 0, 'activity': 'Tourist Destination Facility 620 $',
    })
    check('foley jobs', foley['jobs'] == 620)
    check('foley invest', foley['invest'] == 361_000_000)
    check('foley activity', foley['activity'] == 'Tourist Destination Facility')

    hercules = sanitize_project({
        'company': 'Hercules Poly Eclectic', 'naics': '339920',
        'jobs': 4_000_000, 'invest': 0, 'activity': 'Playground Equipment 29',
    })
    check('hercules jobs', hercules['jobs'] == 29)
    check('hercules invest', hercules['invest'] == 4_000_000)

    cells = sanitize_project({
        'company': 'Alabama Fuel Cells Tallassee', 'naics': '336413',
        'jobs': 2_250_000, 'invest': 0, 'activity': 'Aviation Fuel Cells 26',
    })
    check('fuel cells jobs', cells['jobs'] == 26)
    check('fuel cells invest', cells['invest'] == 2_250_000)


def test_leaves_real_projects_alone():
    lilly = sanitize_project({
        'company': 'Eli Lilly Huntsville', 'naics': '325412',
        'jobs': 450, 'invest': 6_000_000_000, 'activity': 'Pharmaceutical Preparation Manufacturing',
    })
    check('lilly jobs', lilly['jobs'] == 450)
    check('lilly invest', lilly['invest'] == 6_000_000_000)
    check('lilly activity', lilly['activity'] == 'Pharmaceutical Preparation Manufacturing')


def test_pike_randolph_2020():
    data = json.loads(OUT.read_text())
    pike = data['counties']['01109']['2020']
    rand = data['counties']['01111']['2020']
    check('pike 2020 printed totals', pike[:3] == [2, 86, 29_273_303])
    check('pike 2020 manufacturing is Golden Boy only', pike[3:] == [1, 67, 13_273_303])
    check('randolph 2020 totals', rand == [3, 94, 27_135_066, 3, 94, 27_135_066])
    filed = [p for p in data['projects'] if p['year'] == 2020 and p['county'] == '01109']
    check('pike 2020 project count', len(filed) == 2)
    check('no randolph project left in pike', all('Randolph ' not in p['company'] for p in filed))
    moved = [p for p in data['projects'] if p['year'] == 2020 and p['county'] == '01111']
    check('randolph holds the three plants', {p['company'] for p in moved} >= {'OMM Timber Wadley', 'JELD-WEN Wedowee', 'SteelFab, Inc. Alabama Division Roanoke'})


def test_published_file():
    data = json.loads(OUT.read_text())
    validate_projects(data['projects'])
    check('no project over the cap', all(p['jobs'] < JOB_CAP for p in data['projects']))
    # Elmore 2019 is the two manufacturing rows whose dollars had been counted as jobs.
    elmore = data['counties']['01051']['2019']
    check('elmore printed jobs', elmore[1] == 55)
    check('elmore manufacturing jobs', elmore[4] == 55)
    check('elmore manufacturing investment', elmore[5] == 6_250_000)
    check('2019 state manufacturing jobs', data['state']['2019'][4] < JOB_CAP)
    # Baldwin 2016 printed totals already matched jobs of 961 once Foley is 620, not 361 million.
    baldwin = [p for p in data['projects'] if p['company'].startswith('BC Foley')]
    check('foley stored', len(baldwin) == 1 and baldwin[0]['jobs'] == 620 and baldwin[0]['invest'] == 361_000_000)


def test_recompute_uses_corrected_jobs():
    out = {
        'years': [2019],
        'counties': {'01051': {'2019': [2, 55, 6_250_000, 2, 6_250_000, 0]}},
        'state': {},
        'projects': [
            {'year': 2019, 'county': '01051', 'naics': '339920', 'jobs': 29, 'invest': 4_000_000},
            {'year': 2019, 'county': '01051', 'naics': '336413', 'jobs': 26, 'invest': 2_250_000},
        ],
    }
    recompute_manufacturing(out)
    check('recompute county jobs', out['counties']['01051']['2019'][4] == 55)
    check('recompute keeps printed jobs', out['counties']['01051']['2019'][1] == 55)
    check('recompute state', out['state']['2019'][4] == 55 and out['state']['2019'][5] == 6_250_000)


if __name__ == '__main__':
    test_known_swaps()
    test_leaves_real_projects_alone()
    test_recompute_uses_corrected_jobs()
    test_pike_randolph_2020()
    test_published_file()
    print('all announcement checks passed')
