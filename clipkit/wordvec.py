# ---------------------------------------------------------------- 词表语义兜底
# 没有 torch 时，用 demo 生成的 lexicon.json + centers.npy 做一层「伪语义」：
# 把查询词映射到主题，再按主题中心向量排序。真实项目没有这套东西，会自动跳过。

def _load_lexicon(cfg):
    import numpy as np
    lex_p = os.path.join(cfg.index_dir, "lexicon.json")
    cen_p = os.path.join(cfg.index_dir, "centers.npy")
    if not (os.path.isfile(lex_p) and os.path.isfile(cen_p)):
        return None, None, None
    with open(lex_p, encoding="utf-8") as f:
        lex = json.load(f)
    cen = np.load(cen_p).astype("float32")
    topics = sorted(set(lex.values()))
    idx = {t: i for i, t in enumerate(topics)}
    return lex, cen, idx


def topic_vector(cfg, q):
    """查询 → 主题中心向量（查不到主题返回 None）"""
    try:
        lex, cen, idx = _load_lexicon(cfg)
    except Exception:
        return None
    if not lex:
        return None
    votes = {}
    for w, t in lex.items():
        if w and w in q:
            votes[t] = votes.get(t, 0) + len(w)
    if not votes:
        return None
    best = max(votes.items(), key=lambda kv: kv[1])[0]
    i = idx.get(best)
    return None if i is None else cen[i]
