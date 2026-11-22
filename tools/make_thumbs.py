# 완성 모델 썸네일 만들기: tools/thumb.html을 헤드리스로 열고 .mpd마다 webp 저장.
# 부품 라이브러리 요청은 /tmp/ml/partcache 디스크 캐시로 응답(없으면 받아서 저장).
# 사용: python3 tools/make_thumbs.py <출력폴더> <파일...>   (SHARD/NSHARD 환경변수로 나눠 돌리기)
import asyncio, base64, json, functools, http.server, os, sys, threading, time, urllib.request
from playwright.async_api import async_playwright
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
T3 = '/tmp/t3/node_modules/three/'
CACHE = '/tmp/ml/libcache'; os.makedirs(CACHE, exist_ok=True)
SHARD = int(os.environ.get('SHARD', '0')); NSH = int(os.environ.get('NSHARD', '1')); PORT = 8850 + SHARD


class Q(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a): pass


def lib_get(url):
    rest = url.split('/ldraw/', 1)[1] if '/ldraw/' in url else ''
    if not rest or rest.endswith('/'): return 404, b''
    key = os.path.join(CACHE, rest.replace('/', '__'))
    if os.path.exists(key):
        b = open(key, 'rb').read()
        return (404, b'') if b == b'__404__' else (200, b)
    try:
        b = urllib.request.urlopen(url, timeout=30).read(); open(key, 'wb').write(b); return 200, b
    except urllib.error.HTTPError as e:
        if e.code == 404: open(key, 'wb').write(b'__404__')
        return e.code, b''
    except Exception:
        return 503, b''


async def main(out, files):
    srv = http.server.ThreadingHTTPServer(('127.0.0.1', PORT), functools.partial(Q, directory=ROOT))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    os.makedirs(out, exist_ok=True)
    files = [f for i, f in enumerate(sorted(files)) if i % NSH == SHARD]
    async with async_playwright() as p:
        b = await p.chromium.launch(executable_path='/usr/bin/google-chrome', args=['--use-gl=angle', '--use-angle=swiftshader', '--enable-unsafe-swiftshader'])
        pg = None

        async def fresh():
            nonlocal pg
            if pg: await pg.close()
            pg = await b.new_page(viewport={'width': 480, 'height': 360})
            async def r_cdn(r):
                u = r.request.url
                if 'three@0.170.0/' in u: await r.fulfill(path=T3 + u.split('three@0.170.0/')[1], content_type='application/javascript')
                else: await r.abort()
            async def r_lib(r):
                st, body = await asyncio.to_thread(lib_get, r.request.url)
                await r.fulfill(status=st, body=body, headers={'access-control-allow-origin': '*'})
            await pg.route('https://cdn.jsdelivr.net/**', r_cdn)
            await pg.route('https://raw.githubusercontent.com/**', r_lib)
            await pg.goto(f'http://127.0.0.1:{PORT}/tools/thumb.html')
            await pg.wait_for_function('window.ready', timeout=60000)
        await fresh()
        for f in files:
            name = os.path.basename(f).rsplit('.', 1)[0]
            dst = os.path.join(out, name + '.webp')
            if os.path.exists(dst): continue
            t0 = time.time()
            try:
                text = open(f, encoding='utf-8', errors='replace').read()
                r = await asyncio.wait_for(pg.evaluate('t => renderModel(t)', text), timeout=int(os.environ.get('TMO', '240')))
                open(dst, 'wb').write(base64.b64decode(r['url'].split(',', 1)[1]))
                open(os.path.join(out, name + '.json'), 'w').write(json.dumps({'parts': r['parts'], 'steps': r['steps']}))
                print('ok', name, r['parts'], r['steps'], f'{time.time() - t0:.1f}s', flush=True)
            except Exception as e:
                print('FAIL', name, str(e)[:100], flush=True)
                await fresh()
        await b.close()

if __name__ == '__main__':
    asyncio.run(main(sys.argv[1], sys.argv[2:]))
