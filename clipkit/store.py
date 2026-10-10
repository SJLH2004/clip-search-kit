# -*- coding: utf-8 -*-
"""数据层：索引 / VLM 描述 / 台词库的加载与分类。

不依赖 torch —— 只要 numpy。检索、分类、时间线都不需要模型。
"""
import os, csv, json, re, collections

CATS = ["武馆·训练", "武馆·师父", "手部特写", "人物·面部", "器械·兵器",
        "拳谱·史料", "仪式·祭祀", "群体·队列", "博物馆·展览", "室内·生活",
        "户外·城市", "户外·自然", "其他"]

# 每个类别的关键词兜底规则（结构化信号缺失时使用）
CAT_RULES = [
    ("拳谱·史料", "拳谱|书页|字迹|文献|古籍|史料|族谱|纸张|字条|卷轴"),
    ("仪式·祭祀", "祭祀|祭拜|上香|跪拜|牌位|祠堂|香炉|香烛"),
    ("武馆·师父", "师父|师傅|教练在|指导"),
    ("武馆·训练", "训练|练拳|打拳|练功|对练|推手|沙袋|招式|定式|扎马步"),
    ("博物馆·展览", "博物馆|展览|展品|展厅|雕塑|陈列|文物"),
    ("户外·自然", "树林|山间|江边|河边|田野|草地|自然风光|下雨|雪地|山林"),
    ("户外·城市", "街道|马路|楼房|建筑|航拍|鸟瞰|广场|公园|大桥|城市"),
    ("室内·生活", "室内|房间|宿舍|客厅|办公室|餐桌|吃饭|坐着|说话|卧室"),
    ("群体·队列", "队列|成排|成群|一群人|多人站|排列|集体"),
]


def parse_visual(desc):
    """从 VLM 描述的「画面」字段抽结构化信号 → (景别, 有无手部特写, 器械)"""
    shot, hand, equip = "", "", ""
    for line in (desc or "").split(chr(10)):
        if not line.startswith("画面"):
            continue
        body = line.split(":", 1)[-1].replace("：", "；")
        body = body.replace(",", "；").replace("，", "；")
        for part in body.split("；"):
            p = part.strip()
            if not p:
                continue
            if p.startswith("有手部特写") or p.startswith("有手"):
                hand = "有"
            elif p.startswith("无手部特写") or p.startswith("无手"):
                hand = "无"
            elif p.startswith("有器械") or p.startswith("无器械"):
                equip = p
            elif p in ("全景", "中景", "近景", "特写", "远景"):
                shot = p
    return shot, hand, equip


def infer_cats(text):
    text = text or ""
    shot, hand, equip = parse_visual(text)
    out = []
    if hand == "有" or shot == "特写":
        out.append("手部特写")
    if "面部特写" in text or "人脸" in text or re.search("表情|眼神|面孔", text):
        out.append("人物·面部")
    if equip.startswith("有"):
        out.append("器械·兵器")
    for name, pat in CAT_RULES:
        if re.search(pat, text):
            out.append(name)
    if "户外·自然" in out and "户外·城市" in out:
        out.remove("户外·自然")
    return out or ["其他"]


def terms_of(q):
    """查询切词：中文按 1~3 字 n-gram + 整词，英文按 token"""
    q = (q or "").strip()
    if not q:
        return []
    raw = [t for t in re.split(r"[\s,，、;；/|]+", q) if t]
    out, seen = [], set()

    def add(t):
        t = t.strip()
        if t and t not in seen:
            seen.add(t)
            out.append(t)

    for t in raw:
        add(t)
        for seg in re.findall(r"[\u4e00-\u9fff]+", t):
            if len(seg) <= 3:
                add(seg)
            else:
                for n in (3, 2):
                    for i in range(len(seg) - n + 1):
                        add(seg[i:i + n])
        for w in re.findall(r"[A-Za-z0-9_]+", t):
            add(w)
    out.sort(key=len, reverse=True)
    return out[:14]


def score_text(text, terms):
    if not text:
        return 0.0, []
    low = text.lower()
    s, hit = 0.0, []
    for t in terms:
        c = low.count(t.lower())
        if c:
            w = 2.2 if len(t) >= 3 else (1.5 if len(t) == 2 else 1.0)
            s += w * (1 + min(c - 1, 2) * 0.3)
            hit.append(t)
    return s, hit


class Store(object):
    """加载索引 + 描述 + 台词，提供检索所需的全部数据"""

    def __init__(self, cfg, load_vectors=True, quiet=False):
        self.cfg = cfg
        self.rows = []
        self.tags = {}
        self.subs = {}
        self.vectors = None
        self.vnorm = None
        self.clip_cats = {}
        self.cat_buckets = {}
        self.missing = []
        self._load(load_vectors, quiet)

    def _load(self, load_vectors, quiet):
        cfg = self.cfg
        if os.path.isfile(cfg.index_file):
            with open(cfg.index_file, encoding="utf-8-sig") as f:
                self.rows = list(csv.DictReader(f))
        else:
            self.missing.append(cfg.index_file)

        if load_vectors and os.path.isfile(cfg.vectors_file):
            import numpy as np
            v = np.load(cfg.vectors_file).astype(np.float32)
            if len(self.rows) and v.shape[0] != len(self.rows):
                raise SystemExit("索引不一致：%d 行 vs %d 个向量。重建索引：python -m clipkit index"
                                 % (len(self.rows), v.shape[0]))
            n = np.linalg.norm(v, axis=1, keepdims=True)
            self.vectors = v
            self.vnorm = v / np.where(n == 0, 1.0, n)
        elif load_vectors:
            self.missing.append(cfg.vectors_file)

        if os.path.isfile(cfg.tags_file):
            with open(cfg.tags_file, encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        d = json.loads(line)
                    except Exception:
                        continue
                    if d.get("ok"):
                        self.tags[(d.get("clip", ""), d.get("frame", ""))] = d
        else:
            self.missing.append(cfg.tags_file)

        if os.path.isfile(cfg.transcripts_file):
            with open(cfg.transcripts_file, encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        d = json.loads(line)
                    except Exception:
                        continue
                    if d.get("ok") and d.get("segments"):
                        self.subs[d.get("clip", "")] = {"dur": d.get("dur", 0),
                                                        "segs": d["segments"]}
        else:
            self.missing.append(cfg.transcripts_file)

        self._index_cats()

    def _index_cats(self):
        for c in CATS:
            self.cat_buckets[c] = []
        for r in self.rows:
            k = (r.get("clip", ""), r.get("frame", ""))
            t = self.tags.get(k)
            src = ((t.get("desc", "") if t else "") + " " + r.get("img", ""))
            cs = infer_cats(src)
            self.clip_cats.setdefault(r.get("clip", ""), set()).update(cs)
            for c in cs:
                self.cat_buckets.setdefault(c, []).append(k)

    # ---- 概览 ----
    @property
    def n_frames(self):
        return len(self.rows)

    @property
    def n_clips(self):
        return len({r.get("clip", "") for r in self.rows})

    def stats(self):
        return {"frames": self.n_frames, "clips": self.n_clips,
                "tags": len(self.tags), "subs": len(self.subs),
                "categories": {c: len(self.cat_buckets.get(c, [])) for c in CATS},
                "missing": self.missing}

    # ---- 台词 ----
    def all_subs_for(self, clip, maxn=40):
        d = self.subs.get(clip)
        if not d:
            return []
        return [{"s": s["start"], "e": s["end"], "t": s.get("text", "")}
                for s in d["segs"] if s.get("text")][:maxn]

    def search_subs_keyword(self, q, top=20):
        keys = [k for k in re.split(r"[\s,，、]+", q) if k]
        if not keys:
            return []
        out = []
        for clip, d in self.subs.items():
            hits, score = [], 0
            for seg in d["segs"]:
                t = seg.get("text", "")
                if not t:
                    continue
                n = sum(t.count(k) for k in keys)
                if n:
                    hits.append({"s": seg["start"], "e": seg["end"], "t": t})
                    score += n
            if hits:
                out.append({"clip": clip, "dur": d["dur"], "score": score,
                            "hits": hits, "match": "keyword"})
        out.sort(key=lambda x: -x["score"])
        return out[:top]

    # ---- 画面 ----
    def text_hits(self, terms, max_hits=500):
        if not terms:
            return {}
        res = {}
        for key, d in self.tags.items():
            blob = (d.get("desc", "") or "") + " " + " ".join(d.get("tags") or [])
            s, hit = score_text(blob, terms)
            if s > 0:
                res[key] = (s, hit)
        if len(res) > max_hits:
            res = dict(sorted(res.items(), key=lambda kv: -kv[1][0])[:max_hits])
        return res

    def keyword_hits(self, terms, max_hits=500):
        """没有向量时的纯关键词检索（降级路径）"""
        res = []
        for key, (s, hit) in self.text_hits(terms, max_hits).items():
            res.append((s, key))
        res.sort(key=lambda x: -x[0])
        return [k for _, k in res]

    def timeline(self, results, maxn=40):
        ev = []
        for r in results[:maxn]:
            sec = None
            m = re.match(r"([\d.]+)s", r.get("approx_sec") or "")
            if m:
                try:
                    sec = float(m.group(1))
                except ValueError:
                    sec = None
            ev.append({"kind": "frame", "clip": r["clip"], "sec": sec,
                       "label": "%s · %s" % (r.get("frame", ""), r.get("at", "")),
                       "img": r.get("img", ""), "desc": r.get("desc", ""),
                       "keywords": r.get("keywords", []), "score": r.get("score")})
            for s in self.subs.get(r["clip"], {"segs": []})["segs"]:
                t = (s.get("text") or "").strip()
                if t:
                    ev.append({"kind": "sub", "clip": r["clip"], "sec": s["start"],
                               "end": s["end"], "label": t, "text": t})
        ev.sort(key=lambda x: (x["clip"], x["sec"] if x["sec"] is not None else 0))
        return ev
