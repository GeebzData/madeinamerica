"""Run Kentucky's Location and Expansion Search for a date range in headless Chrome and save the results table.

ky_search.py FROM TO OUT.json   e.g. 2025-01-01 2025-12-31 ../raw/commerce/ky_2025.json
Ticks all 120 counties (the form requires a county), submits, and saves the header, rows and summary text.
Needs Google Chrome and the websocket-client package. Output feeds build_commerce_counties.py.
"""
import json, subprocess, sys, tempfile, time, urllib.request
import websocket
CHROME = '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'
proc = subprocess.Popen([CHROME, '--headless=new', '--disable-gpu', '--remote-debugging-port=9336',
                         f'--user-data-dir={tempfile.mkdtemp()}', 'about:blank'],
                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
try:
    for _ in range(50):
        try:
            page = next(t for t in json.load(urllib.request.urlopen('http://127.0.0.1:9336/json')) if t['type'] == 'page')
            break
        except Exception:
            time.sleep(0.2)
    ws = websocket.create_connection(page['webSocketDebuggerUrl'], timeout=120)
    n = [0]
    def call(method, **params):
        n[0] += 1
        ws.send(json.dumps({'id': n[0], 'method': method, 'params': params}))
        while True:
            msg = json.loads(ws.recv())
            if msg.get('id') == n[0]:
                return msg.get('result', {})
    ev = lambda js: call('Runtime.evaluate', expression=js, returnByValue=True, awaitPromise=True).get('result', {}).get('value')
    call('Page.navigate', url='https://locationexpansionsearch.ced.ky.gov/SearchCriteria')
    time.sleep(5)
    ev(f"""document.querySelector('[name="searchCriteria.AnnouncementDateFrom"]').value='{sys.argv[1]}';
           document.querySelector('[name="searchCriteria.AnnouncementDateTo"]').value='{sys.argv[2]}';
           document.querySelectorAll('[name="searchCriteria.selectedCounties"]').forEach(c => c.checked = true);
           document.querySelector('form button[type=submit]').click();""")
    time.sleep(20)
    out = ev("""({url: location.href, text: document.body.innerText.slice(0, 2000),
                 heads: [...document.querySelectorAll('table th')].map(e=>e.innerText.trim()),
                 rows: [...document.querySelectorAll('table tbody tr')].map(tr=>[...tr.children].map(td=>td.innerText.trim()))})""")
    json.dump(out, open(sys.argv[3], 'w'))
    print(out['url'], len(out['rows']), 'rows', out['heads'])
    print(out['text'][:800])
finally:
    proc.terminate()
