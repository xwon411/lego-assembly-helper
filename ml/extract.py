# 앱(index.html)을 헤드리스로 열어 모델별 부품 정보 덤프:
#  - 원본(STEP 있음): 정답 단계
#  - STEP 줄 제거본: 지금 앱 규칙 방식(층별·근접 묶음)의 단계  → 비교 기준
import asyncio, functools, http.server, threading, json, glob, os, re, sys
from playwright.async_api import async_playwright
ROOT='/home/claude/lego-assembly-helper'; T3='/tmp/t3/node_modules/three/'
class Q(http.server.SimpleHTTPRequestHandler):
    def log_message(self,*a): pass
srv=http.server.ThreadingHTTPServer(('127.0.0.1',8820), functools.partial(Q, directory=ROOT))
threading.Thread(target=srv.serve_forever,daemon=True).start()
DUMP='''(()=>{const s=__app.state; return s.bricks.map(b=>{const i=s.info.get(b); const bx=i.box;
  return {part:i.partId, color:String(i.colorCode), min:bx.min.toArray().map(v=>+v.toFixed(2)), max:bx.max.toArray().map(v=>+v.toFixed(2)), step:s.stepOf.get(b)}})})()'''
async def load(pg, text, label):
    await pg.evaluate("([t,l])=>{ window.__done=false; __app.state.steps=[]; }", [text,label])
    await pg.evaluate("([t,l])=>__app.loadFromText(t,l)", [text,label])
    await pg.wait_for_function("__app.state.steps.length>0 && !document.getElementById('overlay').classList.contains('on')", timeout=600000)
    return await pg.evaluate(DUMP)
async def main():
    async with async_playwright() as p:
        b=await p.chromium.launch(executable_path='/usr/bin/google-chrome', args=['--use-gl=angle','--use-angle=swiftshader','--enable-unsafe-swiftshader'])
        async def route(r):
            u=r.request.url
            if 'three@0.170.0/' in u: await r.fulfill(path=T3+u.split('three@0.170.0/')[1], content_type='application/javascript')
            else: await r.abort()
        ctx=await b.new_context(viewport={'width':800,'height':600}); await ctx.add_init_script("localStorage.setItem('lah:guideSeen','1')")
        pg=await ctx.new_page(); errs=[]; pg.on('pageerror', lambda e: errs.append(str(e)[:200]))
        await pg.route('https://cdn.jsdelivr.net/**', route)
        await pg.goto('http://127.0.0.1:8820/index.html?sample=samples/car.mpd')
        await pg.wait_for_function("window.__app && __app.state.steps.length>0", timeout=120000)
        for f in sorted(glob.glob('/tmp/ml/raw/*.mpd')):
            name=os.path.basename(f).split('.')[0]
            out=os.path.join(os.path.dirname(os.path.abspath(__file__)), 'feat', f'{name}.json')
            if os.path.exists(out): continue
            text=open(f,encoding='utf-8',errors='replace').read()
            truth=await load(pg,text,name)
            nostep=re.sub(r'^0 (STEP|ROTSTEP).*$','',text,flags=re.M)
            heur=await load(pg,nostep,name+'-nostep')
            same = len(truth)==len(heur) and all(a['part']==b['part'] and a['min']==b['min'] for a,b in zip(truth,heur))
            for a,b2 in zip(truth,heur): a['heur']=b2['step']
            json.dump({'name':name,'bricks':truth,'aligned':same}, open(out,'w'))
            print(name, 'bricks',len(truth),'truth steps',len(set(x['step'] for x in truth)),'heur steps',len(set(x['heur'] for x in truth)),'aligned',same, flush=True)
        print('errors',errs)
        await b.close()
asyncio.run(main())
