"""갤러리 데이터 만들기 (OMR 세트 → sets/)

1) extract: 브라우저로 받은 묶음 파일(omr_all_XX.json.gz, 또는 예전 omr_bundle.json)을 풀어서
            /tmp/ml/gal/src/<id>.mpd + /tmp/ml/gal/meta.json
2) (따로) python3 tools/make_thumbs.py /tmp/ml/gal/thumbs /tmp/ml/gal/src/*.mpd   → 썸네일 + 부품·단계 수
3) assemble: sets/m/<id>.mpd.gz, sets/t/<id>.webp, sets/catalog.json

사용: python3 tools/build_catalog.py extract <묶음 파일...>
      python3 tools/build_catalog.py assemble
"""
import gzip, json, os, re, shutil, sys

WORK = '/tmp/ml/gal'
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, 'sets')


def safe(s):
    return re.sub(r'[^A-Za-z0-9._-]+', '_', s).strip('_')


def model_label(set_id, file):
    stem = re.sub(r'\.(mpd|ldr)$', '', file, flags=re.I)
    rest = stem[len(set_id):].lstrip('_- ') if stem.lower().startswith(set_id.lower()) else stem
    return rest.replace('-', ' ').replace('_', ' ').strip() or '기본 모델'


def author_of(text):
    m = re.search(r'^0 Author:\s*(.+?)\s*$', text, re.M)
    if not m: return ''
    return re.sub(r'\s*\[[^\]]*\]\s*$', '', m.group(1)).strip()


def read_bundle(path):
    raw = open(path, 'rb').read()
    if raw[:2] == b'\x1f\x8b': raw = gzip.decompress(raw)
    d = json.loads(raw)
    sets = {}
    for k, v in d.items():
        if 'models' in v:                      # 새 형식: 세트 → 모델들
            sets[v['set']] = v
        else:                                   # 예전 omr_bundle.json: "세트__파일" → text
            sid, file = k.split('__', 1)
            s = sets.setdefault(sid, {'set': sid, 'name': v['name'], 'theme': v['theme'], 'year': v['year'], 'models': []})
            s['models'].append({'file': file, 'text': v['text']})
    return sets


def extract(paths):
    os.makedirs(os.path.join(WORK, 'src'), exist_ok=True)
    meta_path = os.path.join(WORK, 'meta.json')
    meta = json.load(open(meta_path)) if os.path.exists(meta_path) else {}
    for p in paths:
        for sid, s in read_bundle(p).items():
            theme = [t.strip() for t in (s.get('theme') or '').split('>')]
            models = []
            for i, m in enumerate(s['models']):
                mid = safe(f"{sid}" if i == 0 else f"{sid}_{i}")
                # 'FILE 이름 ' 끝 공백 때문에 하위 모델을 못 찾는 파일이 있어서 정리
                text = re.sub(r'^(0 FILE .*?)[ \t]+(\r?)$', r'\1\2', m['text'], flags=re.M)
                open(os.path.join(WORK, 'src', mid + '.mpd'), 'w', encoding='utf-8', newline='').write(text)
                models.append({'id': mid, 'label': '기본 모델' if i == 0 else model_label(sid, m['file']),
                               'file': m['file'], 'author': author_of(m['text'])})
            meta[sid] = {'id': sid, 'name': s['name'], 'theme': theme[0], 'sub': theme[1] if len(theme) > 1 else '',
                         'year': s.get('year', ''), 'models': models}
        print(p, '→ 누적 세트', len(meta), flush=True)
    json.dump(meta, open(meta_path, 'w'), ensure_ascii=False)


def assemble():
    meta = json.load(open(os.path.join(WORK, 'meta.json')))
    # select.json이 있으면 그 세트만 (난이도별로 고르게 1,000세트 — 2026-11-22 결정)
    sel_path = os.path.join(WORK, 'select.json')
    if os.path.exists(sel_path):
        keep = set(json.load(open(sel_path))); meta = {k: v for k, v in meta.items() if k in keep}
    shutil.rmtree(OUT, ignore_errors=True)
    os.makedirs(os.path.join(OUT, 'm'), exist_ok=True); os.makedirs(os.path.join(OUT, 't'), exist_ok=True)
    cat, skipped = [], 0
    for sid in sorted(meta, key=lambda x: [int(t) if t.isdigit() else t for t in re.split(r'(\d+)', x)]):
        s = meta[sid]; models = []
        for m in s['models']:
            th = os.path.join(WORK, 'thumbs', m['id'] + '.webp'); info = os.path.join(WORK, 'thumbs', m['id'] + '.json')
            if not (os.path.exists(th) and os.path.exists(info)): skipped += 1; continue   # 렌더링 실패 = 앱에서도 못 여는 파일
            pi = json.load(open(info))
            if pi['parts'] == 0: skipped += 1; continue
            src = open(os.path.join(WORK, 'src', m['id'] + '.mpd'), 'rb').read()
            with gzip.open(os.path.join(OUT, 'm', m['id'] + '.mpd.gz'), 'wb', compresslevel=9) as f: f.write(src)
            shutil.copy(th, os.path.join(OUT, 't', m['id'] + '.webp'))
            models.append({'id': m['id'], 'label': m['label'], 'author': m['author'], 'parts': pi['parts'], 'steps': pi['steps']})
        if models:
            cat.append({'id': sid, 'name': s['name'], 'theme': s['theme'], 'sub': s['sub'], 'year': s['year'], 'models': models})
    json.dump(cat, open(os.path.join(OUT, 'catalog.json'), 'w'), ensure_ascii=False, separators=(',', ':'))
    size = sum(os.path.getsize(os.path.join(dp, f)) for dp, _, fs in os.walk(OUT) for f in fs)
    print(f'세트 {len(cat)}개, 모델 {sum(len(c["models"]) for c in cat)}개, 빠진 모델 {skipped}개, sets/ {size / 1e6:.1f}MB')


if __name__ == '__main__':
    {'extract': lambda: extract(sys.argv[2:]), 'assemble': assemble}[sys.argv[1]]()
