# -*- coding: utf-8 -*-
"""检索引擎：向量可用时走「视觉相似 + VLM 描述关键词」混合排序，
没有向量时自动降级为纯关键词，功能不中断。"""
import os, re
from . import store as S


class Encoder(object):
    """中文-CLIP 文本编码器（惰性加载，没装 torch 就返回 None）"""

    def __init__(self, model_name, device=None):
        self.model_name = model_name
        self.device = device
        self.model = None
        self.proc = None
        self.lock = None
        self.error = ""

    def available(self):
        try:
            import torch, transformers  # noqa
            return True
        except Exception as e:
            self.error = "%s: %s" % (type(e).__name__, e)
            return False

    def load(self):
        if self.model is not None:
            return True
        if not self.available():
            return False
        import threading, torch
        from transformers import ChineseCLIPModel, ChineseCLIPProcessor
        if self.device is None:
            self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self.lock = threading.Lock()
        self.model = ChineseCLIPModel.from_pretrained(self.model_name).to(self.device).eval()
        self.proc = ChineseCLIPProcessor.from_pretrained(self.model_name)
        return True

    @staticmethod
    def _pick(o):
        import torch
        if torch.is_tensor(o):
            return o
        for k in ("text_embeds", "pooler_output"):
            v = getattr(o, k, None)
            if torch.is_tensor(v):
                return v
        return o.last_hidden_state[:, 0]

    def encode(self, text):
        """返回归一化后的 1D numpy 向量；不可用时返回 None"""
        if not self.load():
            return None
        import torch
        with self.lock, torch.no_grad():
            inp = self.proc(text=[text], return_tensors="pt", padding=True).to(self.device)
            t = self._pick(self.model.get_text_features(**inp)).float()
            t = t / t.norm(dim=-1, keepdim=True)
            return t.cpu().numpy()[0]
    
    def encode_batch(self, texts):
        if not self.load():
            return None
        import numpy as np, torch
        out = []
        with self.lock, torch.no_grad():
            for i in range(0, len(texts), 64):
                chunk = texts[i:i + 64]
                inp = self.proc(text=chunk, return_tensors="pt", padding=True,
                                truncation=True, max_length=64).to(self.device)
                e = self._pick(self.model.get_text_features(**inp)).float()
                e = e / e.norm(dim=-1, keepdim=True)
                out.append(e.cpu().numpy())
        return np.concatenate(out) if out else None


class Searcher(object):
    def __init__(self, store, encoder=None):
        self.st = store
        self.enc = encoder

    @property
    def semantic(self):
        return self.st.vnorm is not None and self.enc is not None and self.enc.available()

    def subs(self, q, top=20):
        """台词检索：关键词优先，语义兜底"""
        q = (q or "").strip()
        if not q or not self.st.subs:
            return [], "none"
        res = self.st.search_subs_keyword(q, top=top)
        if res:
            return res, "keyword"
        if not self.semantic or not re.search(r"[\u4e00-\u9fff]", q):
            return [], "none"
        segs, texts = [], []
        for clip, d in self.st.subs.items():
            for seg in d["segs"]:
                t = (seg.get("text") or "").strip()
                if t:
                    segs.append((clip, seg))
                    texts.append(t)
        if not texts:
            return [], "none"
        tv = self.enc.encode(q)
        if tv is None:
            return [], "none"
        mat = self.enc.encode_batch(texts)
        if mat is None:
            return [], "none"
        sim = mat @ tv
        order = sim.argsort()[::-1]
        grouped = {}
        for i in order:
            sc = float(sim[i])
            if sc < 0.18:
                break
            clip, seg = segs[int(i)]
            grouped.setdefault(clip, []).append(
                {"s": seg["start"], "e": seg["end"], "t": seg["text"], "sc": round(sc, 3)})
            if len(grouped) >= top:
                break
        out = [{"clip": c, "dur": self.st.subs[c]["dur"], "score": h[0].get("sc", 0),
                "hits": sorted(h, key=lambda x: x["s"]), "match": "semantic"}
               for c, h in grouped.items()]
        return out, ("semantic" if out else "none")

    def frames(self, q, top=12, dedup=True, cats=None):
        """画面检索：返回 results + meta"""
        q = (q or "").strip()
        meta = {"mode": "keyword", "terms": [], "text_hits": 0, "hidden_by_cat": 0}
        if not q or not self.st.rows:
            return [], meta
        terms = S.terms_of(q)
        meta["terms"] = terms
        thits = self.st.text_hits(terms)
        meta["text_hits"] = len(thits)
        cats = set(cats) if cats else None

        scored = []
        if self.st.vnorm is not None and self.enc is not None:
            tv = self.enc.encode(q)
        else:
            tv = None

        if tv is not None:
            meta["mode"] = "hybrid"
            sims = self.st.vnorm @ tv
            cand = set(int(i) for i in sims.argsort()[::-1][:700])
            for i, r in enumerate(self.st.rows):
                if (r.get("clip", ""), r.get("frame", "")) in thits:
                    cand.add(i)
            maxt = max([v[0] for v in thits.values()], default=1.0)
            for i in cand:
                r = self.st.rows[i]
                if cats and not (self.st.clip_cats.get(r.get("clip", ""), set()) & cats):
                    meta["hidden_by_cat"] += 1
                    continue
                s = float(sims[i])
                te = thits.get((r.get("clip", ""), r.get("frame", "")), (0.0, []))
                bonus = 0.10 * (te[0] / maxt) if maxt else 0.0
                scored.append((s + bonus, s, te[0], te[1], i))
            scored.sort(key=lambda x: -x[0])
        else:
            meta["mode"] = "keyword"
            order = self.st.keyword_hits(terms)
            idx = {(r.get("clip", ""), r.get("frame", "")): i for i, r in enumerate(self.st.rows)}
            for key in order:
                i = idx.get(key)
                if i is None:
                    continue
                r = self.st.rows[i]
                if cats and not (self.st.clip_cats.get(r.get("clip", ""), set()) & cats):
                    meta["hidden_by_cat"] += 1
                    continue
                te = thits.get(key, (0.0, []))
                scored.append((te[0], te[0], te[0], te[1], i))

        return self._pack(scored, top, dedup), meta

    def _pack(self, scored, top, dedup):
        out, seen = [], set()
        for final, s, ts, hits, i in scored:
            r = self.st.rows[i]
            clip = r.get("clip", "")
            frame = r.get("frame", "")
            if dedup and clip in seen:
                continue
            seen.add(clip)
            tag = self.st.tags.get((clip, frame), {})
            keyw = []
            for t in (tag.get("tags") or []):
                if "," in t:
                    keyw = [x.strip() for x in t.split(",") if x.strip()]
                    break
            out.append({
                "rank": len(out) + 1,
                "img": r.get("img", ""), "clip": clip, "frame": frame,
                "at": r.get("at") or "—", "approx_sec": r.get("approx_sec") or "",
                "group": r.get("group", ""), "dur": r.get("dur", ""),
                "score": round(float(final), 4), "sim": round(float(s), 4),
                "text": round(float(ts), 2), "hits": list(hits)[:4],
                "desc": (tag.get("desc") or "").strip(), "keywords": keyw[:8],
                "cats": [c for c in S.CATS
                         if c in self.st.clip_cats.get(clip, set())][:3],
            })
            if len(out) >= top:
                break
        return out
