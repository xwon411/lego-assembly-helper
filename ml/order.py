"""조립 순서 학습 실험.

문제: 부품 i, j 중 무엇을 먼저 조립하는가 (쌍 분류) → 점수로 바꿔 전체 순서를 만든다.
평가: 정답 단계가 다른 부품 쌍 중 순서를 맞힌 비율(쌍 정확도). 예측이 동점이면 0.5점.
검증: 모델 단위로 하나씩 빼고 학습(leave-one-model-out), 모델별 점수의 평균.
"""
import json, os, glob, sys
import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import HistGradientBoostingClassifier

RNG = np.random.default_rng(0)
TOL = 2.0       # 맞닿음 판정 허용 오차 (LDU)
MAX_PAIRS = 30000  # 모델당 학습 쌍 상한 (큰 모델이 학습을 독차지하지 않게)


def load():
    models = []
    for f in sorted(glob.glob(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'feat', '*.json'))):
        d = json.load(open(f))
        B = d['bricks']
        mn = np.array([b['min'] for b in B], float)
        mx = np.array([b['max'] for b in B], float)
        models.append(dict(name=d['name'], mn=mn, mx=mx,
                           truth=np.array([b['step'] for b in B], float),
                           heur=np.array([b['heur'] for b in B], float)))
    return models


def relations(mn, mx):
    """부품 사이 관계 행렬.
    below[i,j]: i가 j 바로 아래에서 받침. 상자에 윗면 돌기(4 LDU)가 들어 있어서 끼워진 두 부품은
                y로 0~4 LDU 겹친다 → 겹침이 -1~6 LDU이고 xz가 겹치면 받침으로 봄.
    touch[i,j]: 상자를 2 LDU 키웠을 때 서로 닿음 (받침 포함, 그래프용)."""
    ox = np.minimum(mx[:, None, 0], mx[None, :, 0]) - np.maximum(mn[:, None, 0], mn[None, :, 0])
    oy = np.minimum(mx[:, None, 1], mx[None, :, 1]) - np.maximum(mn[:, None, 1], mn[None, :, 1])
    oz = np.minimum(mx[:, None, 2], mx[None, :, 2]) - np.maximum(mn[:, None, 2], mn[None, :, 2])
    area = (mx[:, 0] - mn[:, 0]) * (mx[:, 2] - mn[:, 2]) + 1e-6
    overlap_xz = np.clip(ox, 0, None) * np.clip(oz, 0, None)
    frac = overlap_xz / np.minimum(area[:, None], area[None, :])
    gap = mx[:, None, 1] - mn[None, :, 1]
    cy = (mn[:, 1] + mx[:, 1]) / 2
    below = (gap > -1) & (gap < 6) & (overlap_xz > 4) & (cy[:, None] < cy[None, :])
    touch = (ox > -TOL) & (oy > -TOL) & (oz > -TOL)
    side = touch & ~below & ~below.T
    np.fill_diagonal(below, False); np.fill_diagonal(side, False); np.fill_diagonal(touch, False)
    return below, side, frac


def graph_hops(mn, mx, below, side):
    """맞닿은 부품끼리 잇는 그래프에서, 덩어리(서로 안 닿는 모델)마다 '뿌리'(가장 큰 부품)를 잡고
    뿌리로부터 몇 칸 떨어졌는지. 방향(아래→위, 뒤집어 만들기)과 상관없이 '기본 부품에서 바깥으로 자라는' 정도."""
    from scipy.sparse.csgraph import shortest_path, connected_components
    adj = (below | below.T | side).astype(float)
    n = len(mn)
    vol = (mx[:, 0] - mn[:, 0]) * (mx[:, 2] - mn[:, 2]) * np.maximum(mx[:, 1] - mn[:, 1], 1)
    ncomp, lab = connected_components(adj, directed=False)
    hop = np.zeros(n); geo = np.zeros(n); isroot = np.zeros(n); dy = np.zeros(n)
    c = (mn + mx) / 2
    H = (mx[:, 1].max() - mn[:, 1].min()) + 1e-6
    for k in range(ncomp):
        idx = np.where(lab == k)[0]
        root = idx[np.argmax(vol[idx])]
        h = shortest_path(adj, unweighted=True, indices=root)[idx]
        hop[idx] = h / (h.max() + 1e-6) if len(idx) > 1 else 0
        g = np.linalg.norm(c[idx] - c[root], axis=1)
        geo[idx] = g / (g.max() + 1e-6) if len(idx) > 1 else 0
        dy[idx] = (c[idx, 1] - c[root, 1]) / H
        isroot[root] = 1
    size = np.bincount(lab)[lab] / n           # 내가 속한 덩어리의 크기 비율
    return hop, geo, isroot, dy, np.abs(dy), size


def node_features(mn, mx, below, side):
    H = (mx[:, 1].max() - mn[:, 1].min()) + 1e-6
    W = max(mx[:, 0].max() - mn[:, 0].min(), mx[:, 2].max() - mn[:, 2].min()) + 1e-6
    c = (mn + mx) / 2
    size = mx - mn
    y0 = mn[:, 1].min()
    cx, cz = c[:, 0].mean(), c[:, 2].mean()
    n_below = below.sum(0)   # 나를 받치는 부품 수
    n_above = below.sum(1)   # 내가 받치는 부품 수
    f = np.column_stack([
        (mn[:, 1] - y0) / H,                    # 바닥 높이 (정규화)
        (mx[:, 1] - y0) / H,                    # 윗면 높이
        np.hypot(c[:, 0] - cx, c[:, 2] - cz) / W,  # 가운데에서 떨어진 정도
        (c[:, 0] - mn[:, 0].min()) / W,         # x 위치
        (c[:, 2] - mn[:, 2].min()) / W,         # z 위치
        np.log1p(size[:, 0] * size[:, 2]),      # 바닥 면적
        np.log1p(size[:, 1]),                   # 두께
        np.log1p(n_below), np.log1p(n_above), np.log1p(side.sum(1)),
        (mn[:, 1] - y0 < TOL).astype(float),    # 바닥에 놓임
        *graph_hops(mn, mx, below, side),       # 뿌리에서 홉 거리, 기하 거리, 뿌리 여부
    ])
    return f


NODE_NAMES = ['바닥높이', '윗면높이', '중심거리', 'x', 'z', 'log면적', 'log두께', 'log받침수', 'log위부품수', 'log옆접촉수', '바닥에놓임', '뿌리홉', '뿌리거리', '뿌리', '뿌리기준높이', '뿌리기준|높이|', '덩어리크기']


def pair_features(F, below, side, frac, I, J, mn):
    d = F[I] - F[J]
    rel = np.column_stack([
        below[I, J].astype(float) - below[J, I].astype(float),   # i가 j를 받침(+1) / j가 i를 받침(-1)
        side[I, J].astype(float),
        frac[I, J],
        np.sign(mn[I, 1] - mn[J, 1]) * frac[I, J],              # xz가 겹치는데 i가 위인가
    ])
    return np.hstack([d, rel])


PAIR_NAMES = ['Δ' + n for n in NODE_NAMES] + ['받침관계(i→j)', '옆맞닿음', 'xz겹침', '겹침×위아래']


def prepare(m):
    below, side, frac = relations(m['mn'], m['mx'])
    F = node_features(m['mn'], m['mx'], below, side)
    m.update(below=below, side=side, frac=frac, F=F)


def train_pairs(m):
    t = m['truth']
    n = len(t)
    I, J = np.where(t[:, None] != t[None, :])
    if len(I) > MAX_PAIRS:
        k = RNG.choice(len(I), MAX_PAIRS, replace=False)
        I, J = I[k], J[k]
    X = pair_features(m['F'], m['below'], m['side'], m['frac'], I, J, m['mn'])
    y = (t[I] < t[J]).astype(int)           # 1 = i가 먼저
    w = np.full(len(I), 1.0 / len(I))        # 모델마다 같은 무게
    return X, y, w


def scores_from_model(clf, m):
    """모든 쌍의 '먼저일 확률'을 평균해 부품별 점수 (작을수록 먼저)"""
    n = len(m['truth'])
    I, J = np.meshgrid(np.arange(n), np.arange(n), indexing='ij')
    I, J = I.ravel(), J.ravel()
    keep = I != J
    I, J = I[keep], J[keep]
    p = np.zeros(len(I))
    for s in range(0, len(I), 400000):
        X = pair_features(m['F'], m['below'], m['side'], m['frac'], I[s:s+400000], J[s:s+400000], m['mn'])
        p[s:s+400000] = clf.predict_proba(X)[:, 1]
    P = np.full((n, n), 0.5)
    P[I, J] = p
    return -P.mean(1)          # 먼저일 확률이 높을수록 작은 점수


def pair_acc(score, truth):
    I, J = np.where(truth[:, None] < truth[None, :])       # i가 정답상 먼저
    ds = score[I] - score[J]
    return float(((ds < 0) + 0.5 * (ds == 0)).mean())


def main():
    models = load()
    for m in models:
        prepare(m)
    rows = []
    for k, test in enumerate(models):
        tr = [m for i, m in enumerate(models) if i != k]
        Xs, ys, ws = zip(*[train_pairs(m) for m in tr])
        X, y, w = np.vstack(Xs), np.concatenate(ys), np.concatenate(ws)
        w = w / w.mean()
        lr = LogisticRegression(C=1.0, max_iter=2000).fit(X, y, sample_weight=w)
        gb = HistGradientBoostingClassifier(max_iter=200, learning_rate=0.1, max_leaf_nodes=31, random_state=0).fit(X, y, sample_weight=w)
        r = dict(name=test['name'], n=len(test['truth']),
                 rule=pair_acc(test['heur'], test['truth']),
                 height=pair_acc(test['mn'][:, 1], test['truth']),
                 hop=pair_acc(test['F'][:, 11] + 1e-3 * test['F'][:, 12], test['truth']),
                 lr=pair_acc(scores_from_model(lr, test), test['truth']),
                 gb=pair_acc(scores_from_model(gb, test), test['truth']))
        rows.append(r)
        print(f"{r['name'][:28]:28s} n={r['n']:5d}  규칙 {r['rule']:.3f}  높이 {r['height']:.3f}  홉 {r['hop']:.3f}  LR {r['lr']:.3f}  GB {r['gb']:.3f}", flush=True)
    avg = {k: np.mean([r[k] for r in rows]) for k in ['rule', 'height', 'hop', 'lr', 'gb']}
    print('평균(모델별 동일 가중)', {k: round(v, 3) for k, v in avg.items()})
    json.dump(rows, open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'results_v3.json'), 'w'), ensure_ascii=False, indent=1)


if __name__ == '__main__':
    main()
