"""앱(JS)의 AI 순서가 파이썬(ml/model.json 트리로 직접 계산)과 같은지 확인.
1) model.json 트리 계산 == sklearn 결과 (export 직후 확인용, 여기선 트리 직접 사용)
2) 같은 상자·같은 규칙 단계로 탐욕 순서를 파이썬에서 만들고, 앱을 헤드리스로 열어 state.aiOrderIdx와 비교
사용: USE_RULE=1 python3 ml/parity.py <모델 이름 일부> ...
"""
import os, sys, json, glob, re, asyncio, functools, http.server, threading, time
os.environ['USE_RULE'] = '1'
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from order import load
from next import prepare, state_features
from playwright.async_api import async_playwright

HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
M = json.load(open(os.path.join(HERE, 'model.json')))


def score(X):
    out = np.full(len(X), M['base'])
    for t in M['trees']:
        for r, x in enumerate(X):
            nd = t[0]
            while len(nd) > 1:
                nd = t[nd[2]] if x[nd[0]] <= nd[1] else t[nd[3]]
            out[r] += nd[0]
    return out


def py_order(m, color):
    n = len(m['truth']); placed = np.zeros(n, bool); last = np.array([], int); order = []
    while len(order) < n:
        cand = np.where(~placed)[0]
        s = score(state_features(m, placed, last, cand, color))
        i = cand[int(np.argmax(s))]; order.append(int(i)); placed[i] = True; last = np.array([i])
    return order


class Q(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a): pass


async def js_orders(names):
    srv = http.server.ThreadingHTTPServer(('127.0.0.1', 8830), functools.partial(Q, directory=ROOT))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    out = {}
    async with async_playwright() as p:
        b = await p.chromium.launch(executable_path='/usr/bin/google-chrome', args=['--use-gl=angle', '--use-angle=swiftshader', '--enable-unsafe-swiftshader'])
        ctx = await b.new_context(viewport={'width': 800, 'height': 600})
        await ctx.add_init_script("localStorage.setItem('lah:guideSeen','1')")
        pg = await ctx.new_page()
        T3 = '/tmp/t3/node_modules/three/'
        async def route(r):
            u = r.request.url
            if 'three@0.170.0/' in u: await r.fulfill(path=T3 + u.split('three@0.170.0/')[1], content_type='application/javascript')
            else: await r.abort()
        await pg.route('https://cdn.jsdelivr.net/**', route)
        await pg.goto('http://127.0.0.1:8830/index.html?sample=samples/car.mpd')
        await pg.wait_for_function("window.__app && __app.state.steps.length>0", timeout=120000)
        for name in names:
            f = glob.glob(f'/tmp/ml/raw/{name}*.mpd')[0]
            text = re.sub(r'^0 (STEP|ROTSTEP).*$', '', open(f, encoding='utf-8', errors='replace').read(), flags=re.M)
            await pg.evaluate("()=>{__app.state.steps=[]; __app.state.aiOrderIdx=null}")
            await pg.evaluate("([t,l])=>__app.loadFromText(t,l)", [text, name])
            await pg.wait_for_function("__app.state.steps.length>0 && !document.getElementById('overlay').classList.contains('on')", timeout=600000)
            out[name] = await pg.evaluate("({order:__app.state.aiOrderIdx, ms:__app.state.aiMs, ai:__app.state.aiSplit, steps:__app.state.steps.length, info:document.getElementById('modelInfo')?.textContent})")
        await b.close()
    return out


def main(names):
    models = load(); files = sorted(glob.glob(os.path.join(HERE, 'feat', '*.json')))
    js = asyncio.run(js_orders(names))
    for name in names:
        k = [i for i, f in enumerate(files) if os.path.basename(f).startswith(name)][0]
        m = models[k]; prepare(m)
        color = np.array([b['color'] for b in json.load(open(files[k]))['bricks']])
        t0 = time.time(); po = py_order(m, color); t1 = time.time()
        jo = js[name]['order'] or []
        same = sum(1 for a, b in zip(po, jo) if a == b)
        first = next((i for i, (a, b) in enumerate(zip(po, jo)) if a != b), None)
        print(f"{name}: 부품 {len(po)} | JS {js[name]['ms']}ms, 단계 {js[name]['steps']}, AI={js[name]['ai']} | 같은 위치 {same}/{len(po)}, 처음 다른 곳 {first} | {js[name]['info']}")


if __name__ == '__main__':
    main(sys.argv[1:])
