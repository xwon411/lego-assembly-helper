# 세트 갤러리 테스트: 첫 화면 갤러리 → 테마·난이도·검색 필터 → 세트 열기 → 다시 열기/Esc → ?set= 링크
# 부품 라이브러리 요청은 tools/make_thumbs.py의 디스크 캐시로 응답. 사용: python3 tests/gallery.py (Lakeside Lodge·McLaren Senna가 catalog에 있어야 함)
import asyncio, functools, http.server, threading, json
from playwright.async_api import async_playwright
ROOT=__import__('os').path.dirname(__import__('os').path.dirname(__import__('os').path.abspath(__file__))); T3='/tmp/t3/node_modules/three/'
class Q(http.server.SimpleHTTPRequestHandler):
    def log_message(self,*a): pass
srv=http.server.ThreadingHTTPServer(('127.0.0.1',8870), functools.partial(Q, directory=ROOT)); threading.Thread(target=srv.serve_forever,daemon=True).start()
import sys; sys.path.insert(0, ROOT+'/tools'); from make_thumbs import lib_get
async def main():
    async with async_playwright() as p:
        b=await p.chromium.launch(executable_path='/usr/bin/google-chrome', args=['--use-gl=angle','--use-angle=swiftshader','--enable-unsafe-swiftshader'])
        ctx=await b.new_context(viewport={'width':1280,'height':800})
        pg=await ctx.new_page(); errs=[]
        pg.on('pageerror', lambda e: errs.append(str(e)[:200])); pg.on('console', lambda m: m.type=='error' and 'Failed to load resource' not in m.text and errs.append(m.text[:200]))
        async def r_cdn(r):
            u=r.request.url
            if 'three@0.170.0/' in u: await r.fulfill(path=T3+u.split('three@0.170.0/')[1], content_type='application/javascript')
            else: await r.abort()
        async def r_lib(r):
            st, body = await asyncio.to_thread(lib_get, r.request.url)
            await r.fulfill(status=st, body=body, headers={'access-control-allow-origin':'*'})
        await pg.route('https://cdn.jsdelivr.net/**', r_cdn); await pg.route('https://raw.githubusercontent.com/**', r_lib)
        await pg.goto('http://127.0.0.1:8870/index.html'); await pg.wait_for_timeout(2500)
        print('count:', await pg.text_content('#gCount'), 'guide shown:', await pg.evaluate("document.getElementById('guide').classList.contains('on')"))
        await pg.screenshot(path='/tmp/gallery_1.png')
        await pg.click('.g-theme[data-theme="Brickheadz"]'); await pg.wait_for_timeout(300); print('brickheadz:', await pg.text_content('#gCount'))
        await pg.click('.g-theme[data-theme="전체"]'); await pg.click('.g-chip[data-level="easy"]'); await pg.wait_for_timeout(300); print('easy:', await pg.text_content('#gCount'))
        await pg.click('.g-chip[data-level="easy"]'); await pg.fill('#gSearch','senna'); await pg.wait_for_timeout(300); print('search senna:', await pg.text_content('#gCount'))
        await pg.fill('#gSearch','zzzz'); await pg.wait_for_timeout(300); print('search none:', await pg.text_content('#gCount'), await pg.locator('.g-empty').count())
        await pg.fill('#gSearch','')
        await pg.click('.g-card:has-text("Lakeside Lodge")')
        await pg.wait_for_function("window.__app && __app.state.steps.length>0 && !document.getElementById('overlay').classList.contains('on')", timeout=300000)
        print('loaded:', await pg.text_content('#modelInfo'), '| url', pg.url, '| guide', await pg.evaluate("document.getElementById('guide').classList.contains('on')"))
        await pg.evaluate("document.getElementById('guide').classList.remove('on')")
        await pg.screenshot(path='/tmp/gallery_2.png')
        await pg.click('#bGallery'); await pg.wait_for_timeout(500); print('reopen, close visible:', await pg.is_visible('#gClose'))
        await pg.keyboard.press('Escape'); await pg.wait_for_timeout(300); print('esc closed:', not await pg.evaluate("document.getElementById('gallery').classList.contains('on')"))
        # 딥 링크
        pg2=await ctx.new_page(); await pg2.route('https://cdn.jsdelivr.net/**', r_cdn); await pg2.route('https://raw.githubusercontent.com/**', r_lib)
        await pg2.goto('http://127.0.0.1:8870/index.html?set=75892-1')
        await pg2.wait_for_function("window.__app && __app.state.steps.length>0 && !document.getElementById('overlay').classList.contains('on')", timeout=300000)
        print('deeplink:', await pg2.text_content('#modelInfo'))
        print('errors:', errs)
        await b.close()
asyncio.run(main())
