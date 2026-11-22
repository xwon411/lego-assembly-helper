"""스모크 테스트: 샘플 4종을 열어 단계 수·콘솔 에러를 확인하고 스크린샷을 남긴다.

준비:
  npm i --prefix /tmp/t3 three@0.170.0
  pip install playwright && python -m playwright install chromium
실행 (저장소 루트에서):
  python3 tests/smoke.py            # 스크린샷은 tests/out/
환경변수:
  CHROME=/usr/bin/google-chrome     # 시스템 Chrome을 쓸 때 (없으면 Playwright 내장 Chromium)
  THREE_DIR=/tmp/t3/node_modules/three/
"""
import asyncio, functools, http.server, json, os, pathlib, threading, sys
from playwright.async_api import async_playwright

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = ROOT / 'tests' / 'out'
THREE = os.environ.get('THREE_DIR', '/tmp/t3/node_modules/three/')
PORT = 8765

EXPECT = {  # 샘플별 기대 단계 수
    'samples/car.mpd': 8,
    'samples/mini-construction.mpd': 40,
    'samples/lighthouse.mpd': 13,   # STEP 없음 → AI 순서 (규칙 방식이면 12)
}
READY = "window.__app && __app.state.steps.length>0 && !document.getElementById('overlay').classList.contains('on')"


class Quiet(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a):
        pass


async def main():
    srv = http.server.ThreadingHTTPServer(('127.0.0.1', PORT), functools.partial(Quiet, directory=str(ROOT)))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    OUT.mkdir(parents=True, exist_ok=True)
    failed = False
    async with async_playwright() as p:
        kw = {'args': ['--use-gl=angle', '--use-angle=swiftshader', '--enable-unsafe-swiftshader']}
        if os.environ.get('CHROME'):
            kw['executable_path'] = os.environ['CHROME']
        if os.environ.get('HTTPS_PROXY'):
            kw['proxy'] = {'server': os.environ['HTTPS_PROXY'], 'bypass': '127.0.0.1'}
        browser = await p.chromium.launch(**kw)

        async def three(route):
            url = route.request.url
            if 'three@0.170.0/' in url:
                await route.fulfill(path=THREE + url.split('three@0.170.0/')[1], content_type='application/javascript')
            else:
                await route.abort()  # 글꼴 등 다른 CDN 파일은 테스트에서 생략 (시스템 글꼴로 표시)

        for vp_name, vp in [('desk', (1280, 800)), ('phone', (390, 844))]:
            for sample, steps in EXPECT.items():
                ctx = await browser.new_context(viewport={'width': vp[0], 'height': vp[1]}, ignore_https_errors=True)
                await ctx.add_init_script("localStorage.setItem('lah:guideSeen','1')")
                page = await ctx.new_page()
                errs = []
                page.on('pageerror', lambda e: errs.append(str(e)))
                await page.route('https://cdn.jsdelivr.net/**', three)
                await page.goto(f'http://127.0.0.1:{PORT}/index.html?sample={sample}')
                await page.wait_for_function(READY, timeout=120000)
                n = await page.evaluate('__app.state.steps.length')
                for _ in range(3):
                    await page.click('#bNext')
                    await page.wait_for_timeout(150)
                await page.wait_for_timeout(1500)
                name = f"{vp_name}_{pathlib.Path(sample).stem}"
                await page.screenshot(path=str(OUT / f'{name}.png'))
                info = await page.inner_text('#modelInfo')
                ok = n == steps and not errs
                failed |= not ok
                print(('OK  ' if ok else 'FAIL'), name, json.dumps({'steps': n, 'expected': steps, 'info': info, 'errors': errs}, ensure_ascii=False))
                await ctx.close()
        await browser.close()
    sys.exit(1 if failed else 0)


asyncio.run(main())
