# OMR .mpd(부품 미포함)을 부품까지 넣은 packed .mpd로 만든다.
# 부품 파일은 gkjohnson/ldraw-parts-library 미러에서 받아 /tmp/ml/partcache에 캐시.
# 사용: python3 ml/pack.py <입력.mpd ...>  → /tmp/ml/raw/<이름>_Packed.mpd
import os, re, sys, urllib.request, urllib.parse
BASE = 'https://raw.githubusercontent.com/gkjohnson/ldraw-parts-library/master/complete/ldraw/'
CACHE = '/tmp/ml/partcache'; os.makedirs(CACHE, exist_ok=True)
MISS = set()

def fetch_part(name):
    n = name.replace('\\', '/').lower()
    key = os.path.join(CACHE, n.replace('/', '__'))
    if os.path.exists(key):
        t = open(key, encoding='utf-8', errors='replace').read()
        return None if t == '__MISSING__' else t
    cands = [f'parts/{n}', f'p/{n}'] if '/' not in n or n.startswith('s/') or n.startswith('48/') or n.startswith('8/') else [f'parts/{n}', f'p/{n}']
    if n.startswith('48/') or n.startswith('8/'): cands = [f'p/{n}']
    for c in cands:
        try:
            t = urllib.request.urlopen(BASE + urllib.parse.quote(c), timeout=30).read().decode('utf-8', 'replace')
            open(key, 'w').write(t); return t
        except Exception:
            pass
    open(key, 'w').write('__MISSING__'); return None

def refs(text):
    out = []
    for l in text.splitlines():
        p = l.split()
        if len(p) >= 15 and p[0] == '1':
            out.append(' '.join(p[14:]))
    return out

def pack(path):
    text = open(path, encoding='utf-8', errors='replace').read().replace('\r\n', '\n')
    local = {m.group(1).strip().lower() for m in re.finditer(r'^0 FILE (.+)$', text, re.M)}
    if not local:  # 단일 .ldr
        local = {os.path.basename(path).lower()}
    seen, out, queue = set(), [], [r for r in refs(text)]
    while queue:
        r = queue.pop()
        k = r.replace('\\', '/').lower()
        if k in local or k in seen: continue
        seen.add(k)
        t = fetch_part(r)
        if t is None: MISS.add(k); continue
        out.append(f'0 FILE {r}\n{t.strip()}\n')
        queue.extend(refs(t))
    body = text if text.lstrip().startswith('0 FILE') else f'0 FILE {os.path.basename(path)}\n{text}'
    return body.rstrip() + '\n\n' + '\n'.join(out)

if __name__ == '__main__':
    for p in sys.argv[1:]:
        name = os.path.basename(p).rsplit('.', 1)[0]
        dst = f'/tmp/ml/raw/{name}_Packed.mpd'
        if os.path.exists(dst): continue
        open(dst, 'w').write(pack(p))
        print('packed', name, 'missing so far:', len(MISS), flush=True)
    if MISS: print('MISSING', sorted(MISS)[:50])
