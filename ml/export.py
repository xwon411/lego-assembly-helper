"""최종 모델: 65개 세트 전부로 그래디언트 부스팅 학습 → 앱에서 쓰는 JSON(ml/model.json)으로 내보냄.
그리고 '단계 묶기' 규칙 후보들을 교차검증 순서로 비교한다.
사용: python3 ml/export.py         (내보내기 + 묶기 비교)
"""
import json, os, glob, sys
import numpy as np
from sklearn.ensemble import HistGradientBoostingClassifier
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from order import load, pair_acc
from next import prepare, train_rows, state_features, FEAT_NAMES

HERE = os.path.dirname(os.path.abspath(__file__))
GB = dict(max_iter=200, learning_rate=0.1, max_leaf_nodes=15, random_state=0)


def load_all():
    models = load()
    colors = []
    for f, m in zip(sorted(glob.glob(os.path.join(HERE, 'feat', '*.json'))), models):
        d = json.load(open(f))
        colors.append(np.array([b['color'] for b in d['bricks']]))
        prepare(m)
    return models, colors


def fit(models, colors, idx):
    data = [train_rows(models[i], colors[i]) for i in idx]
    X = np.vstack([d[0] for d in data]); y = np.concatenate([d[1] for d in data])
    w = np.concatenate([d[2] for d in data]); w = w / w.mean()
    return HistGradientBoostingClassifier(**GB).fit(X, y, sample_weight=w)


def dump_trees(clf):
    trees = []
    for pred in clf._predictors:
        nodes = pred[0].nodes
        t = []
        for nd in nodes:
            if nd['is_leaf']:
                t.append([round(float(nd['value']), 6)])
            else:
                t.append([int(nd['feature_idx']), round(float(nd['num_threshold']), 6),
                          int(nd['left']), int(nd['right']), int(bool(nd['missing_go_to_left']))])
        trees.append(t)
    return dict(base=float(clf._baseline_prediction.ravel()[0]), trees=trees, features=FEAT_NAMES)


def greedy(clf, m, color):
    n = len(m['truth']); placed = np.zeros(n, bool); last = np.array([], int); order = []; probs = []
    while len(order) < n:
        cand = np.where(~placed)[0]
        p = clf.predict_proba(state_features(m, placed, last, cand, color))[:, 1]
        k = int(np.argmax(p)); i = cand[k]
        order.append(i); probs.append(p[k]); placed[i] = True; last = np.array([i])
    return order, probs


def group2(order, m, color, T):
    """목표 크기 T(= 부품 수 / 규칙 단계 수). T개가 차면 끊고, T/2 이상인데 이어지지 않는 부품이 오면 끊음."""
    steps = []; cur = []
    for i in order:
        if cur:
            same = any(m['shape'][i] == m['shape'][j] and color[i] == color[j] for j in cur)
            cont = same or m['touch'][i, cur].any()
            if len(cur) >= T or (len(cur) >= T / 2 and not cont):
                steps.append(cur); cur = []
        cur.append(i)
    if cur: steps.append(cur)
    rank = np.empty(len(order))
    for s_, arr in enumerate(steps): rank[arr] = s_
    return rank, len(steps)


def group(order, m, color, K=8):
    """탐욕 순서를 단계로 묶기: 같은 모양·색이 이어지거나, 지금 단계 부품에 닿고 같은 층(8 LDU)이면 같은 단계.
    한 단계 최대 K개."""
    steps = []; cur = []
    for i in order:
        if cur and len(cur) < K:
            same = any(m['shape'][i] == m['shape'][j] and color[i] == color[j] for j in cur)
            layer = abs(m['mn'][i, 1] - m['mn'][cur[0], 1]) < 8
            touch = m['touch'][i, cur].any()
            if same or (touch and layer):
                cur.append(i); continue
        if cur: steps.append(cur)
        cur = [i]
    if cur: steps.append(cur)
    rank = np.empty(len(order))
    for s, arr in enumerate(steps):
        rank[arr] = s
    return rank, len(steps)


def main():
    models, colors = load_all()
    clf = fit(models, colors, range(len(models)))
    out = dump_trees(clf)
    json.dump(out, open(os.path.join(HERE, 'model.json'), 'w'), separators=(',', ':'), ensure_ascii=False)
    print('model.json', os.path.getsize(os.path.join(HERE, 'model.json')) // 1024, 'KB,', len(out['trees']), 'trees')

    # 묶기 비교 (5겹, next.py와 같은 나누기)
    FOLDS = 5
    fold_of = np.random.RandomState(0).permutation(len(models)) % FOLDS
    rows = []
    for fk in range(FOLDS):
        c = fit(models, colors, [i for i in range(len(models)) if fold_of[i] != fk])
        for k in np.where(fold_of == fk)[0]:
            m, col = models[k], colors[k]
            order, _ = greedy(c, m, col)
            r = dict(name=m['name'], rule=pair_acc(m['heur'], m['truth']),
                     n_rule=len(np.unique(m['heur'])), n_truth=len(np.unique(m['truth'])))
            full = np.empty(len(order)); full[order] = np.arange(len(order))
            r['ai_parts'] = pair_acc(full, m['truth'])
            for K in (4, 8, 12):
                rank, ns = group(order, m, col, K)
                r[f'ai_K{K}'] = pair_acc(rank, m['truth']); r[f'n_K{K}'] = ns
            T = max(1, round(len(order) / max(1, len(np.unique(m['heur'])))))
            rank, ns = group2(order, m, col, T); r['ai_T'] = pair_acc(rank, m['truth']); r['n_T'] = ns
            rows.append(r)
            print(f"{r['name'][:24]:24s} 규칙 {r['rule']:.3f} AI {r['ai_parts']:.3f} K8 {r['ai_K8']:.3f} | 단계 수 정답 {r['n_truth']} 규칙 {r['n_rule']} AI {r['n_K8']}", flush=True)
    keys = [k for k in rows[0] if k != 'name']
    print('평균', {k: round(float(np.mean([r[k] for r in rows])), 3) for k in keys})
    json.dump(rows, open(os.path.join(HERE, 'results_group.json'), 'w'), ensure_ascii=False, indent=1)


if __name__ == '__main__':
    main()
