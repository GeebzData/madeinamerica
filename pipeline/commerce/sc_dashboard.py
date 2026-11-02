"""Read S.C. Commerce's public recruitment dashboard (Power BI) in headless Chrome, as a visitor would.

Year totals:  sc_dashboard.py URL run START END OUT.json        one page snapshot per year
County totals: sc_dashboard.py URL counties START END OUT.json [BATCH] [COUNTY]
               sets the Year range, then picks each county in the County filter and saves the page text.
               Resumes from OUT.json; a fresh run every BATCH counties avoids a filter that stops responding.
URL is the report link embedded on https://www.sccommerce.com/state-economy/project-recruitment-data.
Needs Google Chrome and the websocket-client package. Output feeds build_commerce_counties.py.
"""
import json, subprocess, sys, tempfile, time, urllib.request
import websocket

CHROME = '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'
URL = sys.argv[1]
proc = subprocess.Popen([CHROME, '--headless=new', '--disable-gpu', '--remote-debugging-port=9334',
                         f'--user-data-dir={tempfile.mkdtemp()}', 'about:blank'],
                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
try:
    for _ in range(50):
        try:
            page = next(t for t in json.load(urllib.request.urlopen('http://127.0.0.1:9334/json')) if t['type'] == 'page')
            break
        except Exception:
            time.sleep(0.2)
    ws = websocket.create_connection(page['webSocketDebuggerUrl'], timeout=60)
    n = [0]

    def call(method, **params):
        n[0] += 1
        ws.send(json.dumps({'id': n[0], 'method': method, 'params': params}))
        while True:
            msg = json.loads(ws.recv())
            if msg.get('id') == n[0]:
                return msg.get('result', {})

    def ev(js):
        return call('Runtime.evaluate', expression=js, returnByValue=True, awaitPromise=True).get('result', {}).get('value')

    def click(x, y):
        for t in ('mousePressed', 'mouseReleased'):
            call('Input.dispatchMouseEvent', type=t, x=x, y=y, button='left', clickCount=1)

    call('Runtime.enable')
    call('Emulation.setDeviceMetricsOverride', width=1600, height=1000, deviceScaleFactor=1, mobile=False)
    call('Page.navigate', url=URL)
    time.sleep(22)
    mode = sys.argv[2] if len(sys.argv) > 2 else 'explore'
    find_year = """(() => { const els=[...document.querySelectorAll('.slicer-dropdown-menu, [aria-label]')].filter(e=>/^Year/.test((e.getAttribute('aria-label')||'').trim()) || e.classList.contains('slicer-dropdown-menu'));
      return els.map(e=>{const r=e.getBoundingClientRect();return [e.className.toString().slice(0,60), e.getAttribute('aria-label'), r.x+r.width/2, r.y+r.height/2, r.width, r.height]}) })()"""
    print(json.dumps(ev(find_year)))
    if mode == 'explore':
        print(json.dumps(ev("""[...document.querySelectorAll('input')].map(e=>{const r=e.getBoundingClientRect();return [e.type,e.value,e.getAttribute('aria-label'),e.className.toString().slice(0,50),r.x+r.width/2,r.y+r.height/2]})""")))
        sys.exit()
    def set_input(label, value):
        box = ev(f"""(() => {{const e=[...document.querySelectorAll('input.date-slicer-input')].find(e=>e.getAttribute('aria-label')=='{label}');const r=e.getBoundingClientRect();return [r.x+r.width/2,r.y+r.height/2]}})()""")
        click(*box)
        time.sleep(0.3)
        ev(f"""(() => {{const e=[...document.querySelectorAll('input.date-slicer-input')].find(e=>e.getAttribute('aria-label')=='{label}');e.select();}})()""")
        call('Input.insertText', text=str(value))
        for t in ('keyDown', 'keyUp'):
            call('Input.dispatchKeyEvent', type=t, key='Enter', code='Enter', windowsVirtualKeyCode=13)
        time.sleep(0.5)

    if mode == 'counties':
        set_input('End', int(sys.argv[4]))
        set_input('Start', int(sys.argv[3]))
        time.sleep(6)
        box = [b for b in ev(find_year) if b[1] == 'new_selectedcountyname'][0]
        click(box[2], box[3])
        time.sleep(3)
        items = ev("""[...document.querySelectorAll('.slicerItemContainer')].map(e=>{const r=e.getBoundingClientRect();return [e.innerText.trim(), e.getAttribute('aria-selected'), r.x+r.width/2, r.y+r.height/2]})""")
        SC = ['Abbeville','Aiken','Allendale','Anderson','Bamberg','Barnwell','Beaufort','Berkeley','Calhoun','Charleston','Cherokee','Chester','Chesterfield','Clarendon','Colleton','Darlington','Dillon','Dorchester','Edgefield','Fairfield','Florence','Georgetown','Greenville','Greenwood','Hampton','Horry','Jasper','Kershaw','Lancaster','Laurens','Lee','Lexington','McCormick','Marion','Marlboro','Newberry','Oconee','Orangeburg','Pickens','Richland','Saluda','Spartanburg','Sumter','Union','Williamsburg','York']
        import os, re as _re
        out = json.load(open(sys.argv[5])) if os.path.exists(sys.argv[5]) else {}
        good = lambda n: n in out and f'South Carolina • {n} • All Countries' in out[n]
        out = {k: v for k, v in out.items() if good(k)}
        def pick(name):
            for _ in range(4):
                if not ev("!!document.querySelector('.slicerItemContainer')"):
                    box = [b for b in ev(find_year) if b[1] == 'new_selectedcountyname'][0]
                    click(box[2], box[3])
                    time.sleep(2.5)
                sb = ev("""(() => {const e=[...document.querySelectorAll('input.searchInput')].find(e=>e.getBoundingClientRect().width>0);if(!e) return null;const r=e.getBoundingClientRect();return [r.x+r.width/2,r.y+r.height/2]})()""")
                if sb:
                    break
                call('Input.dispatchKeyEvent', type='keyDown', key='Escape', code='Escape', windowsVirtualKeyCode=27)
                time.sleep(1.5)
            sb = ev("""(() => {const e=[...document.querySelectorAll('input.searchInput')].find(e=>e.getBoundingClientRect().width>0);if(!e) return null;const r=e.getBoundingClientRect();return [r.x+r.width/2,r.y+r.height/2]})()""")
            click(*sb)
            ev("""(() => {const e=[...document.querySelectorAll('input.searchInput')].find(e=>e.getBoundingClientRect().width>0);e.select();})()""")
            for ch in name:
                call('Input.dispatchKeyEvent', type='keyDown', key=ch, text=ch)
                call('Input.dispatchKeyEvent', type='keyUp', key=ch)
                time.sleep(0.05)
            time.sleep(2.5)
            item = ev(f"""(() => {{const e=[...document.querySelectorAll('.slicerItemContainer')].find(e=>e.innerText.trim()=={json.dumps(name)});if(!e) return null;const r=e.getBoundingClientRect();return [r.x+r.width/2,r.y+r.height/2]}})()""")
            if item:
                click(*item)
            return bool(item)

        prev = None
        todo = [c for c in SC if not good(c)][:int(sys.argv[6]) if len(sys.argv) > 6 else None]
        if len(sys.argv) > 7:
            todo = [sys.argv[7]]
        print('todo', len(todo), file=sys.stderr)
        for name in todo:
            if prev:
                pick(prev)
            if not pick(name):
                print(name, 'not found', file=sys.stderr)
                prev = None
                continue
            prev = name
            time.sleep(7)
            out[name] = ev("document.body.innerText")
            hdr = out[name].split('Announcements')[1][:120].replace(chr(10), ' ')
            print(name, hdr, file=sys.stderr)
            json.dump(out, open(sys.argv[5], 'w'))
        json.dump(out, open(sys.argv[5], 'w'))
        sys.exit()
    out = {}
finally:
    proc.terminate()
