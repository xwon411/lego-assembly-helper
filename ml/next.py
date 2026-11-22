"""'다음 단계 부품' 예측 모델 (설명서 만드는 사람 흉내 내기).

상태 = 지금까지 조립한 부품 집합 S(+ 직전 단계 L). 남은 부품 p마다 "다음 단계에 들어가는가"를 분류.
학습: 정답 순서를 따라가며(teacher forcing) 단계 t마다 남은 부품 전체를 후보로, 정답 단계 부품 = 1.
생성: 빈 상태에서 시작해 점수가 가장 높은 부품을 하나씩 골라 붙임(탐욕적) → 전체 순서.
평가: (1) 생성한 순서의 쌍 정확도 (order.py와 같은 지표)
      (2) 다음 부품 적중률: 정답 접두사가 주어졌을 때 1순위 후보가 정답 다음 단계에 실제로 있는가
"""
import json, os, glob, sys
import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import HistGradientBoostingClassifier
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from order import load, relations, graph_hops, pair_acc

RNG = np.random.default_rng(0)


def prepare(m):
    mn, mx = m['mn'], m['mx']
    below, side, frac = relations(mn, mx)
    touch = below | below.T | side
    m['below'], m['touch'] = below, touch
    m['c'] = (mn + mx) / 2
    m['H'] = (mx[:, 1].max() - mn[:, 1].min()) + 1e-6
    m['W'] = np.linalg.norm(mx.max(0) - mn.min(0)) + 1e-6
    size = mx - mn
    m['area'] = np.log1p(size[:, 0] * size[:, 2])
    m['thick'] = np.log1p(size[:, 1])
    m['deg'] = np.log1p(touch.sum(1))
    hop, geo, isroot, dy, ady, csize = graph_hops(mn, mx, below, side)
    m['hop'], m['geo'], m['isroot'] = hop, geo, isroot
    # 같은 부품 종류 판정용 키 (모양 = 크기 반올림, 색은 따로)
    m['shape'] = np.array([hash(tuple(np.round(s, 0))) for s in size])
    from scipy.sparse.csgraph import connected_components
    m['comp'] = connected_components(touch.astype(float), directed=False)[1]


FEAT_NAMES = ['조립부와 닿음', '닿은 수(log)', '아래 받침 있음', '위에서 받쳐짐(뒤집기)', '직전 단계와 거리',
              '조립부와 거리', '조립부 대비 높이', '|조립부 대비 높이|', '직전 단계와 같은 모양', '직전 단계와 같은 모양·색',
              '면적(log)', '두께(log)', '연결 수(log)', '뿌리 홉', '뿌리 거리', '뿌리', '진행률', '아직 아무것도 없음',
              '직전 단계와 같은 덩어리', '직전 단계에 닿음', '덩어리 시작 전(덩어리 안 조립 0개)']
USE_RULE = os.environ.get('USE_RULE', '0') == '1'
if USE_RULE:
    FEAT_NAMES = FEAT_NAMES + ['규칙상 남은 것 중 맨 앞', '규칙 순서 차이']


def state_features(m, placed, last, cand, color):
    """placed: bool 배열(조립됨), last: 직전 단계 부품 인덱스, cand: 후보 인덱스"""
    n = len(placed)
    P = np.where(placed)[0]
    c = m['c']
    if len(P):
        t_S = m['touch'][np.ix_(cand, P)]
        touchS = t_S.sum(1)
        supp = m['below'][np.ix_(P, cand)].sum(0)        # 조립된 부품이 후보를 아래에서 받침
        hang = m['below'][np.ix_(cand, P)].sum(1)        # 후보가 조립된 부품 아래에 붙음
        dS = np.min(np.linalg.norm(c[cand][:, None] - c[P][None], axis=2), 1) / m['W']
        relh = (c[cand, 1] - c[P, 1].mean()) / m['H']
    else:
        touchS = supp = hang = np.zeros(len(cand)); dS = np.ones(len(cand)); relh = np.zeros(len(cand))
    if len(last):
        dL = np.min(np.linalg.norm(c[cand][:, None] - c[last][None], axis=2), 1) / m['W']
        same_shape = np.isin(m['shape'][cand], m['shape'][last]).astype(float)
        last_keys = set(zip(m['shape'][last], color[last]))
        same_sc = np.array([(m['shape'][i], color[i]) in last_keys for i in cand], float)
    else:
        dL = np.ones(len(cand)); same_shape = same_sc = np.zeros(len(cand))
    if len(last):
        same_comp = np.isin(m['comp'][cand], m['comp'][last]).astype(float)
        touchL = (m['touch'][np.ix_(cand, last)].sum(1) > 0).astype(float)
    else:
        same_comp = touchL = np.zeros(len(cand))
    comp_started = np.isin(m['comp'][cand], m['comp'][P]) if len(P) else np.zeros(len(cand), bool)
    fresh = (~comp_started).astype(float)
    prog = np.full(len(cand), placed.sum() / n)
    empty = np.full(len(cand), float(len(P) == 0))
    return np.column_stack([
        (touchS > 0).astype(float), np.log1p(touchS), (supp > 0).astype(float), (hang > 0).astype(float),
        dL, dS, relh, np.abs(relh), same_shape, same_sc,
        m['area'][cand], m['thick'][cand], m['deg'][cand], m['hop'][cand], m['geo'][cand], m['isroot'][cand],
        prog, empty, same_comp, touchL, fresh,
    ] + ([(m['heur'][cand] == m['heur'][cand].min()).astype(float),
          (m['heur'][cand] - m['heur'][cand].min()) / (m['heur'].max() + 1)] if USE_RULE else []))


def train_rows(m, color, max_rows=40000):
    t = m['truth']
    steps = np.unique(t)
    n = len(t)
    placed = np.zeros(n, bool)
    last = np.array([], int)
    Xs, ys = [], []
    for s in steps:
        cand = np.where(~placed)[0]
        X = state_features(m, placed, last, cand, color)
        y = (t[cand] == s).astype(int)
        Xs.append(X); ys.append(y)
        cur = np.where(t == s)[0]
        placed[cur] = True
        last = cur
    X, y = np.vstack(Xs), np.concatenate(ys)
    if len(y) > max_rows:   # 큰 모델이 학습을 독차지하지 않게 (양성은 다 남김)
        pos = np.where(y == 1)[0]; neg = np.where(y == 0)[0]
        neg = RNG.choice(neg, max(0, max_rows - len(pos)), replace=False)
        k = np.concatenate([pos, neg]); X, y = X[k], y[k]
    w = np.full(len(y), 1.0 / len(y))
    return X, y, w


def decode(clf, m, color, step_size=None):
    """탐욕적 생성: 매번 점수 1위 부품을 붙임. 같은 '단계' 묶기는 앱에서 따로."""
    n = len(m['truth'])
    placed = np.zeros(n, bool)
    last = np.array([], int)
    order = []
    while len(order) < n:
        cand = np.where(~placed)[0]
        p = clf.predict_proba(state_features(m, placed, last, cand, color))[:, 1]
        i = cand[int(np.argmax(p))]
        order.append(i); placed[i] = True
        last = np.array([i])
    rank = np.empty(n); rank[order] = np.arange(n)
    return rank


def next_hit(clf, m, color):
    """정답 접두사가 주어졌을 때 1순위 후보가 실제 다음 단계에 있는 비율"""
    t = m['truth']; n = len(t)
    placed = np.zeros(n, bool); last = np.array([], int)
    hits = []
    for s in np.unique(t)[:-1] if len(np.unique(t)) > 1 else []:
        cand = np.where(~placed)[0]
        p = clf.predict_proba(state_features(m, placed, last, cand, color))[:, 1]
        hits.append(t[cand[int(np.argmax(p))]] == s)
        cur = np.where(t == s)[0]; placed[cur] = True; last = cur
    return float(np.mean(hits)) if hits else float('nan')


def rule_next_hit(m):
    """비교: 지금 앱 규칙(heur 순서)에서 남은 것 중 가장 앞선 부품이 정답 다음 단계에 있는가"""
    t = m['truth']; h = m['heur']; n = len(t)
    placed = np.zeros(n, bool); hits = []
    for s in np.unique(t)[:-1]:
        cand = np.where(~placed)[0]
        best = cand[h[cand] == h[cand].min()]
        hits.append(np.mean(t[best] == s))        # 동점이면 평균 (무작위로 고른다고 봄)
        placed[t == s] = True
    return float(np.mean(hits))


def random_next_hit(m):
    t = m['truth']; placed = np.zeros(len(t), bool); hits = []
    for s in np.unique(t)[:-1]:
        cand = np.where(~placed)[0]
        hits.append(np.mean(t[cand] == s))
        placed[t == s] = True
    return float(np.mean(hits))


def main(save=False):
    models = load()
    colors = []
    for f, m in zip(sorted(glob.glob(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'feat', '*.json'))), models):
        d = json.load(open(f))
        colors.append(np.array([hash(b['color']) for b in d['bricks']]))
        prepare(m)
    rows = []
    FOLDS = int(os.environ.get('FOLDS', '0')) or len(models)   # 0 = 모델 하나씩 빼기
    rng = np.random.RandomState(0); fold_of = rng.permutation(len(models)) % FOLDS
    cache = [train_rows(m, colors[i]) for i, m in enumerate(models)]
    fitted = {}
    for k, test in enumerate(models):
        fk = fold_of[k]
        if fk not in fitted:
            data = [cache[i] for i in range(len(models)) if fold_of[i] != fk]
            X = np.vstack([d[0] for d in data]); y = np.concatenate([d[1] for d in data]); w = np.concatenate([d[2] for d in data]); w = w / w.mean()
            fitted[fk] = (LogisticRegression(C=1.0, max_iter=3000).fit(X, y, sample_weight=w),
                          HistGradientBoostingClassifier(max_iter=200, learning_rate=0.1, max_leaf_nodes=15, random_state=0).fit(X, y, sample_weight=w))
        lr, gb = fitted[fk]
        data = None
        col = colors[k]
        r = dict(name=test['name'], n=len(test['truth']),
                 rule=pair_acc(test['heur'], test['truth']),
                 lr=pair_acc(decode(lr, test, col), test['truth']),
                 gb=pair_acc(decode(gb, test, col), test['truth']),
                 hit_rand=random_next_hit(test), hit_rule=rule_next_hit(test),
                 hit_lr=next_hit(lr, test, col), hit_gb=next_hit(gb, test, col))
        rows.append(r)
        print(f"{r['name'][:26]:26s} n={r['n']:5d} | 순서 규칙 {r['rule']:.3f} LR {r['lr']:.3f} GB {r['gb']:.3f} | 다음부품 무작위 {r['hit_rand']:.2f} 규칙 {r['hit_rule']:.2f} LR {r['hit_lr']:.2f} GB {r['hit_gb']:.2f}", flush=True)
    keys = ['rule', 'lr', 'gb', 'hit_rand', 'hit_rule', 'hit_lr', 'hit_gb']
    print('평균', {k: round(float(np.mean([r[k] for r in rows])), 3) for k in keys})
    json.dump(rows, open(os.path.join(os.path.dirname(os.path.abspath(__file__)), os.environ.get('OUT','results_next3.json')), 'w'), ensure_ascii=False, indent=1)


if __name__ == '__main__':
    main()
